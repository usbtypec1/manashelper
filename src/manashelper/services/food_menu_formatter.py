from aiogram.enums import ParseMode
from aiogram.types import InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaPhoto, InputMediaVideo

from manashelper.services.daily_menu_service import DailyMenuModel

MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaLivePhoto | InputMediaPhoto | InputMediaVideo


def format_daily_menu(daily_menu: DailyMenuModel) -> str:
    lines = [f"<b>Меню на {daily_menu.date.strftime('%d.%m.%Y')}</b>", ""]

    total_calories = 0
    for dish in daily_menu.dishes:
        lines.append(f"🍽 {dish.name} — {dish.calories} ккал")
        total_calories += dish.calories

    lines.append("")
    lines.append(f"Итого калорий: {total_calories}")
    if daily_menu.ratings_count:
        lines.append(f"⭐ Оценка: {daily_menu.average_rating:.1f} ({daily_menu.ratings_count})")
    else:
        lines.append("⭐ Оценок пока нет")
    lines.append(f"👁 Просмотров: {daily_menu.views_count}")
    return "\n".join(lines)


def format_not_found(skip_days: int) -> str:
    if skip_days == 0:
        return "Меню на сегодня ещё не опубликовано."
    return "Меню на выбранный день ещё не опубликовано."


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
