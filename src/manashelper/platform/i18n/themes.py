from collections.abc import Callable

from manashelper.localization.theme import Theme

# Decorate interface text before dynamic data is interpolated; keep user content and status values intact.
_HALLOWEEN_ICONS = {
    "common.welcome": ("", "🎃"),
    "menu.food": ("🍉", "🎃"),
    "menu.study": ("📚", "🦉"),
    "menu.schedule": ("📅", "🕸️"),
    "menu.attendance": ("📋", "👻"),
    "menu.grades": ("💯", "🦇"),
    "menu.eders": ("💻", "⏳"),
    "menu.eders_materials": ("📚", "📜"),
    "menu.study_week": ("🗓️", "🌙"),
    "menu.marketplace": ("🛒", "🍬"),
    "menu.settings": ("⚙️", "🕯️"),
    "menu.main": ("🏠", "🎃"),
    "settings.title": ("", "🕯️"),
    "settings.notifications": ("🔔", "🦇"),
    "settings.my_lessons": ("📚", "📜"),
    "settings.obis_credentials": ("🔑", "🗝️"),
    "settings.language": ("🌐", "🌙"),
    "settings.theme": ("🎨", "🎃"),
    "settings.feedback": ("💬", "👻"),
    "food.today": ("📅", "🎃"),
    "food.tomorrow": ("📆", "🌙"),
    "food.day_after_tomorrow": ("🗓", "🦇"),
    "food.views": ("👁", "👀"),
    "food.lunch": ("🍽️", "🎃"),
    "food.dinner": ("🌙", "🌙"),
    "food.notification_settings": ("🍽", "🦇"),
    "notifications.title": ("", "🦇"),
    "notifications.configure": ("⚙️", "🕯️"),
    "notifications.schedule_changes": ("", "🕸️"),
    "notifications.exam_grades": ("", "🍬"),
    "notifications.lesson_skips": ("", "👻"),
    "notifications.eders": ("", "📜"),
    "schedule.my_schedule": ("📅", "🕸️"),
    "schedule.search_subject": ("🔎", "🕯️"),
    "schedule.choose_courses": ("📚", "📜"),
    "schedule.faculties": ("", "🏰"),
    "schedule.departments": ("", "📜"),
    "schedule.courses": ("", "🦇"),
    "schedule.day_header": ("📅", "🌙"),
    "schedule.changes_header": ("🔔", "🦇"),
    "schedule.search_prompt": ("", "🕯️"),
    "schedule.results": ("🔎", "🕯️"),
    "schedule.results_page": ("🔎", "🕯️"),
    "obis.settings": ("", "🗝️"),
    "obis.loading_grades": ("📚", "🍬"),
    "obis.loading_attendance": ("📋", "👻"),
    "obis.page_indicator": ("", "🦇"),
    "obis.no_grades": ("", "🕯️"),
    "obis.no_subjects": ("", "📜"),
    "obis.new_grade": ("🔔", "🍬"),
    "obis.skip_recorded": ("", "👻"),
    "eders.page": ("", "📜"),
    "eders.week_header": ("", "🌙"),
    "eders.week_empty_day": ("", "🕯️"),
    "eders.reminder_day": ("", "🦇"),
    "eders.reminder_two_hours": ("", "🕯️"),
    "eders.opened_notification": ("", "🕸️"),
    "eders.changed_notification": ("", "🦇"),
    "eders.material_new": ("", "📜"),
    "eders.material_changed": ("", "🕸️"),
    "language.prompt": ("🌐", "🌙"),
    "feedback.message_prompt": ("💬", "👻"),
    "data.preparing": ("", "🕯️"),
}


def decorate_translation(key: str, text: str, theme: Theme) -> str:
    # Keep factual fragments (dates, grades, submission states, achievement rules)
    # readable; theme all other interface copy, including validation and empty states.
    if (
        theme == Theme.PICKME
        and key.startswith(
            (
                "common.",
                "menu.",
                "settings.",
                "theme.",
                "food.",
                "schedule.",
                "obis.",
                "eders.",
                "notifications.",
                "ads.",
                "feedback.",
                "broadcast.",
                "language.prompt",
                "language.selected",
                "data.",
                "miniapp.ui.",
                "gamification.ui.",
                "gamification.open_prompt",
                "gamification.view_all",
                "gamification.award_notification",
                "gamification.unavailable",
            )
        )
        and key
        not in {
            "theme.basic",
            "theme.halloween",
            "theme.pickme",
            "schedule.course_year",
            "schedule.search_course",
            "schedule.search_weekday",
            "schedule.change_updated",
            "schedule.change_added",
            "schedule.change_cancelled",
            "obis.subject",
            "obis.exam",
            "obis.theory",
            "obis.practice",
            "obis.theory_lower",
            "obis.practice_lower",
            "obis.missed_percentage",
            "obis.skips_left.one",
            "obis.remaining_skips.one",
            "eders.unknown",
            "eders.date_conflict",
            "eders.date_unverified",
            "eders.not_submitted",
            "eders.draft",
            "eders.submitted",
            "eders.in_progress",
            "eders.not_graded",
            "eders.graded",
            "eders.opens",
            "eders.closes",
            "eders.submission",
            "eders.grading",
            "eders.previous_deadline",
            "eders.week_opens",
            "eders.week_due",
            "eders.marked_done",
            "ads.status_pending",
            "ads.status_published",
            "ads.status_rejected",
            "ads.price",
            "ads.valid_until",
            "ads.reason",
            "ads.rejection_reason",
            "miniapp.ui.course_number",
            "miniapp.ui.monday",
            "miniapp.ui.tuesday",
            "miniapp.ui.wednesday",
            "miniapp.ui.thursday",
            "miniapp.ui.friday",
            "miniapp.ui.saturday",
            "miniapp.ui.sunday",
        }
    ):
        return f"{text} 🎀"
    if theme == Theme.HALLOWEEN and key in _HALLOWEEN_ICONS:
        original, replacement = _HALLOWEEN_ICONS[key]
        if original:
            text = text.removeprefix(f"{original} ")
        return f"{replacement} {text}"
    return text


def halloween_translation(key: str, _: Callable[[str], str]) -> str | None:
    match key:
        case "food.day_selection_title":
            return _("halloween.food_title")
        case "food.menu_header" | "food.rich_menu_header":
            return _("halloween.food_menu_header")
        case "food.dish" | "food.rich_dish":
            return _("halloween.food_dish")
        case "food.total_calories" | "food.rich_total_calories":
            return _("halloween.food_total_calories")
        case "food.rating" | "food.rich_rating":
            return _("halloween.food_rating")
        case "food.no_ratings":
            return _("halloween.food_no_ratings")
        case "food.rate_prompt":
            return _("halloween.food_rate_prompt")
        case "food.rating_thanks":
            return _("halloween.food_rating_thanks")
        case "food.enjoy_meal":
            return _("halloween.food_enjoy_meal")
        case "food.choose_day":
            return _("halloween.food_choose_day")
        case "food.open_menu":
            return _("halloween.food_open_menu")
        case "food.today_unpublished":
            return _("halloween.food_today_unpublished")
        case "food.menu_unpublished":
            return _("halloween.food_menu_unpublished")
        case "food.no_available_menus":
            return _("halloween.food_no_available_menus")
    return None
