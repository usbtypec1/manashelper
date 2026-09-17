from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import VersionCallback, VersionsPageCallback
from manashelper.services.version_history import VersionSummary

VERSIONS_PER_ROW = 4


def build_versions_list_keyboard(versions: list[VersionSummary], page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for entry in versions:
        builder.button(text=f"v{entry.version}", callback_data=VersionCallback(version=entry.version, page=page))
    builder.adjust(VERSIONS_PER_ROW)

    if total_pages > 1:
        nav_builder = InlineKeyboardBuilder()
        if page > 0:
            nav_builder.button(text="⬅️", callback_data=VersionsPageCallback(page=page - 1))
        if page < total_pages - 1:
            nav_builder.button(text="➡️", callback_data=VersionsPageCallback(page=page + 1))
        nav_builder.adjust(2)
        builder.attach(nav_builder)

    return builder.as_markup()


def build_version_detail_keyboard(page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("◀️ Back"), callback_data=VersionsPageCallback(page=page))
    builder.adjust(1)
    return builder.as_markup()
