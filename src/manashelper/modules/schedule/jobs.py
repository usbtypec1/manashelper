import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.schedule.application.course import CourseService
from manashelper.modules.schedule.application.sync_course import ScheduleChangeSender, SyncCourseTimetable
from manashelper.modules.schedule.presentation.sender import TelegramScheduleChangeSender
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService

logger = logging.getLogger(__name__)


async def sync_timetable_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            courses = await request_container.get(CourseService)
            course_ids = await courses.get_all_ids()
    except Exception:
        logger.exception("Failed to load course ids for timetable sync")
        return

    for course_id in course_ids:
        await _sync_course_timetable(container, bot, course_id)


async def _sync_course_timetable(container: AsyncContainer, bot: Bot, course_id: int) -> None:
    try:
        async with container() as request_container:
            service = await request_container.get(SyncCourseTimetable)
            locales = await request_container.get(LocaleService)
            themes = await request_container.get(ThemeService)
            sender: ScheduleChangeSender = TelegramScheduleChangeSender(bot, locales, themes)
            await service.execute(course_id, sender)
    except Exception:
        logger.exception("Failed to sync timetable for course %s", course_id)
