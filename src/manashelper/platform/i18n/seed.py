"""Explicit PO-to-DB bootstrap import; delivery never reads these source files.

The `halloween.*` keys remain import-source entries for compatibility. Canonical
food keys already contain their resolved Halloween variants in the document.
"""

from functools import partial
from pathlib import Path
from typing import Literal

from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po

from manashelper.localization.theme import Theme
from manashelper.platform.i18n.themes import decorate_translation, halloween_translation
from ui_flows.domain.schema import LocaleCode, template_parameters
from ui_flows.domain.texts import TextDocument, TextEntry, TextVariant

LOCALES: tuple[LocaleCode, ...] = ("en", "ru", "ky", "tr", "zh")
PluralCategory = Literal["one", "few", "many", "other"]
_PLURAL_FORMS: dict[LocaleCode, tuple[PluralCategory, ...]] = {
    "en": ("one", "other"),
    "ru": ("one", "few", "many"),
    "ky": ("one", "other"),
    "tr": ("other",),
    "zh": ("other",),
}

# Legacy reply-keyboard matching accepts the labels originally shown in either
# theme. This is a fixed compatibility contract, not a runtime source-code scan.
REPLY_KEYS = frozenset(
    {
        "ads.my_ads",
        "ads.post",
        "common.back_to_menu",
        "menu.attendance",
        "menu.eders",
        "menu.eders_materials",
        "menu.food",
        "menu.grades",
        "menu.marketplace",
        "menu.schedule",
        "menu.settings",
        "menu.study",
        "menu.study_week",
    }
)
_LABEL_KEYS = REPLY_KEYS | frozenset(
    {
        "ads.add_comment",
        "ads.approve",
        "ads.confirm_delete",
        "ads.no_comment",
        "ads.no_expiration",
        "ads.reject",
        "ads.submit_review",
        "broadcast.edit_buttons",
        "broadcast.without_buttons",
        "common.back",
        "common.cancel",
        "common.delete",
        "common.disable_all",
        "common.done",
        "common.duration.days_1",
        "common.duration.days_7",
        "common.duration.hours_24",
        "common.duration.hours_3",
        "common.duration.hours_6",
        "common.duration.minutes_15",
        "common.duration.minutes_45",
        "common.enable_all",
        "common.off",
        "common.send",
        "common.skip",
        "eders.filter_all",
        "eders.filter_available",
        "eders.filter_awaiting",
        "eders.filter_materials",
        "eders.filter_new_materials",
        "eders.filter_not_submitted",
        "eders.filter_today",
        "eders.filter_unknown",
        "eders.filter_week",
        "eders.setting_archived",
        "eders.setting_changes",
        "eders.setting_day",
        "eders.setting_materials",
        "eders.setting_openings",
        "eders.setting_two_hours",
        "food.auto_delete_settings",
        "food.day_after_tomorrow",
        "food.dinner",
        "food.lunch",
        "food.open_menu",
        "food.today",
        "food.tomorrow",
        "notifications.configure",
        "notifications.eders",
        "notifications.exam_grades",
        "notifications.lesson_skips",
        "notifications.schedule_changes",
        "obis.accept_terms",
        "obis.clear_credentials",
        "obis.confirm_clear",
        "obis.enter_credentials",
        "obis.terms",
        "obis.update_credentials",
        "phone.add",
        "phone.share",
        "schedule.choose_courses",
        "schedule.course_year",
        "schedule.my_schedule",
        "schedule.search_subject",
        "settings.feedback",
        "settings.language",
        "settings.my_lessons",
        "settings.notifications",
        "settings.obis_credentials",
        "settings.phone_numbers",
        "settings.theme",
        "student_questions.fill_again",
        "student_questions.no",
        "student_questions.not_student",
        "student_questions.preparatory",
        "student_questions.year_1",
        "student_questions.year_2",
        "student_questions.year_3",
        "student_questions.year_4",
        "student_questions.year_5",
        "student_questions.yes",
        "theme.basic",
        "theme.halloween",
        "ui_flows.open_editor",
    }
)
_OWNER_BY_PREFIX = {
    "ads": "advertisements",
    "phone": "users",
    "language": "users",
    "theme": "users",
    "food": "food_menu",
    "halloween": "food_menu",
    "common": "telegram",
    "menu": "telegram",
    "settings": "telegram",
    "commands": "telegram",
    "data": "telegram",
    "weekday": "localization",
}


def _strings(message: Message) -> tuple[str, ...]:
    value = message.string
    if isinstance(value, str):
        return (value,)
    if value is None:
        raise ValueError("An imported message must have a translation")
    return tuple(value)


def _message(catalog: Catalog, key: str) -> Message:
    message = catalog.get(key)
    if message is None or "fuzzy" in message.flags or any(not value for value in _strings(message)):
        raise ValueError(f"Missing or unfinished source translation: {key}")
    return message


def _translation(catalog: Catalog, key: str) -> str:
    return _strings(_message(catalog, key))[0]


def import_document(root: Path | None = None) -> TextDocument:
    """Read all five authored PO catalogs only during explicit import/bootstrap."""
    source = root or Path(__file__).resolve().parents[2] / "locales"
    catalogs: dict[LocaleCode, Catalog] = {}
    for locale in LOCALES:
        with (source / locale / "LC_MESSAGES/messages.po").open(encoding="utf-8") as stream:
            catalogs[locale] = read_po(stream, locale=locale, abort_invalid=True)
    entries = []
    for english in sorted(
        (item for item in catalogs["en"] if item.id),
        key=lambda item: item.id if isinstance(item.id, str) else item.id[0],
    ):
        key = english.id if isinstance(english.id, str) else english.id[0]
        if key.startswith(("ui_flows.editor.", "ui_flows.web.")):
            continue
        plural_key = None if isinstance(english.id, str) else english.id[1]
        base = _strings(english)[0]
        parameters = tuple(sorted(template_parameters(base)))
        content_type: Literal["label", "html", "plain"] = (
            "label" if key in _LABEL_KEYS else ("html" if "<" in base else "plain")
        )
        variants = []
        for locale in LOCALES:
            forms: tuple[PluralCategory, ...] = _PLURAL_FORMS[locale] if plural_key else ("other",)
            values = _strings(_message(catalogs[locale], key))
            if len(values) != len(forms):
                raise ValueError(f"Source plural forms do not match the supported locale: {locale}/{key}")
            for form, value in zip(forms, values, strict=True):
                if template_parameters(value) != set(parameters):
                    raise ValueError(f"Source translation parameters differ: {locale}/{key}")
                variants.append(TextVariant(locale=locale, theme="basic", form=form, text=value))
                themed = halloween_translation(key, partial(_translation, catalogs[locale]))
                if themed is None:
                    themed = decorate_translation(key, value, Theme.HALLOWEEN)
                variants.append(TextVariant(locale=locale, theme="halloween", form=form, text=themed))
        prefix = key.split(".", 1)[0]
        entries.append(
            TextEntry(
                key=key,
                owner=_OWNER_BY_PREFIX.get(prefix, prefix),
                parameters=parameters,
                content_type=content_type,
                plural_key=plural_key,
                variants=tuple(variants),
            )
        )
    return TextDocument(schema_version=1, entries=tuple(entries))
