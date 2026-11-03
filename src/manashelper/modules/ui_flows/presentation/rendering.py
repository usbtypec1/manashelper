from typing import Literal

from aiogram.utils.i18n import gettext as _

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.ui_flows.catalog import get_catalog_texts
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from ui_flows.application.interpreter import EvaluationContext
from ui_flows.application.texts import TextValidationError, text_units
from ui_flows.application.texts import validate_message as validate_text_message
from ui_flows.application.validation import accepts_scalar, reference_type, sample_value
from ui_flows.domain.contracts import ActionSnapshot
from ui_flows.domain.delivery import Screen, ScreenButton, ScreenMedia
from ui_flows.domain.schema import (
    ActionNode,
    Button,
    CatalogText,
    EndNode,
    FlowDocument,
    InputNode,
    MenuNode,
    ReturnNode,
    Text,
    TransitionButton,
    template_parameters,
)
from ui_flows.domain.state import ExecutionResult, RuntimeUser
from ui_flows.domain.texts import resolve_inline
from ui_flows.errors import FlowExecutionError
from ui_flows.ports.texts import TextCatalog


class InvalidScreenError(FlowExecutionError):
    node_id: str | None = None
    path: str = "/document/nodes"


def _units(text: str) -> int:
    try:
        return text_units(text)
    except TextValidationError as error:
        raise InvalidScreenError(str(error)) from error


def validate_message(text: str, *, max_length: int = 4096) -> None:
    try:
        validate_text_message(text, max_length=max_length)
    except TextValidationError as error:
        raise InvalidScreenError(str(error)) from error


def _render(text: Text, context: EvaluationContext, catalog: dict[str, str], user: RuntimeUser, *, html: bool) -> str:
    if isinstance(text, CatalogText):
        template = catalog.get(text.key)
        if template is None:
            raise InvalidScreenError("Unknown catalog template")
        entry = i18n.current_catalog.entry(text.key)
        if entry.plural_key is not None:
            quantity = context.resolve(text.parameters["count"]) if "count" in text.parameters else None
            if type(quantity) is not int:
                raise InvalidScreenError("Plural text requires an integer count")
            template = i18n.current_catalog.gettext(text.key, user.locale, user.theme, quantity)
    else:
        template = resolve_inline(text.translations, text.themes, user.locale, user.theme)
    if template_parameters(template) != text.parameters.keys():
        raise InvalidScreenError("Template parameters do not match the bindings")
    parameters = {}
    for name, binding in text.parameters.items():
        value = context.resolve(binding)
        if isinstance(value, (dict, list)):
            raise InvalidScreenError("Text parameters require scalar values")
        if isinstance(value, bool):
            formatted = _("student_questions.yes") if value else _("student_questions.no")
        else:
            formatted = "" if value is None else str(value)
        parameters[name] = escape_html(formatted) if html else formatted
    return template.format_map(parameters)


def validate_reply_label(label: str) -> None:
    if label.startswith("/"):
        raise InvalidScreenError("Reply button labels must not be commands")


class FlowRenderer:
    def validate_document(
        self, document: FlowDocument, capabilities: dict[str, str | bool | int | float | None]
    ) -> None:
        data = {name: sample_value(field) for name, field in document.fields.items()}
        for locale in Locale:
            for theme in Theme:
                user = RuntimeUser(1, 1, locale.value, theme.value)
                with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
                    catalog = get_catalog_texts()
                    context = EvaluationContext(document, data, user, capabilities)
                    for index, node in enumerate(document.nodes):
                        if isinstance(node, ActionNode):
                            for text in node.waiting_text:
                                validate_message(_render(text, context, catalog, user, html=True))
                            continue
                        if not isinstance(node, (MenuNode, InputNode, EndNode, ReturnNode)):
                            continue
                        try:
                            body = "\n\n".join(_render(text, context, catalog, user, html=True) for text in node.text)
                            if body:
                                validate_message(body)
                            if isinstance(node, InputNode):
                                validate_message(_render(node.error, context, catalog, user, html=True) + "\n\n" + body)
                            if isinstance(node, (MenuNode, InputNode)):
                                for text in node.messages:
                                    validate_message(_render(text, context, catalog, user, html=True))
                                unconditional_labels = set()
                                for row in node.buttons:
                                    for button in row:
                                        label = _render(button.label, context, catalog, user, html=False)
                                        if not label.strip() or _units(label) > 64:
                                            raise InvalidScreenError("Button label exceeds editor limits")
                                        if isinstance(node, MenuNode) and node.keyboard == "reply":
                                            validate_reply_label(label)
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
        text_catalog: TextCatalog | None = None,
    ) -> Screen:
        with (
            i18n.context(),
            i18n.use_catalog(text_catalog or i18n.current_catalog),
            i18n.use_locale(user.locale),
            i18n.use_theme(Theme(user.theme)),
        ):
            catalog = get_catalog_texts()
            context = EvaluationContext(document, result.state.data, user, capabilities)
            node = result.node
            if isinstance(node, ActionNode) and result.state.status == "waiting_effect":
                body = "\n\n".join(_render(text, context, catalog, user, html=True) for text in node.waiting_text)
                validate_message(body)
                return Screen(
                    text=body,
                    keyboard="none",
                    locale=user.locale,
                    theme=user.theme,
                    text_catalog_release=i18n.current_catalog.release_id,
                )
            if result.outcome == "cancelled" and result.returned_from is None:
                return Screen(
                    text=_("ui_flows.cancelled"),
                    keyboard="main",
                    locale=user.locale,
                    theme=user.theme,
                    text_catalog_release=i18n.current_catalog.release_id,
                )
            if not isinstance(node, (MenuNode, InputNode, EndNode, ReturnNode)):
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
                else ("none" if feature else ("main" if isinstance(node, (EndNode, ReturnNode)) else "inline"))
            )
            rows = []
            labels = set()
            if isinstance(node, (MenuNode, InputNode)):
                groups: list[tuple[list[Button], EvaluationContext, str | None]] = [
                    (row, context, None) for row in node.buttons
                ]
                if isinstance(node, MenuNode):
                    for group_index, group in enumerate(node.repeated):
                        items = context.resolve(group.source)
                        if not isinstance(items, list):
                            raise InvalidScreenError("Repeated action source is not a collection")
                        declaration = reference_type(document, group.source, {})
                        if declaration is None or not accepts_scalar(declaration, items):
                            raise InvalidScreenError("Repeated action source does not match its declared type")
                        for item_index, item in enumerate(items):
                            if not isinstance(item, dict):
                                raise InvalidScreenError("Repeated action items must be objects")
                            item_context = EvaluationContext(
                                document, dict(result.state.data), user, capabilities, item=item
                            )
                            groups.append((group.buttons, item_context, f"r{group_index}_{item_index}"))
                for row, button_context, prefix in groups:
                    rendered_row = []
                    for button_index, button in enumerate(row):
                        if button.when is not None and not button_context.matches(button.when):
                            continue
                        label = _render(button.label, button_context, catalog, user, html=False)
                        if not label.strip() or _units(label) > 64:
                            raise InvalidScreenError("Button label exceeds editor limits")
                        if keyboard == "reply":
                            validate_reply_label(label)
                        if keyboard == "reply" and label in labels:
                            raise InvalidScreenError("Reply button labels are ambiguous")
                        labels.add(label)
                        url = str(button.url) if hasattr(button, "url") else None
                        snapshot = None
                        if prefix is not None and isinstance(button, TransitionButton):
                            assignments = {
                                name: button_context.resolve(value) for name, value in button.assignments.items()
                            }
                            if any(
                                not accepts_scalar(document.fields[name], value) for name, value in assignments.items()
                            ):
                                raise InvalidScreenError("Repeated action values do not match their destination")
                            snapshot = ActionSnapshot(
                                template_id=button.id,
                                target=button.target,
                                assignments=assignments,
                                item=dict(button_context.sources["item"]),
                            )
                        rendered_row.append(
                            ScreenButton(
                                id=f"{prefix}_{button_index}" if prefix is not None else button.id,
                                label=label,
                                url=url,
                                snapshot=snapshot,
                            )
                        )
                    if rendered_row:
                        rows.append(rendered_row)
            if len(rows) > 20 or sum(len(row) for row in rows) > 160:
                raise InvalidScreenError("Rendered action collection exceeds keyboard limits")
            media = []
            messages = []
            if isinstance(node, (MenuNode, InputNode)):
                messages = [_render(text, context, catalog, user, html=True) for text in node.messages]
                if node.message_source is not None:
                    chunks = context.resolve(node.message_source)
                    if (
                        not isinstance(chunks, list)
                        or len(chunks) > 20
                        or any(not isinstance(item, str) for item in chunks)
                    ):
                        raise InvalidScreenError("Message source requires at most twenty text chunks")
                    messages.extend(escape_html(str(item)) for item in chunks)
                if len(messages) > 20:
                    raise InvalidScreenError("Authored and sourced messages exceed twenty chunks")
                for message in messages:
                    validate_message(message)
                if node.media is not None:
                    collection = context.resolve(node.media)
                    if not isinstance(collection, list) or len(collection) > 10:
                        raise InvalidScreenError("Screen media requires at most ten typed items")
                    for item in collection:
                        if not isinstance(item, dict) or item.get("type") not in {"photo", "video"}:
                            raise InvalidScreenError("Screen media item is invalid")
                        file_id = item.get("file_id")
                        if not isinstance(file_id, str):
                            raise InvalidScreenError("Screen media file is invalid")
                        caption = item.get("caption")
                        if caption is not None and not isinstance(caption, str):
                            raise InvalidScreenError("Media caption must be text")
                        rendered_caption = escape_html(caption) if caption else None
                        if rendered_caption is not None:
                            validate_message(rendered_caption, max_length=1024)
                        media.append(
                            ScreenMedia(
                                kind="photo" if item["type"] == "photo" else "video",
                                file_id=file_id,
                                caption=rendered_caption,
                            )
                        )
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
                text_catalog_release=i18n.current_catalog.release_id,
                media=media,
                messages=messages,
                contact_request=_("phone.share")
                if isinstance(node, InputNode) and node.input_type == "contact"
                else None,
            )
