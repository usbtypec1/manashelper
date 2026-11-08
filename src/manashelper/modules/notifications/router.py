from datetime import UTC, datetime

from aiogram import F, Router, flags
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.notifications.application.use_cases.get_notification_settings import (
    GetNotificationSettingsUseCase,
)
from manashelper.modules.notifications.application.use_cases.set_broadcast_mute import SetBroadcastMuteUseCase
from manashelper.modules.notifications.application.use_cases.toggle_notification_setting import (
    ToggleNotificationSettingUseCase,
)
from manashelper.modules.notifications.callbacks import BroadcastMuteCallback, NotificationSettingCallback
from manashelper.modules.notifications.keyboards import build_notifications_keyboard
from manashelper.modules.notifications.settings import (
    NotificationSetting,
    NotificationSettingsSummary,
    UserNotFoundError,
)
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback

router = Router(name="notifications")


async def _show_notifications_menu(callback_query: CallbackQuery, settings: NotificationSettingsSummary) -> None:
    if isinstance(callback_query.message, Message):
        text = _("notifications.title")
        if settings.broadcast_muted_until is not None and settings.broadcast_muted_until > datetime.now(UTC):
            text += "\n\n" + _("notifications.broadcast_muted_until").format(
                until=settings.broadcast_muted_until.astimezone(BISHKEK_TZ).strftime("%d.%m.%Y %H:%M")
            )
        await callback_query.message.edit_text(text, reply_markup=build_notifications_keyboard(settings))


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_NOTIFICATIONS))
@flags.private_chat_only
async def on_open_notifications(
    callback_query: CallbackQuery,
    get_notification_settings: FromDishka[GetNotificationSettingsUseCase],
) -> None:
    try:
        settings = await get_notification_settings.execute(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.BACK_TO_NOTIFICATIONS))
@flags.private_chat_only
async def on_back_to_notifications(
    callback_query: CallbackQuery,
    get_notification_settings: FromDishka[GetNotificationSettingsUseCase],
) -> None:
    await on_open_notifications(callback_query, get_notification_settings)


@router.callback_query(NotificationSettingCallback.filter())
@flags.private_chat_only
async def on_toggle_notification_setting(
    callback_query: CallbackQuery,
    callback_data: NotificationSettingCallback,
    toggle_notification_setting: FromDishka[ToggleNotificationSettingUseCase],
) -> None:
    try:
        settings = await toggle_notification_setting.execute(callback_query.from_user.id, callback_data.setting)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return

    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()


@router.callback_query(BroadcastMuteCallback.filter())
@flags.private_chat_only
async def on_broadcast_mute(
    callback_query: CallbackQuery,
    callback_data: BroadcastMuteCallback,
    set_broadcast_mute: FromDishka[SetBroadcastMuteUseCase],
) -> None:
    try:
        settings = await set_broadcast_mute.execute(callback_query.from_user.id, callback_data.muted)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    if callback_data.muted:
        if isinstance(callback_query.message, Message) and callback_query.message.reply_markup is not None:
            settings_button = NotificationSettingCallback(setting=NotificationSetting.SCHEDULE_CHANGES).pack()
            if any(
                button.callback_data == settings_button
                for row in callback_query.message.reply_markup.inline_keyboard
                for button in row
            ):
                await _show_notifications_menu(callback_query, settings)
        await callback_query.answer(_("notifications.broadcast_muted"), show_alert=True)
    else:
        await _show_notifications_menu(callback_query, settings)
        await callback_query.answer(_("notifications.broadcast_resumed"))
