from manashelper.localization.theme import Theme

# Only bot navigation is decorated; user content, status symbols and data stay intact.
_HALLOWEEN_ICONS = {
    "common.welcome": ("", "🎃"),
    "menu.food": ("🍉", "🎃"),
    "menu.schedule": ("📅", "🕸️"),
    "menu.attendance": ("📋", "👻"),
    "menu.grades": ("💯", "🦇"),
    "menu.eders": ("", "⏳"),
    "menu.eders_materials": ("", "📜"),
    "menu.study_week": ("", "🌙"),
    "menu.marketplace": ("🛒", "🍬"),
    "menu.settings": ("⚙️", "🕯️"),
    "menu.main": ("", "🎃"),
    "settings.title": ("", "🕯️"),
    "settings.notifications": ("🔔", "🦇"),
    "settings.my_lessons": ("📚", "📜"),
    "settings.obis_credentials": ("🔑", "🗝️"),
    "settings.phone_numbers": ("📱", "☎️"),
    "settings.language": ("🌐", "🌙"),
    "settings.theme": ("🎨", "🎃"),
    "settings.feedback": ("💬", "👻"),
}


def decorate_translation(key: str, text: str, theme: Theme) -> str:
    if theme == Theme.HALLOWEEN and key in _HALLOWEEN_ICONS:
        original, replacement = _HALLOWEEN_ICONS[key]
        if original:
            text = text.removeprefix(f"{original} ")
        return f"{replacement} {text}"
    return text
