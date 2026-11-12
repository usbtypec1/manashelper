from dataclasses import asdict
from typing import Any

from aiogram.utils.i18n import gettext as _

from manashelper.modules.gamification.application.queries import AchievementProfile, LeaderboardEntry
from manashelper.platform.i18n.catalog import i18n


def achievement_strings() -> dict[str, tuple[str, str]]:
    # Literal keys keep Babel extraction and all five catalogs authoritative.
    return {
        "night_owl": (_("gamification.night_owl.name"), _("gamification.night_owl.description")),
        "foodie": (_("gamification.foodie.name"), _("gamification.foodie.description")),
        "cafeteria_boss": (_("gamification.cafeteria_boss.name"), _("gamification.cafeteria_boss.description")),
        "formula_one": (_("gamification.formula_one.name"), _("gamification.formula_one.description")),
        "champion": (_("gamification.champion.name"), _("gamification.champion.description")),
        "comeback": (_("gamification.comeback.name"), _("gamification.comeback.description")),
        "fall": (_("gamification.fall.name"), _("gamification.fall.description")),
        "seller": (_("gamification.seller.name"), _("gamification.seller.description")),
        "eldin_balasy": (_("gamification.eldin_balasy.name"), _("gamification.eldin_balasy.description")),
        "thin_ice": (_("gamification.thin_ice.name"), _("gamification.thin_ice.description")),
    }


def ui_strings(locale: str) -> dict[str, str]:
    with i18n.context(), i18n.use_locale(locale):
        return {
            "title": _("menu.achievements"),
            "collection": _("gamification.ui.collection"),
            "leaderboard": _("gamification.ui.leaderboard"),
            "earned": _("gamification.ui.earned"),
            "rank": _("gamification.ui.rank"),
            "unranked": _("gamification.ui.unranked"),
            "locked": _("gamification.ui.locked"),
            "progress": _("gamification.ui.progress"),
            "sourcePending": _("gamification.ui.source_pending"),
            "baselineMissing": _("gamification.ui.baseline_missing"),
            "empty": _("gamification.ui.empty"),
            "you": _("gamification.ui.you"),
            "close": _("gamification.ui.close"),
            "loading": _("gamification.ui.loading"),
            "error": _("gamification.ui.error"),
            "retry": _("gamification.ui.retry"),
            "openTelegram": _("gamification.ui.open_telegram"),
            "subtitle": _("gamification.ui.subtitle"),
            "topTen": _("gamification.ui.top_ten"),
        }


def localize_profile(profile: AchievementProfile, locale: str) -> dict[str, Any]:
    result = asdict(profile)
    with i18n.context(), i18n.use_locale(locale):
        strings = achievement_strings()
        for card in result["achievements"]:
            card["name"], card["description"] = strings[card["key"]]
    result["locale"] = locale
    return result


def localize_leaderboard(entries: tuple[LeaderboardEntry, ...], viewer_id: int, locale: str) -> dict[str, Any]:
    with i18n.context(), i18n.use_locale(locale):
        strings = achievement_strings()
        return {
            "entries": [
                {
                    "full_name": entry.full_name,
                    "score": entry.score,
                    "rank": entry.rank,
                    "is_self": entry.user_id == viewer_id,
                    "achievements": [
                        {
                            "key": award.key,
                            "name": strings[award.key][0],
                            "description": strings[award.key][1],
                            "earned_at": award.earned_at,
                        }
                        for award in entry.achievements
                    ],
                }
                for entry in entries
            ]
        }
