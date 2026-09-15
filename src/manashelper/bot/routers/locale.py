from aiogram import F, Router, flags
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import LocaleCallback, SettingsAction, SettingsCallback
from manashelper.bot.keyboards.locale import LOCALE_PROMPT_TEXT, NATIVE_NAMES, build_locale_keyboard
from manashelper.bot.routers.start import send_welcome
from manashelper.localization.i18n import i18n
from manashelper.services.locale import LocaleService

router = Router(name="locale")


@router.message(Command("language"))
@flags.private_chat_only
async def on_language_command(message: Message) -> None:
    await message.answer(LOCALE_PROMPT_TEXT, reply_markup=build_locale_keyboard())


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_LANGUAGE))
@flags.private_chat_only
async def on_open_language(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(LOCALE_PROMPT_TEXT, reply_markup=build_locale_keyboard())
    await callback_query.answer()


@router.callback_query(LocaleCallback.filter())
@flags.private_chat_only
async def on_locale_selected(
    callback_query: CallbackQuery,
    callback_data: LocaleCallback,
    locale_service: FromDishka[LocaleService],
) -> None:
    await locale_service.set_locale(callback_query.from_user.id, callback_data.locale)

    # The picker fires before a locale is resolved (or while switching away from the current
    # one), so the ambient gettext context can't be trusted here — bind explicitly to the one
    # the user just picked instead.
    with i18n.context(), i18n.use_locale(callback_data.locale.value):
        if isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                _("✅ Language: {language}").format(language=NATIVE_NAMES[callback_data.locale])
            )
            await send_welcome(callback_query.message)
    await callback_query.answer()
