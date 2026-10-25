from aiogram import F, Router, flags
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.notifications.callbacks import NotificationSettingCallback
from manashelper.modules.notifications.keyboards import build_notifications_keyboard
from manashelper.modules.notifications.settings import (
    NotificationSettingsService,
    NotificationSettingsSummary,
    UserNotFoundError,
)
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback

router = Router(name="notifications")


async def _show_notifications_menu(callback_query: CallbackQuery, settings: NotificationSettingsSummary) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("notifications.title"), reply_markup=build_notifications_keyboard(settings)
        )


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_NOTIFICATIONS))
@flags.private_chat_only
async def on_open_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    try:
        settings = await notification_settings_service.get_settings(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.BACK_TO_NOTIFICATIONS))
@flags.private_chat_only
async def on_back_to_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    await on_open_notifications(callback_query, notification_settings_service)


@router.callback_query(NotificationSettingCallback.filter())
@flags.private_chat_only
async def on_toggle_notification_setting(
    callback_query: CallbackQuery,
    callback_data: NotificationSettingCallback,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    try:
        settings = await notification_settings_service.toggle_setting(
            callback_query.from_user.id, callback_data.setting
        )
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return

    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()
