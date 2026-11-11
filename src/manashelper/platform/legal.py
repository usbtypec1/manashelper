"""Shared terms content for Telegram and the public Mini App page."""

from aiogram.utils.i18n import gettext as _

TERMS_UPDATED = "2026-11-11"
TERMS_SOURCES = {
    "obis": (
        "https://obistest.manas.edu.kg/site/login",
        "https://obistest.manas.edu.kg/vs-ders/taken-lessons",
        "https://obistest.manas.edu.kg/vs-ders/taken-grades",
        "https://obistest.manas.edu.kg/vs-ders/transkript-detailed",
        "https://obistest.manas.edu.kg/site/eders",
    ),
    "eders": (
        "https://eders.manas.edu.kg/login/index.php",
        "https://eders.manas.edu.kg/auth/userkey/login.php",
        "https://eders.manas.edu.kg/my/courses.php",
        "https://eders.manas.edu.kg/user/profile.php",
        "https://eders.manas.edu.kg/lib/ajax/service.php",
        "https://eders.manas.edu.kg/course/view.php?id={course_id}",
        "https://eders.manas.edu.kg/mod/assign/view.php?id={activity_id}",
        "https://eders.manas.edu.kg/mod/quiz/view.php?id={activity_id}",
    ),
}


def terms_ui_strings() -> dict[str, str]:
    # Keep the public page's UI keys visible to Babel extraction too.
    return {
        "title": _("terms.title"),
        "language": _("terms.language"),
        "updated_label": _("terms.updated_label"),
        "back": _("terms.back"),
    }


def terms_sections() -> tuple[tuple[str, str, str], ...]:
    return (
        ("services", _("terms.services.title"), _("terms.services.body")),
        ("data", _("terms.data.title"), _("terms.data.body")),
        ("obis", _("terms.obis.title"), _("terms.obis.body")),
        ("eders", _("terms.eders.title"), _("terms.eders.body")),
        ("sync", _("terms.sync.title"), _("terms.sync.body")),
        ("ranking", _("terms.ranking.title"), _("terms.ranking.body")),
        ("controls", _("terms.controls.title"), _("terms.controls.body")),
        ("limits", _("terms.limits.title"), _("terms.limits.body")),
    )
