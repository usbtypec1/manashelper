from aiogram.filters.callback_data import CallbackData

from manashelper.modules.notifications.settings import NotificationSetting


class BroadcastMuteCallback(CallbackData, prefix="broadcast_mute"):
    muted: bool


class NotificationSettingCallback(CallbackData, prefix="notification_setting"):
    setting: NotificationSetting
