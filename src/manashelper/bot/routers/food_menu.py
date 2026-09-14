from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import FOOD_MENU_DAY_TO_SKIP_DAYS, FoodMenuCallback, FoodMenuRatingCallback
from manashelper.bot.keyboards.food_menu import build_day_keyboard, build_rating_keyboard
from manashelper.services.daily_menu import DailyMenuNotFoundError, DailyMenuService
from manashelper.services.food_menu_formatter import build_photos, format_daily_menu, format_not_found

router = Router(name="food_menu")

FOOD_MENU_INTRO_TEXT = (
    "🍉 <b>Меню столовой</b>\n\n"
    "Выберите день ниже или отправьте команду:\n"
    "• <code>/yemek today</code> — сегодня\n"
    "• <code>/yemek tomorrow</code> — завтра\n"
    "• <code>/yemek 2</code> — через N дней"
)
USAGE_TEXT = "ℹ️ Использование: <code>/yemek today</code>, <code>/yemek tomorrow</code> или <code>/yemek 2</code>"


@router.message(F.text == "🍉 Йемек")
async def on_food_menu_button(message: Message) -> None:
    await message.answer(FOOD_MENU_INTRO_TEXT, reply_markup=build_day_keyboard())


async def _send_daily_menu(message: Message, skip_days: int, daily_menu_service: DailyMenuService) -> None:
    try:
        daily_menu = await daily_menu_service.get_daily_menu_by_skipping_days(skip_days)
    except DailyMenuNotFoundError:
        await message.answer(format_not_found(skip_days))
        return

    caption = format_daily_menu(daily_menu)
    await message.answer_media_group(media=build_photos(caption, daily_menu))
    await message.answer("⭐ Оцените меню:", reply_markup=build_rating_keyboard(daily_menu.id))


def _parse_skip_days(args: str | None) -> int | None:
    if args is None:
        return None
    normalized = args.strip().lower()
    if normalized == "today":
        return 0
    if normalized == "tomorrow":
        return 1
    if normalized.isdigit():
        return int(normalized)
    return None


@router.message(Command("yemek"))
async def cmd_yemek(
    message: Message,
    command: CommandObject,
    daily_menu_service: FromDishka[DailyMenuService],
) -> None:
    skip_days = _parse_skip_days(command.args)
    if skip_days is None:
        await message.answer(USAGE_TEXT, reply_markup=build_day_keyboard())
        return
    await _send_daily_menu(message, skip_days, daily_menu_service)


@router.callback_query(FoodMenuCallback.filter())
async def on_food_menu_day_callback(
    callback_query: CallbackQuery,
    callback_data: FoodMenuCallback,
    daily_menu_service: FromDishka[DailyMenuService],
) -> None:
    skip_days = FOOD_MENU_DAY_TO_SKIP_DAYS[callback_data.day]
    if isinstance(callback_query.message, Message):
        await _send_daily_menu(callback_query.message, skip_days, daily_menu_service)
    await callback_query.answer()


@router.callback_query(FoodMenuRatingCallback.filter())
async def on_food_menu_rating_callback(
    callback_query: CallbackQuery,
    callback_data: FoodMenuRatingCallback,
    daily_menu_service: FromDishka[DailyMenuService],
) -> None:
    await daily_menu_service.set_rating(callback_query.from_user.id, callback_data.daily_menu_id, callback_data.rating)
    await callback_query.answer("Спасибо за оценку!", show_alert=True)
