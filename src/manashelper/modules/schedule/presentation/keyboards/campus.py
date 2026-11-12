from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.localization.weekdays import weekday_abbr
from manashelper.modules.schedule.application.campus import FreeRooms, SearchMatch
from manashelper.modules.schedule.application.time_ranges import format_minutes, parse_time_range_start_minutes
from manashelper.modules.schedule.application.timetable_entries import WORKDAYS
from manashelper.modules.schedule.presentation.callbacks import (
    CampusKind,
    CampusResultCallback,
    CampusSearchCallback,
    FreeRoomsCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.platform.telegram.callbacks import NavigationAction, NavigationCallback
from manashelper.platform.telegram.navigation import build_navigation_keyboard

NOW_WEEKDAY = 0


def _study_navigation() -> InlineKeyboardBuilder:
    return build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY))


def _period_label(time_range: str) -> str:
    return format_minutes(parse_time_range_start_minutes(time_range))


def build_free_rooms_keyboard(result: FreeRooms, building: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not building:
        buildings = InlineKeyboardBuilder()
        for name, count in result.buildings():
            buildings.button(
                text=f"{name} · {count}",
                callback_data=FreeRoomsCallback(weekday=result.weekday, period=result.period, building=name),
            )
        buildings.adjust(3)
        builder.attach(buildings)

    if result.periods:
        periods = InlineKeyboardBuilder()
        if result.period > 0:
            previous = result.periods[result.period - 1]
            periods.button(
                text=f"⬅️ {_period_label(previous)}",
                callback_data=FreeRoomsCallback(weekday=result.weekday, period=result.period - 1, building=building),
            )
        periods.button(
            text=_("schedule.rooms.now"),
            callback_data=FreeRoomsCallback(weekday=NOW_WEEKDAY, period=0, building=building),
        )
        if result.period < len(result.periods) - 1:
            following = result.periods[result.period + 1]
            periods.button(
                text=f"{_period_label(following)} ➡️",
                callback_data=FreeRoomsCallback(weekday=result.weekday, period=result.period + 1, building=building),
            )
        periods.adjust(3)
        builder.attach(periods)

        days = InlineKeyboardBuilder()
        for weekday in WORKDAYS:
            if weekday != result.weekday:
                days.button(
                    text=weekday_abbr(weekday),
                    callback_data=FreeRoomsCallback(weekday=weekday, period=result.period, building=building),
                )
        days.adjust(4)
        builder.attach(days)

    tools = InlineKeyboardBuilder()
    if building:
        tools.button(
            text=_("schedule.rooms.buildings"),
            callback_data=FreeRoomsCallback(weekday=result.weekday, period=result.period),
        )
    tools.button(text=_("schedule.rooms.search"), callback_data=CampusSearchCallback(kind=CampusKind.ROOM))
    tools.adjust(1)
    builder.attach(tools)
    builder.attach(_study_navigation())
    return builder.as_markup()


def build_campus_prompt_keyboard() -> InlineKeyboardMarkup:
    return _study_navigation().as_markup()


def build_matches_keyboard(kind: CampusKind, matches: list[SearchMatch]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, match in enumerate(matches):
        builder.button(text=match.name, callback_data=CampusResultCallback(kind=kind, index=index))
    builder.adjust(1)
    builder.attach(_search_again(kind))
    return builder.as_markup()


def _search_again(kind: CampusKind) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    label = _("schedule.rooms.search") if kind == CampusKind.ROOM else _("schedule.teacher.search")
    builder.button(text=label, callback_data=CampusSearchCallback(kind=kind))
    if kind == CampusKind.ROOM:
        builder.button(
            text=_("schedule.rooms.free_now"),
            callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_FREE_ROOMS),
        )
    builder.adjust(1)
    builder.attach(_study_navigation())
    return builder


def build_campus_result_keyboard(kind: CampusKind, index: int, weekday: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    days = InlineKeyboardBuilder()
    for day in WORKDAYS:
        if day != weekday:
            emoji = "⬅️" if day < weekday else "➡️"
            days.button(
                text=f"{emoji} {weekday_abbr(day)}",
                callback_data=CampusResultCallback(kind=kind, index=index, weekday=day),
            )
    days.adjust(4)
    builder.attach(days)
    builder.attach(_search_again(kind))
    return builder.as_markup()


def build_campus_not_found_keyboard(kind: CampusKind) -> InlineKeyboardMarkup:
    return _search_again(kind).as_markup()


def build_now_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("schedule.now.refresh"), callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_NOW)
    )
    builder.button(
        text=_("schedule.my_schedule"), callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_MY_SCHEDULE)
    )
    builder.adjust(2)
    builder.attach(_study_navigation())
    return builder.as_markup()
