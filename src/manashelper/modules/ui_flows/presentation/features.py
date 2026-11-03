from dataclasses import dataclass, field

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from dishka import AsyncContainer

from manashelper.core.config import Settings
from manashelper.modules.advertisements.presentation.entrypoints import send_marketplace_menu
from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.models import DeadlineFilter
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.presentation.entrypoints import show_eders
from manashelper.modules.feedback.entrypoints import start_feedback
from manashelper.modules.food_menu.application.daily_menu import DailyMenuService
from manashelper.modules.food_menu.presentation.entrypoints import show_food_menu
from manashelper.modules.notifications.entrypoints import show_notifications
from manashelper.modules.notifications.settings import NotificationSettingsService
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.presentation.entrypoints import show_attendance, show_grades, show_obis_settings
from manashelper.modules.schedule.application.faculty import FacultyService
from manashelper.modules.schedule.presentation.entrypoints import show_course_tracking, show_timetable_menu
from manashelper.modules.study_week.application import GetStudyWeek
from manashelper.modules.study_week.entrypoints import show_study_week
from manashelper.modules.ui_flows.menus import EDERS_FEATURES, FEATURES
from manashelper.modules.users.application.user_contact import UserContactService
from manashelper.modules.users.presentation.entrypoints import show_phone_numbers
from manashelper.platform.telegram.entrypoints import show_settings
from ui_flows.application.locations import LocationService
from ui_flows.domain.state import RuntimeUser
from ui_flows.errors import FlowExecutionError


@dataclass(frozen=True, slots=True)
class TelegramFlowContext:
    message: Message = field(repr=False)
    state: FSMContext = field(repr=False)


async def open_feature(
    request: AsyncContainer, context: TelegramFlowContext, user: RuntimeUser, update_id: int, feature: str
) -> None:
    settings = await request.get(Settings)
    if feature not in FEATURES or (feature in EDERS_FEATURES and not settings.eders_enabled):
        raise FlowExecutionError("Feature is unavailable")
    if feature == "feedback" and user.id != settings.admin_chat_id:
        raise FlowExecutionError("Feature is unavailable")
    if context.message.chat.id != user.id or user.id != user.chat_id:
        raise FlowExecutionError("Feature handoff requires the owner's private chat")
    await context.state.clear()
    match feature:
        case "food_menu":
            await show_food_menu(context.message, await request.get(DailyMenuService))
        case "marketplace":
            await send_marketplace_menu(context.message, settings)
        case "settings":
            await show_settings(context.message)
        case "notifications":
            await show_notifications(context.message, user.id, await request.get(NotificationSettingsService))
        case "course_tracking":
            await show_course_tracking(context.message, await request.get(FacultyService))
        case "obis_credentials":
            await show_obis_settings(context.message, user.id, await request.get(ObisService))
        case "phone_numbers":
            await show_phone_numbers(context.message, user.id, await request.get(UserContactService))
        case "feedback":
            await start_feedback(context.message, context.state)
        case "schedule":
            await show_timetable_menu(context.message)
        case "attendance":
            await show_attendance(context.message, user.id, context.state, await request.get(ObisService))
        case "grades":
            await show_grades(context.message, user.id, context.state, await request.get(ObisService))
        case "study_week":
            await show_study_week(context.message, user.id, await request.get(GetStudyWeek))
        case "eders" | "eders_materials":
            selected = DeadlineFilter.MATERIALS if feature == "eders_materials" else DeadlineFilter.ALL
            await show_eders(
                context.message,
                user.id,
                context.state,
                await request.get(EdersService),
                await request.get(EdersTrackingService),
                selected,
            )
    await (await request.get(LocationService)).observe(
        user.id, user.chat_id, update_id, feature, await context.state.get_state()
    )
