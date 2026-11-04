import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.schedule.application.course import CourseQuery
from manashelper.modules.schedule.application.sync_course import ScheduleChangeSender
from manashelper.modules.schedule.application.use_cases.sync_course_timetable import SyncCourseTimetableUseCase
from manashelper.modules.schedule.presentation.sender import TelegramScheduleChangeSender
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.telegram.outbox.service import OutboxService

logger = logging.getLogger(__name__)


async def sync_timetable_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            courses = await request_container.get(CourseQuery)
            course_ids = await courses.get_all_ids()
    except Exception:
        logger.exception("Failed to load course ids for timetable sync")
        return

    for course_id in course_ids:
        await _sync_course_timetable(container, bot, course_id)


async def _sync_course_timetable(container: AsyncContainer, bot: Bot, course_id: int) -> None:
    try:
        async with container() as request_container:
            sync_course_timetable = await request_container.get(SyncCourseTimetableUseCase)
            locales = await request_container.get(LocaleQuery)
            themes = await request_container.get(ThemeQuery)
            outbox = await request_container.get(OutboxService)
            sender: ScheduleChangeSender = TelegramScheduleChangeSender(outbox, locales, themes)
            await sync_course_timetable.execute(course_id, sender)
    except Exception:
        logger.exception("Failed to sync timetable for course %s", course_id)
