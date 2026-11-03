"""Pure text-publication validation shared by the catalog and Telegram renderer."""

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.schema import template_parameters
from ui_flows.domain.texts import TextDocument

LOCALES = ("en", "ru", "ky", "tr", "zh")
_PLURAL_FORMS = {
    "en": frozenset({"one", "other"}),
    "ru": frozenset({"one", "few", "many"}),
    "ky": frozenset({"one", "other"}),
    "tr": frozenset({"other"}),
    "zh": frozenset({"other"}),
}
_HREF = re.compile(r"(\bhref\s*=\s*)([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)


class TextValidationError(ValueError):
    pass


def text_units(text: str) -> int:
    try:
        return len(text.encode("utf-16-le")) // 2
    except UnicodeError as error:
        raise TextValidationError("Invalid Unicode text") from error


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
            raise TextValidationError("Unsupported Telegram HTML tag")
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise TextValidationError("Repeated HTML attribute")
        if tag == "a":
            try:
                scheme = urlsplit(attributes.get("href") or "").scheme
            except ValueError as error:
                raise TextValidationError("Unsupported Telegram link") from error
            if set(attributes) != {"href"} or scheme not in {"http", "https", "tg"}:
                raise TextValidationError("Unsupported Telegram link")
        elif attributes:
            raise TextValidationError("Unsupported Telegram HTML attribute")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack.pop() != tag:
            raise TextValidationError("Unbalanced Telegram HTML")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raise TextValidationError("Self-closing tags are not supported")

    def handle_comment(self, data: str) -> None:
        raise TextValidationError("HTML comments are not supported")

    def handle_data(self, data: str) -> None:
        if "<" in data:
            raise TextValidationError("Unescaped HTML delimiter")
        self.length += text_units(data)

    def handle_entityref(self, name: str) -> None:
        if name not in {"lt", "gt", "amp", "quot"}:
            raise TextValidationError("Unsupported Telegram HTML entity")
        self.length += 1

    def handle_charref(self, name: str) -> None:
        try:
            value = int(name[1:], 16) if name.startswith(("x", "X")) else int(name)
            self.length += text_units(chr(value))
        except (ValueError, UnicodeError):
            raise TextValidationError("Invalid Unicode entity") from None

    def handle_decl(self, decl: str) -> None:
        raise TextValidationError("HTML declarations are not supported")

    def handle_pi(self, data: str) -> None:
        raise TextValidationError("HTML instructions are not supported")


def validate_message(text: str, *, max_length: int = 4096) -> None:
    parser = _TelegramHtml()
    parser.feed(text)
    parser.close()
    if parser.stack or not 1 <= parser.length <= max_length:
        raise TextValidationError("Invalid Telegram message length or markup")


class _PlainText(HTMLParser):
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raise TextValidationError("Plain text cannot contain markup")

    def handle_endtag(self, tag: str) -> None:
        raise TextValidationError("Plain text cannot contain markup")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raise TextValidationError("Plain text cannot contain markup")

    def handle_comment(self, data: str) -> None:
        raise TextValidationError("Plain text cannot contain markup")

    def handle_decl(self, decl: str) -> None:
        raise TextValidationError("Plain text cannot contain markup")

    def handle_pi(self, data: str) -> None:
        raise TextValidationError("Plain text cannot contain markup")


def expected_forms(locale: str, plural: bool) -> frozenset[str]:
    return _PLURAL_FORMS.get(locale, _PLURAL_FORMS["en"]) if plural else frozenset({"other"})


def _validation_sample(template: str, parameters: tuple[str, ...]) -> str:
    def href_sample(match: re.Match[str]) -> str:
        href = match[3]
        # A complete URL comes from a trusted binding at rendering time. Use a
        # fixed harmless URL for publication checks, never evaluate its contents.
        if href.startswith("{") and href.endswith("}") and len(template_parameters(href)) == 1:
            href = "https://example.invalid/"
        return match[1] + match[2] + href + match[2]

    return _HREF.sub(href_sample, template).format_map(dict.fromkeys(parameters, "value"))


def validate_text_document(document: TextDocument) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    identities: set[str] = set()

    def issue(code: str, path: str, message: str) -> None:
        issues.append(ContractIssue(code=code, path=path, message=message))

    for index, entry in enumerate(document.entries):
        base = f"/entries/{index}"
        for field, identity in (("key", entry.key), ("plural_key", entry.plural_key)):
            if identity is None:
                continue
            if identity in identities:
                issue("duplicate_text_key", f"{base}/{field}", "Text keys and plural aliases must be unique")
            identities.add(identity)
        if len(set(entry.parameters)) != len(entry.parameters):
            issue("duplicate_text_parameter", base + "/parameters", "Parameter names must be unique")
        seen: set[tuple[str, str, str]] = set()
        forms: dict[tuple[str, str], set[str]] = {}
        for variant_index, variant in enumerate(entry.variants):
            path = f"{base}/variants/{variant_index}"
            variant_identity = (variant.locale, variant.theme, variant.form)
            if variant_identity in seen:
                issue("duplicate_text_variant", path, "Locale, theme and form must identify one variant")
            seen.add(variant_identity)
            forms.setdefault((variant.locale, variant.theme), set()).add(variant.form)
            try:
                if template_parameters(variant.text) != set(entry.parameters):
                    raise TextValidationError("Template parameters do not match the entry contract")
                sample = _validation_sample(variant.text, entry.parameters)
                if entry.content_type == "html":
                    validate_message(sample)
                else:
                    parser = _PlainText()
                    parser.feed(sample)
                    parser.close()
                    limit = 64 if entry.content_type == "label" else 4096
                    if not sample.strip() or not 1 <= text_units(sample) <= limit:
                        raise TextValidationError("Text exceeds display limits")
            except (ValueError, UnicodeError):
                issue("invalid_text_template", path + "/text", "Check parameters, markup and display limits")
        for locale in LOCALES:
            if (locale, "basic") not in forms:
                issue("missing_text_locale", base + "/variants", "Every supported locale needs basic text")
        for (locale, _theme), present in forms.items():
            if present != expected_forms(locale, entry.plural_key is not None):
                issue("invalid_text_forms", base + "/variants", "Plural forms do not match the locale contract")
    return issues
