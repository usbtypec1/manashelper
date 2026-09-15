from aiogram.enums import ParseMode
from aiogram.types import InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaPhoto, InputMediaVideo
from aiogram.utils.i18n import gettext as _

from manashelper.services.daily_menu import DailyMenuModel
from manashelper.services.timetable_formatter import weekday_full

MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaLivePhoto | InputMediaPhoto | InputMediaVideo


def format_daily_menu(daily_menu: DailyMenuModel) -> str:
    weekday_name = weekday_full(daily_menu.date.isoweekday())
    lines = [
        _("🍽 <b>Menu for {weekday}, {date}</b>").format(
            weekday=weekday_name, date=daily_menu.date.strftime("%d.%m.%Y")
        ),
        "",
    ]

    total_calories = 0
    for index, dish in enumerate(daily_menu.dishes, start=1):
        lines.append(
            _("{index}. {name} — <b>{calories}</b> kcal").format(index=index, name=dish.name, calories=dish.calories)
        )
        total_calories += dish.calories

    lines.append("")
    lines.append(_("🔥 Total: <b>{calories}</b> kcal").format(calories=total_calories))
    if daily_menu.ratings_count:
        lines.append(
            _("⭐ Rating: <b>{average}</b> ({count})").format(
                average=f"{daily_menu.average_rating:.1f}", count=daily_menu.ratings_count
            )
        )
    else:
        lines.append(_("⭐ No ratings yet"))
    lines.append(_("👁 Views: {count}").format(count=daily_menu.views_count))
    return "\n".join(lines)


def format_not_found(skip_days: int) -> str:
    if skip_days == 0:
        return _("😔 Today's menu hasn't been published yet.")
    return _("😔 The menu for that day hasn't been published yet.")


def build_photos(caption: str, daily_menu: DailyMenuModel) -> list[MediaGroupItem]:
    photos: list[MediaGroupItem] = [
        InputMediaPhoto(
            media=dish.photo_url,
            caption=caption if index == 0 else None,
            parse_mode=ParseMode.HTML if index == 0 else None,
        )
        for index, dish in enumerate(daily_menu.dishes)
    ]
    return photos
