from collections.abc import Callable


def gta_vi_translation(key: str, _: Callable[[str], str]) -> str | None:
    match key:
        case "common.welcome":
            return _("gta_vi.common.welcome")
        case "menu.food" | "miniapp.ui.food":
            return _("gta_vi.menu.food")
        case "menu.study":
            return _("gta_vi.menu.study")
        case "menu.schedule":
            return _("gta_vi.menu.schedule")
        case "menu.marketplace":
            return _("gta_vi.menu.marketplace")
        case "menu.settings":
            return _("gta_vi.menu.settings")
        case "menu.achievements" | "menu.achievements_button" | "miniapp.ui.achievements":
            return _("gta_vi.menu.achievements")
        case "theme.selected":
            return _("gta_vi.theme.selected")
        case "food.day_selection_title":
            return _("gta_vi.food.day_selection_title")
        case "food.choose_day":
            return _("gta_vi.food.choose_day")
        case "food.menu_header" | "food.rich_menu_header":
            return _("gta_vi.food.menu_header")
        case "food.dish":
            return _("gta_vi.food.dish")
        case "food.rich_dish":
            return _("gta_vi.food.rich_dish")
        case "food.total_calories" | "food.rich_total_calories":
            return _("gta_vi.food.total_calories")
        case "food.rating" | "food.rich_rating":
            return _("gta_vi.food.rating")
        case "food.rating_thanks":
            return _("gta_vi.food.rating_thanks")
        case "food.open_menu":
            return _("gta_vi.food.open_menu")
        case "food.enjoy_meal":
            return _("gta_vi.food.enjoy_meal")
        case "schedule.no_classes":
            return _("gta_vi.schedule.no_classes")
        case "schedule.changes_header":
            return _("gta_vi.schedule.changes_header")
        case "obis.new_grade":
            return _("gta_vi.obis.new_grade")
        case "obis.skip_recorded":
            return _("gta_vi.obis.skip_recorded")
        case "eders.reminder_day":
            return _("gta_vi.eders.reminder_day")
        case "eders.reminder_two_hours":
            return _("gta_vi.eders.reminder_two_hours")
        case "eders.opened_notification":
            return _("gta_vi.eders.opened_notification")
        case "eders.changed_notification":
            return _("gta_vi.eders.changed_notification")
        case "eders.material_new":
            return _("gta_vi.eders.material_new")
        case "eders.material_changed":
            return _("gta_vi.eders.material_changed")
        case "miniapp.ui.title" | "settings.title":
            return _("gta_vi.miniapp.ui.title")
        case "miniapp.ui.saved":
            return _("gta_vi.miniapp.ui.saved")
        case "miniapp.ui.free_time":
            return _("gta_vi.miniapp.ui.free_time")
        case "gamification.ui.collection":
            return _("gta_vi.gamification.ui.collection")
        case "gamification.ui.leaderboard":
            return _("gta_vi.gamification.ui.leaderboard")
    return None
