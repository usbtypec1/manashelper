"""Free rooms, room timetables and teacher timetables built from every synchronized course."""

from datetime import datetime
from typing import Any

from aiogram import F, Router, flags
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.schedule.application.campus import CampusQuery, SearchMatch, current_period
from manashelper.modules.schedule.application.timetable_entries import WORKDAYS, find_now_next
from manashelper.modules.schedule.presentation.callbacks import (
    CampusKind,
    CampusResultCallback,
    CampusSearchCallback,
    FreeRoomsCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.modules.schedule.presentation.editing import edit_view
from manashelper.modules.schedule.presentation.entries_formatter import (
    format_free_rooms,
    format_room,
    format_teacher,
)
from manashelper.modules.schedule.presentation.keyboards.campus import (
    NOW_WEEKDAY,
    build_campus_not_found_keyboard,
    build_campus_prompt_keyboard,
    build_campus_result_keyboard,
    build_free_rooms_keyboard,
    build_matches_keyboard,
)
from manashelper.platform.telegram.filters.translated_text import TranslatedText

menu_router = Router(name="campus_menu")
router = Router(name="campus")

MATCHES_KEY = "campus_matches"
MIN_QUERY_LENGTH = 2


class CampusSearchForm(StatesGroup):
    room = State()
    teacher = State()


_STATES = {CampusKind.ROOM: CampusSearchForm.room, CampusKind.TEACHER: CampusSearchForm.teacher}


def search_prompt(kind: CampusKind) -> str:
    if kind == CampusKind.ROOM:
        return _("schedule.rooms.search_prompt")
    return _("schedule.teacher.search_prompt")


def default_weekday(now: datetime) -> int:
    weekday = now.isoweekday()
    return weekday if weekday in WORKDAYS else WORKDAYS[0]


async def _free_rooms_view(
    campus: CampusQuery, weekday: int, period: int, building: str
) -> tuple[str, InlineKeyboardMarkup]:
    periods = await campus.get_periods()
    if weekday == NOW_WEEKDAY:
        weekday, period = current_period(periods, datetime.now(BISHKEK_TZ)) if periods else (WORKDAYS[0], 0)
    result = await campus.get_free_rooms(weekday, period, periods)
    if building and building not in {name for name, _count in result.buildings()}:
        building = ""
    return format_free_rooms(result, building), build_free_rooms_keyboard(result, building)


@menu_router.message(TranslatedText("menu.rooms"))
@flags.private_chat_only
async def on_rooms_button(message: Message, state: FSMContext, campus: FromDishka[CampusQuery]) -> None:
    await state.clear()
    text, keyboard = await _free_rooms_view(campus, NOW_WEEKDAY, 0, "")
    await message.answer(text, reply_markup=keyboard)


@menu_router.message(TranslatedText("menu.teachers"))
@flags.private_chat_only
async def on_teachers_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CampusSearchForm.teacher)
    await message.answer(search_prompt(CampusKind.TEACHER), reply_markup=build_campus_prompt_keyboard())


@menu_router.callback_query(TimetableMenuCallback.filter(F.action == TimetableMenuAction.OPEN_FREE_ROOMS))
@flags.private_chat_only
async def on_free_rooms_now(callback_query: CallbackQuery, state: FSMContext, campus: FromDishka[CampusQuery]) -> None:
    await state.set_state(None)
    text, keyboard = await _free_rooms_view(campus, NOW_WEEKDAY, 0, "")
    await edit_view(callback_query, text, keyboard)
    await callback_query.answer()


@menu_router.callback_query(FreeRoomsCallback.filter())
@flags.private_chat_only
async def on_free_rooms_selected(
    callback_query: CallbackQuery, callback_data: FreeRoomsCallback, campus: FromDishka[CampusQuery]
) -> None:
    weekday = callback_data.weekday if callback_data.weekday in WORKDAYS else NOW_WEEKDAY
    text, keyboard = await _free_rooms_view(campus, weekday, callback_data.period, callback_data.building)
    await edit_view(callback_query, text, keyboard)
    await callback_query.answer()


@menu_router.callback_query(CampusSearchCallback.filter())
@flags.private_chat_only
async def on_search_selected(
    callback_query: CallbackQuery, callback_data: CampusSearchCallback, state: FSMContext
) -> None:
    await state.set_state(_STATES[callback_data.kind])
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            search_prompt(callback_data.kind), reply_markup=build_campus_prompt_keyboard()
        )
    await callback_query.answer()


async def _remember_matches(state: FSMContext, kind: CampusKind, matches: list[SearchMatch]) -> None:
    data = await state.get_data()
    stored: dict[str, Any] = dict(data.get(MATCHES_KEY, {}))
    stored[kind.value] = [[match.key, match.name] for match in matches]
    await state.update_data({MATCHES_KEY: stored})


async def _result_view(
    campus: CampusQuery, kind: CampusKind, key: str, index: int, weekday: int
) -> tuple[str, InlineKeyboardMarkup] | None:
    now = datetime.now(BISHKEK_TZ)
    weekday = weekday if weekday in WORKDAYS else default_weekday(now)
    if kind == CampusKind.ROOM:
        room = await campus.get_room(key)
        if room is None:
            return None
        info, entries = room
        text = format_room(info, entries, weekday, find_now_next(entries, now), now)
    else:
        teacher = await campus.get_teacher(key)
        if teacher is None:
            return None
        name, entries = teacher
        text = format_teacher(name, entries, weekday, find_now_next(entries, now), now)
    return text, build_campus_result_keyboard(kind, index, weekday)


async def _handle_query(message: Message, state: FSMContext, campus: CampusQuery, kind: CampusKind) -> None:
    await state.set_state(None)
    query = message.text.strip() if message.text else ""
    if len(query) < MIN_QUERY_LENGTH:
        await message.answer(_("schedule.query_too_short_retry"), reply_markup=build_campus_not_found_keyboard(kind))
        return
    matches = await (campus.search_rooms(query) if kind == CampusKind.ROOM else campus.search_teachers(query))
    if not matches:
        await message.answer(_("schedule.no_results"), reply_markup=build_campus_not_found_keyboard(kind))
        return
    await _remember_matches(state, kind, matches)
    if len(matches) == 1:
        view = await _result_view(campus, kind, matches[0].key, 0, NOW_WEEKDAY)
        if view is not None:
            await message.answer(view[0], reply_markup=view[1])
            return
    await message.answer(_("schedule.campus.choose"), reply_markup=build_matches_keyboard(kind, matches))


@router.message(StateFilter(CampusSearchForm.room))
@flags.private_chat_only
async def on_room_query(message: Message, state: FSMContext, campus: FromDishka[CampusQuery]) -> None:
    await _handle_query(message, state, campus, CampusKind.ROOM)


@router.message(StateFilter(CampusSearchForm.teacher))
@flags.private_chat_only
async def on_teacher_query(message: Message, state: FSMContext, campus: FromDishka[CampusQuery]) -> None:
    await _handle_query(message, state, campus, CampusKind.TEACHER)


@menu_router.callback_query(CampusResultCallback.filter())
@flags.private_chat_only
async def on_result_selected(
    callback_query: CallbackQuery,
    callback_data: CampusResultCallback,
    state: FSMContext,
    campus: FromDishka[CampusQuery],
) -> None:
    data = await state.get_data()
    matches = data.get(MATCHES_KEY, {}).get(callback_data.kind.value, [])
    if not 0 <= callback_data.index < len(matches):
        await callback_query.answer(_("schedule.search_expired"), show_alert=True)
        return
    view = await _result_view(
        campus, callback_data.kind, matches[callback_data.index][0], callback_data.index, callback_data.weekday
    )
    if view is None:
        await callback_query.answer(_("schedule.search_expired"), show_alert=True)
        return
    await edit_view(callback_query, view[0], view[1])
    await callback_query.answer()
