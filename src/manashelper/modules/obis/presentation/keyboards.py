from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.i18n import get_i18n
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.core.config import get_settings
from manashelper.modules.notifications.settings import NotificationSetting, NotificationSettingsSummary
from manashelper.modules.obis.presentation.callbacks import (
    ObisAction,
    ObisCallback,
    ObisNotificationSettingCallback,
    ObisResultsPageCallback,
)
from manashelper.platform.telegram.callbacks import (
    NavigationAction,
    NavigationCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.platform.telegram.navigation import build_navigation_keyboard


def build_obis_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("menu.attendance"), callback_data=ObisCallback(action=ObisAction.ATTENDANCE))
    builder.button(text=_("menu.grades"), callback_data=ObisCallback(action=ObisAction.GRADES))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY)))
    return builder.as_markup()


def build_obis_notifications_keyboard(settings: NotificationSettingsSummary) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for setting, label, enabled in (
        (NotificationSetting.EXAM_GRADES, _("notifications.exam_grades"), settings.exam_grades_enabled),
        (NotificationSetting.LESSON_SKIPS, _("notifications.lesson_skips"), settings.lesson_skips_enabled),
    ):
        marker = "✅" if enabled else "❌"
        builder.button(text=f"{marker} {label}", callback_data=ObisNotificationSettingCallback(setting=setting))
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard())
    return builder.as_markup()


def build_obis_results_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️", callback_data=ObisResultsPageCallback(page=page - 1))
    if page < total_pages - 1:
        builder.button(text="➡️", callback_data=ObisResultsPageCallback(page=page + 1))
    builder.adjust(2)
    builder.attach(build_navigation_keyboard(ObisCallback(action=ObisAction.MENU)))
    return builder.as_markup()


def build_obis_settings_keyboard(has_credentials: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    credentials_text = _("obis.update_credentials") if has_credentials else _("obis.enter_credentials")
    builder.button(text=credentials_text, callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
    if has_credentials:
        builder.button(
            text=_("obis.clear_credentials"), callback_data=ObisCallback(action=ObisAction.CLEAR_CREDENTIALS)
        )
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard())
    return builder.as_markup()


def build_no_credentials_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("obis.enter_credentials"), callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY)))
    return builder.as_markup()


def build_confirm_clear_credentials_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("obis.confirm_clear"), callback_data=ObisCallback(action=ObisAction.CONFIRM_CLEAR_CREDENTIALS)
    )
    builder.button(text=_("common.cancel"), callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()


def build_terms_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    public_url = get_settings().public_url
    if public_url:
        builder.button(
            text=_("obis.terms"),
            web_app=WebAppInfo(url=f"{public_url.rstrip('/')}/app/?view=terms&lang={get_i18n().current_locale}"),
        )
    else:
        builder.button(text=_("obis.terms"), callback_data=ObisCallback(action=ObisAction.TERMS))
    builder.button(text=_("obis.accept_terms"), callback_data=ObisCallback(action=ObisAction.ACCEPT_TERMS))
    builder.button(text=_("common.cancel"), callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("common.cancel"), callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()
