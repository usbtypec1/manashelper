from aiogram.enums import ParseMode
from aiogram.types import InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaPhoto, InputMediaVideo
from aiogram.utils.i18n import gettext as _

from manashelper.services.daily_menu import DailyMenuModel
from manashelper.services.timetable_formatter import weekday_full

MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaLivePhoto | InputMediaPhoto | InputMediaVideo


def format_daily_menu(daily_menu: DailyMenuModel) -> str:
    weekday_name = weekday_full(daily_menu.date.isoweekday())
    lines = [
        _("food.menu_header").format(weekday=weekday_name, date=daily_menu.date.strftime("%d.%m.%Y")),
        "",
    ]

    total_calories = 0
    for index, dish in enumerate(daily_menu.dishes, start=1):
        lines.append(_("food.dish").format(index=index, name=dish.name, calories=dish.calories))
        total_calories += dish.calories

    lines.append("")
    lines.append(_("food.total_calories").format(calories=total_calories))
    if daily_menu.ratings_count:
        lines.append(
            _("food.rating").format(average=f"{daily_menu.average_rating:.1f}", count=daily_menu.ratings_count)
        )
    else:
        lines.append(_("food.no_ratings"))
    lines.append(_("food.views").format(count=daily_menu.views_count))
    return "\n".join(lines)


def format_not_found(skip_days: int) -> str:
    if skip_days == 0:
        return _("food.today_unpublished")
    return _("food.menu_unpublished")


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
