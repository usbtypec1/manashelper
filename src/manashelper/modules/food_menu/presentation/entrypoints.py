from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import CallbackQuery, EphemeralMessageParameters, Message, ReplyParameters

from manashelper.modules.food_menu.application.daily_menu import DailyMenuService
from manashelper.modules.food_menu.presentation.food_menu_formatter import build_menu_day_selection, build_menu_launcher
from manashelper.modules.food_menu.presentation.keyboards.food_menu import (
    build_menu_day_buttons,
    build_menu_open_button,
)


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
    await message.answer_rich(rich_message=build_menu_launcher(build_menu_open_button()))


async def show_food_menu(
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
    await message.answer_rich(
        rich_message=build_menu_day_selection(
            build_menu_day_buttons(availability.dates, availability.today), show_usage=show_usage
        ),
        ephemeral_message_parameters=parameters,
        reply_parameters=reply_parameters,
    )
