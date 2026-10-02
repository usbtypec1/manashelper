import logging
from datetime import date, datetime

from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, EphemeralMessageParameters, Message, ReplyParameters
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    FOOD_MENU_DAY_TO_SKIP_DAYS,
    FoodMenuCallback,
    FoodMenuDateCallback,
    FoodMenuOpenCallback,
    FoodMenuRatingCallback,
)
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.food_menu import (
    build_food_menu_settings_buttons,
    build_menu_day_keyboard,
    build_menu_open_keyboard,
    build_menu_rating_buttons,
)
from manashelper.services.daily_menu import BISHKEK_TZ, DailyMenuNotFoundError, DailyMenuService
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupSettingsService
from manashelper.services.food_menu_formatter import (
    build_daily_menu_rich_message,
    format_menu_day_selection,
    format_not_found,
    refresh_daily_menu_rating,
)

router = Router(name="food_menu")
logger = logging.getLogger(__name__)


async def _response_parameters(
    message: Message, callback_query: CallbackQuery | None = None
) -> tuple[EphemeralMessageParameters | None, ReplyParameters | None]:
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return None, None
    if callback_query is not None:
        return (
            EphemeralMessageParameters(
                receiver_user_id=callback_query.from_user.id,
                callback_query_id=callback_query.id,
                replace_callback_query_message=message.ephemeral_message_id is None,
            ),
            None,
        )
    if message.from_user is None or message.from_user.is_bot:
        return None, None
    parameters = EphemeralMessageParameters(receiver_user_id=message.from_user.id)
    if message.ephemeral_message_id is not None:
        return parameters, ReplyParameters(ephemeral_message_id=message.ephemeral_message_id)
    # Ordinary commands are eligible only when the bot is a group administrator.
    # Other bots can respond privately after the user clicks the day selector.
    bot = message.bot
    assert bot is not None
    member = await bot.get_chat_member(message.chat.id, bot.id)
    if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return parameters, None
    return None, None


async def _send_menu_launcher(message: Message) -> None:
    await message.answer(_("food.day_selection_title"), reply_markup=build_menu_open_keyboard())


async def _show_day_prompt(
    message: Message,
    daily_menu_service: DailyMenuService,
    *,
    callback_query: CallbackQuery | None = None,
    show_usage: bool = False,
) -> None:
    parameters, reply_parameters = await _response_parameters(message, callback_query)
    if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) and parameters is None:
        await _send_menu_launcher(message)
        return
    availability = await daily_menu_service.get_available_dates()
    await message.answer(
        format_menu_day_selection(bool(availability.dates), show_usage=show_usage),
        reply_markup=build_menu_day_keyboard(availability.dates, availability.today) if availability.dates else None,
        ephemeral_message_parameters=parameters,
        reply_parameters=reply_parameters,
    )


@router.message(TranslatedText("menu.food"))
async def on_food_menu_button(message: Message, daily_menu_service: FromDishka[DailyMenuService]) -> None:
    await _show_day_prompt(message, daily_menu_service)


async def _send_daily_menu(
    message: Message,
    skip_days: int,
    daily_menu_service: DailyMenuService,
    food_menu_cleanup_settings_service: FoodMenuCleanupSettingsService,
    *,
    callback_query: CallbackQuery | None = None,
    menu_date: date | None = None,
) -> None:
    parameters, reply_parameters = await _response_parameters(message, callback_query)
    if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) and parameters is None:
        await _send_menu_launcher(message)
        return
    try:
        user_id = parameters.receiver_user_id if parameters is not None else None
        if message.chat.type == ChatType.PRIVATE:
            user_id = message.chat.id
        if menu_date is None:
            daily_menu = await daily_menu_service.get_daily_menu_by_skipping_days(skip_days, user_id=user_id)
        else:
            daily_menu = await daily_menu_service.get_daily_menu_by_date(menu_date, user_id=user_id)
    except DailyMenuNotFoundError:
        if menu_date is not None:
            skip_days = 0 if menu_date == datetime.now(BISHKEK_TZ).date() else 1
        await message.answer(
            format_not_found(skip_days),
            ephemeral_message_parameters=parameters,
            reply_parameters=reply_parameters,
        )
        return

    sent = await message.answer_rich(
        rich_message=build_daily_menu_rich_message(
            daily_menu,
            build_menu_rating_buttons(daily_menu.id, daily_menu.user_rating),
            build_food_menu_settings_buttons() if parameters is None else [],
        ),
        ephemeral_message_parameters=parameters,
        reply_parameters=reply_parameters,
    )
    if sent.ephemeral_message_id is None and sent.message_id:
        await food_menu_cleanup_settings_service.schedule_cleanup(message.chat.id, [sent.message_id])


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
    food_menu_cleanup_settings_service: FromDishka[FoodMenuCleanupSettingsService],
) -> None:
    skip_days = _parse_skip_days(command.args)
    if skip_days is None:
        await _show_day_prompt(message, daily_menu_service, show_usage=bool(command.args))
        return
    await _send_daily_menu(message, skip_days, daily_menu_service, food_menu_cleanup_settings_service)


@router.callback_query(FoodMenuOpenCallback.filter())
async def on_food_menu_open_callback(
    callback_query: CallbackQuery,
    daily_menu_service: FromDishka[DailyMenuService],
) -> None:
    if isinstance(callback_query.message, Message):
        await _show_day_prompt(callback_query.message, daily_menu_service, callback_query=callback_query)
    await callback_query.answer()


@router.callback_query(FoodMenuDateCallback.filter())
async def on_food_menu_date_callback(
    callback_query: CallbackQuery,
    callback_data: FoodMenuDateCallback,
    daily_menu_service: FromDishka[DailyMenuService],
    food_menu_cleanup_settings_service: FromDishka[FoodMenuCleanupSettingsService],
) -> None:
    try:
        menu_date = date.fromisoformat(callback_data.menu_date)
    except ValueError:
        await callback_query.answer(_("food.menu_unpublished"), show_alert=True)
        return
    if isinstance(callback_query.message, Message):
        await _send_daily_menu(
            callback_query.message,
            0,
            daily_menu_service,
            food_menu_cleanup_settings_service,
            callback_query=callback_query,
            menu_date=menu_date,
        )
    await callback_query.answer()


@router.callback_query(FoodMenuCallback.filter())
async def on_food_menu_day_callback(
    callback_query: CallbackQuery,
    callback_data: FoodMenuCallback,
    daily_menu_service: FromDishka[DailyMenuService],
    food_menu_cleanup_settings_service: FromDishka[FoodMenuCleanupSettingsService],
) -> None:
    skip_days = FOOD_MENU_DAY_TO_SKIP_DAYS[callback_data.day]
    if isinstance(callback_query.message, Message):
        await _send_daily_menu(
            callback_query.message,
            skip_days,
            daily_menu_service,
            food_menu_cleanup_settings_service,
            callback_query=callback_query,
        )
    await callback_query.answer()


@router.callback_query(FoodMenuRatingCallback.filter())
async def on_food_menu_rating_callback(
    callback_query: CallbackQuery,
    callback_data: FoodMenuRatingCallback,
    daily_menu_service: FromDishka[DailyMenuService],
) -> None:
    try:
        daily_menu = await daily_menu_service.set_rating(
            callback_query.from_user.id, callback_data.daily_menu_id, callback_data.rating
        )
    except ValueError:
        await callback_query.answer(_("food.rating_unavailable"), show_alert=True)
        return

    message = callback_query.message
    if isinstance(message, Message) and message.rich_message:
        user_rating = (
            daily_menu.user_rating
            if message.chat.type == "private" or message.ephemeral_message_id is not None
            else None
        )
        rich_message = refresh_daily_menu_rating(
            message.rich_message, daily_menu, build_menu_rating_buttons(daily_menu.id, user_rating)
        )
        try:
            edit = message.edit_ephemeral_text if message.ephemeral_message_id is not None else message.edit_text
            await edit(rich_message=rich_message, parse_mode=None)
        except TelegramBadRequest as error:
            if "message is not modified" not in error.message:
                logger.warning("Failed to refresh menu rating message", exc_info=True)
        except TelegramAPIError:
            logger.warning("Failed to refresh menu rating message", exc_info=True)
    await callback_query.answer(_("food.rating_thanks"))
