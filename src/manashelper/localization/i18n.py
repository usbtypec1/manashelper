from pathlib import Path

from aiogram.utils.i18n import I18n

from manashelper.localization.locale import DEFAULT_LOCALE

# Catalogs live at src/manashelper/locales/<locale>/LC_MESSAGES/messages.{po,mo} — see
# babel.cfg and CLAUDE.md for the extract/init/compile workflow. English has no catalog at
# all: source strings are written in English, and gettext already falls back to the raw
# msgid when a locale (or a specific message within it) isn't found.
i18n = I18n(path=Path(__file__).resolve().parent.parent / "locales", default_locale=DEFAULT_LOCALE.value)
