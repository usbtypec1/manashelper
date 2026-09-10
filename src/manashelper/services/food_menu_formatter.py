from aiogram.enums import ParseMode
from aiogram.types import InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaPhoto, InputMediaVideo

from manashelper.services.daily_menu import DailyMenuModel

MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaLivePhoto | InputMediaPhoto | InputMediaVideo

_WEEKDAY_NAMES = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}


def format_daily_menu(daily_menu: DailyMenuModel) -> str:
    weekday_name = _WEEKDAY_NAMES[daily_menu.date.weekday()]
    lines = [f"🍽 <b>Меню на {weekday_name}, {daily_menu.date.strftime('%d.%m.%Y')}</b>", ""]

    total_calories = 0
    for index, dish in enumerate(daily_menu.dishes, start=1):
        lines.append(f"{index}. {dish.name} — <b>{dish.calories}</b> ккал")
        total_calories += dish.calories

    lines.append("")
    lines.append(f"🔥 Итого: <b>{total_calories}</b> ккал")
    if daily_menu.ratings_count:
        lines.append(f"⭐ Оценка: <b>{daily_menu.average_rating:.1f}</b> ({daily_menu.ratings_count})")
    else:
        lines.append("⭐ Оценок пока нет")
    lines.append(f"👁 Просмотров: {daily_menu.views_count}")
    return "\n".join(lines)


def format_not_found(skip_days: int) -> str:
    if skip_days == 0:
        return "😔 Меню на сегодня ещё не опубликовано."
    return "😔 Меню на выбранный день ещё не опубликовано."


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
