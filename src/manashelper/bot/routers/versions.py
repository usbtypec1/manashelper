from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from dishka import FromDishka

from manashelper.bot.callback_data import VersionCallback, VersionsPageCallback
from manashelper.bot.keyboards.versions import build_version_detail_keyboard, build_versions_list_keyboard
from manashelper.services.version_history import VersionHistoryService
from manashelper.services.version_history_formatter import format_version_detail, format_versions_list_header

router = Router(name="versions")


async def _build_list_message(
    version_history_service: VersionHistoryService, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    total_pages = await version_history_service.total_pages()
    versions = await version_history_service.get_page(page)
    return format_versions_list_header(page, total_pages), build_versions_list_keyboard(versions, page, total_pages)


@router.message(Command("versions"))
async def cmd_versions(message: Message, version_history_service: FromDishka[VersionHistoryService]) -> None:
    text, keyboard = await _build_list_message(version_history_service, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(VersionsPageCallback.filter())
async def on_versions_page_selected(
    callback_query: CallbackQuery,
    callback_data: VersionsPageCallback,
    version_history_service: FromDishka[VersionHistoryService],
) -> None:
    if isinstance(callback_query.message, Message):
        text, keyboard = await _build_list_message(version_history_service, callback_data.page)
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


@router.callback_query(VersionCallback.filter())
async def on_version_selected(
    callback_query: CallbackQuery,
    callback_data: VersionCallback,
    version_history_service: FromDishka[VersionHistoryService],
) -> None:
    entry = await version_history_service.find_version(callback_data.version)
    if entry is not None and isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            format_version_detail(entry), reply_markup=build_version_detail_keyboard(callback_data.page)
        )
    await callback_query.answer()
