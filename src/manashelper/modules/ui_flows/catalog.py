"""Explicit gettext keys available to version-one scenario authors."""

from collections.abc import Callable

from aiogram.utils.i18n import gettext as _

from manashelper.platform.i18n.catalog import i18n

_CATALOG: dict[str, Callable[[], str]] = {
    "ui_flows.demo.intro": lambda: _("ui_flows.demo.intro"),
    "ui_flows.demo.form": lambda: _("ui_flows.demo.form"),
    "ui_flows.demo.prompt": lambda: _("ui_flows.demo.prompt"),
    "ui_flows.demo.invalid": lambda: _("ui_flows.demo.invalid"),
    "ui_flows.demo.confirm": lambda: _("ui_flows.demo.confirm"),
    "ui_flows.demo.result": lambda: _("ui_flows.demo.result"),
    "ui_flows.completed": lambda: _("ui_flows.completed"),
    "ui_flows.cancelled": lambda: _("ui_flows.cancelled"),
    "common.welcome": lambda: _("common.welcome"),
    "menu.main": lambda: _("menu.main"),
    "menu.study": lambda: _("menu.study"),
    "menu.food": lambda: _("menu.food"),
    "menu.marketplace": lambda: _("menu.marketplace"),
    "menu.settings": lambda: _("menu.settings"),
    "menu.schedule": lambda: _("menu.schedule"),
    "menu.study_week": lambda: _("menu.study_week"),
    "menu.eders": lambda: _("menu.eders"),
    "menu.eders_materials": lambda: _("menu.eders_materials"),
    "menu.attendance": lambda: _("menu.attendance"),
    "menu.grades": lambda: _("menu.grades"),
    "common.back_to_menu": lambda: _("common.back_to_menu"),
    "common.cancel": lambda: _("common.cancel"),
    "student_questions.intro": lambda: _("student_questions.intro"),
    "student_questions.course_prompt": lambda: _("student_questions.course_prompt"),
    "student_questions.preparatory": lambda: _("student_questions.preparatory"),
    "student_questions.year_1": lambda: _("student_questions.year_1"),
    "student_questions.year_2": lambda: _("student_questions.year_2"),
    "student_questions.year_3": lambda: _("student_questions.year_3"),
    "student_questions.year_4": lambda: _("student_questions.year_4"),
    "student_questions.year_5": lambda: _("student_questions.year_5"),
    "student_questions.not_student": lambda: _("student_questions.not_student"),
    "student_questions.already_completed": lambda: _("student_questions.already_completed"),
    "student_questions.fill_again": lambda: _("student_questions.fill_again"),
    "student_questions.cancelled": lambda: _("student_questions.cancelled"),
    "student_questions.search_prompt": lambda: _("student_questions.search_prompt"),
    "student_questions.questions_prompt": lambda: _("student_questions.questions_prompt"),
    "student_questions.found_prompt": lambda: _("student_questions.found_prompt"),
    "student_questions.sources_prompt": lambda: _("student_questions.sources_prompt"),
    "student_questions.beta_prompt": lambda: _("student_questions.beta_prompt"),
    "student_questions.invalid_text": lambda: _("student_questions.invalid_text"),
    "student_questions.yes": lambda: _("student_questions.yes"),
    "student_questions.no": lambda: _("student_questions.no"),
    "student_questions.thanks": lambda: _("student_questions.thanks"),
    "student_questions.beta_follow_up": lambda: _("student_questions.beta_follow_up"),
}
CATALOG_KEYS = frozenset(_CATALOG)


def get_catalog_texts() -> dict[str, str]:
    """Resolve inside the current recipient locale/theme; literal calls remain extractable."""
    return {key: i18n.gettext(key) for key in i18n.current_catalog.keys}
