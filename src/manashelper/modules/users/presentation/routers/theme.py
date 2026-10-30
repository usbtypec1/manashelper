from aiogram import F, Router, flags
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.presentation.callbacks import ThemeCallback
from manashelper.modules.users.presentation.keyboards.theme import build_theme_keyboard, theme_name
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.navigation import send_welcome

router = Router(name="theme")


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_THEME))
@flags.private_chat_only
async def on_open_theme(callback_query: CallbackQuery, theme_service: FromDishka[ThemeService]) -> None:
    selected = await theme_service.get_theme(callback_query.from_user.id)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("theme.prompt"), reply_markup=build_theme_keyboard(selected))
    await callback_query.answer()


@router.callback_query(ThemeCallback.filter())
@flags.private_chat_only
async def on_theme_selected(
    callback_query: CallbackQuery,
    callback_data: ThemeCallback,
    theme_service: FromDishka[ThemeService],
) -> None:
    await theme_service.set_theme(callback_query.from_user.id, callback_data.theme)
    with i18n.use_theme(callback_data.theme):
        if isinstance(callback_query.message, Message):
            text = _("theme.selected").format(theme=theme_name(callback_data.theme))
            keyboard = build_theme_keyboard(callback_data.theme)
            if callback_query.message.text != text or callback_query.message.reply_markup != keyboard:
                await callback_query.message.edit_text(text, reply_markup=keyboard)
            await send_welcome(callback_query.message)
        await callback_query.answer()
