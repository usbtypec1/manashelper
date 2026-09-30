from aiogram import Bot
from aiogram.types import BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from manashelper.config import Settings
from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.services.bot_commands import build_admin_commands, build_group_commands, build_private_commands


async def setup_commands(bot: Bot, settings: Settings) -> None:
    for locale in Locale:
        await bot.set_my_commands(
            commands=build_private_commands(locale), scope=BotCommandScopeAllPrivateChats(), language_code=locale.value
        )
        await bot.set_my_commands(
            commands=build_group_commands(locale), scope=BotCommandScopeAllGroupChats(), language_code=locale.value
        )

    # Fallback for clients whose language isn't one of the supported locales.
    await bot.set_my_commands(commands=build_private_commands(DEFAULT_LOCALE), scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=build_group_commands(DEFAULT_LOCALE), scope=BotCommandScopeAllGroupChats())

    # `/broadcast` is scoped to just the admin chat, not any of the "all chats" scopes above - see
    # `services/bot_commands.py::build_admin_commands`.
    await bot.set_my_commands(
        commands=build_admin_commands(DEFAULT_LOCALE), scope=BotCommandScopeChat(chat_id=settings.admin_chat_id)
    )
