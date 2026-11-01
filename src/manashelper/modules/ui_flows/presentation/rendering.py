from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urlsplit

from aiogram.utils.i18n import gettext as _

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.ui_flows.catalog import get_catalog_texts
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from ui_flows.application.interpreter import EvaluationContext
from ui_flows.domain.delivery import Screen, ScreenButton
from ui_flows.domain.schema import (
    CatalogText,
    EndNode,
    FlowDocument,
    InputNode,
    MenuNode,
    Scalar,
    Text,
    template_parameters,
)
from ui_flows.domain.state import ExecutionResult, RuntimeUser
from ui_flows.errors import FlowExecutionError


class InvalidScreenError(FlowExecutionError):
    node_id: str | None = None
    path: str = "/document/nodes"


def _units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class _TelegramHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self.length = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {
            "b",
            "strong",
            "i",
            "em",
            "u",
            "ins",
            "s",
            "strike",
            "del",
            "tg-spoiler",
            "code",
            "pre",
            "blockquote",
            "a",
        }:
            raise InvalidScreenError("Unsupported Telegram HTML tag")
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise InvalidScreenError("Repeated HTML attribute")
        if tag == "a":
            if set(attributes) != {"href"} or urlsplit(attributes["href"] or "").scheme not in {"http", "https", "tg"}:
                raise InvalidScreenError("Unsupported Telegram link")
        elif attributes:
            raise InvalidScreenError("Unsupported Telegram HTML attribute")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack.pop() != tag:
            raise InvalidScreenError("Unbalanced Telegram HTML")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raise InvalidScreenError("Self-closing tags are not supported")

    def handle_comment(self, data: str) -> None:
        raise InvalidScreenError("HTML comments are not supported")

    def handle_data(self, data: str) -> None:
        if "<" in data:
            raise InvalidScreenError("Unescaped HTML delimiter")
        self.length += _units(data)

    def handle_entityref(self, name: str) -> None:
        if name not in {"lt", "gt", "amp", "quot"}:
            raise InvalidScreenError("Unsupported Telegram HTML entity")
        self.length += 1

    def handle_charref(self, name: str) -> None:
        try:
            value = int(name[1:], 16) if name.startswith(("x", "X")) else int(name)
            self.length += _units(chr(value))
        except (ValueError, UnicodeError):
            raise InvalidScreenError("Invalid Unicode entity") from None

    def handle_decl(self, decl: str) -> None:
        raise InvalidScreenError("HTML declarations are not supported")

    def handle_pi(self, data: str) -> None:
        raise InvalidScreenError("HTML instructions are not supported")


def validate_message(text: str) -> None:
    parser = _TelegramHtml()
    parser.feed(text)
    parser.close()
    if parser.stack or not 1 <= parser.length <= 4096:
        raise InvalidScreenError("Invalid Telegram message length or markup")


def _render(text: Text, context: EvaluationContext, catalog: dict[str, str], user: RuntimeUser, *, html: bool) -> str:
    if isinstance(text, CatalogText):
        template = catalog.get(text.key)
        if template is None:
            raise InvalidScreenError("Unknown catalog template")
    else:
        themed = text.themes.get("halloween", {}) if user.theme == "halloween" else {}
        template = (
            themed.get(user.locale) or text.translations.get(user.locale) or themed.get("en") or text.translations["en"]
        )
    if template_parameters(template) != text.parameters.keys():
        raise InvalidScreenError("Template parameters do not match the bindings")
    parameters = {}
    for name, binding in text.parameters.items():
        value = context.resolve(binding)
        if isinstance(value, bool):
            formatted = _("student_questions.yes") if value else _("student_questions.no")
        else:
            formatted = "" if value is None else str(value)
        parameters[name] = escape_html(formatted) if html else formatted
    return template.format_map(parameters)


class FlowRenderer:
    def validate_document(
        self, document: FlowDocument, capabilities: dict[str, str | bool | int | float | None]
    ) -> None:
        samples: dict[str, Scalar] = {"text": "value", "integer": 1, "number": 1.0, "boolean": True}
        data = {name: samples[field.type] for name, field in document.fields.items()}
        for locale in Locale:
            for theme in Theme:
                user = RuntimeUser(1, 1, locale.value, theme.value)
                with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
                    catalog = get_catalog_texts()
                    context = EvaluationContext(document, data, user, capabilities)
                    for index, node in enumerate(document.nodes):
                        if not isinstance(node, (MenuNode, InputNode, EndNode)):
                            continue
                        try:
                            body = "\n\n".join(_render(text, context, catalog, user, html=True) for text in node.text)
                            if body:
                                validate_message(body)
                            if isinstance(node, InputNode):
                                validate_message(_render(node.error, context, catalog, user, html=True) + "\n\n" + body)
                            if isinstance(node, (MenuNode, InputNode)):
                                unconditional_labels = set()
                                for row in node.buttons:
                                    for button in row:
                                        label = _render(button.label, context, catalog, user, html=False)
                                        if not label.strip() or _units(label) > 64:
                                            raise InvalidScreenError("Button label exceeds editor limits")
                                        if (
                                            isinstance(node, MenuNode)
                                            and node.keyboard == "reply"
                                            and button.when is None
                                        ):
                                            if label in unconditional_labels:
                                                raise InvalidScreenError("Reply button labels are ambiguous")
                                            unconditional_labels.add(label)
                        except InvalidScreenError as error:
                            error.node_id, error.path = node.id, f"/nodes/{index}"
                            raise

    def render(
        self,
        document: FlowDocument,
        result: ExecutionResult,
        user: RuntimeUser,
        capabilities: dict[str, str | bool | int | float | None],
    ) -> Screen:
        with i18n.context(), i18n.use_locale(user.locale), i18n.use_theme(Theme(user.theme)):
            catalog = get_catalog_texts()
            context = EvaluationContext(document, result.state.data, user, capabilities)
            node = result.node
            if result.outcome == "cancelled" and result.returned_from is None:
                return Screen(text=_("ui_flows.cancelled"), keyboard="main", locale=user.locale, theme=user.theme)
            if not isinstance(node, (MenuNode, InputNode, EndNode)):
                raise InvalidScreenError("Automatic nodes cannot be displayed")
            parts = [_render(text, context, catalog, user, html=True) for text in node.text]
            if result.outcome == "invalid_input" and isinstance(node, InputNode):
                parts.insert(0, _render(node.error, context, catalog, user, html=True))
            feature = node.feature if isinstance(node, EndNode) else None
            body = "\n\n".join(parts) or ("" if feature else _("ui_flows.completed"))
            if body:
                validate_message(body)
            keyboard: Literal["reply", "inline", "main", "none"] = (
                node.keyboard
                if isinstance(node, MenuNode)
                else ("none" if feature else ("main" if isinstance(node, EndNode) else "inline"))
            )
            rows = []
            labels = set()
            if isinstance(node, (MenuNode, InputNode)):
                for row in node.buttons:
                    rendered_row = []
                    for button in row:
                        if button.when is not None and not context.matches(button.when):
                            continue
                        label = _render(button.label, context, catalog, user, html=False)
                        if not label.strip() or _units(label) > 64:
                            raise InvalidScreenError("Button label exceeds editor limits")
                        if keyboard == "reply" and label in labels:
                            raise InvalidScreenError("Reply button labels are ambiguous")
                        labels.add(label)
                        url = str(button.url) if hasattr(button, "url") else None
                        rendered_row.append(ScreenButton(id=button.id, label=label, url=url))
                    if rendered_row:
                        rows.append(rendered_row)
            if not rows and keyboard in {"reply", "inline"}:
                keyboard = "none"
            return Screen(
                text=body,
                keyboard=keyboard,
                buttons=rows,
                locale=user.locale,
                theme=user.theme,
                feature=feature,
                return_flow=node.return_flow if isinstance(node, EndNode) else None,
            )
