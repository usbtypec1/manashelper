import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import LinkPreviewOptions
from dishka import AsyncContainer

from manashelper.localization.i18n import i18n
from manashelper.scraping.eders_client import EdersFetchError
from manashelper.scraping.eders_parser import EdersParseError
from manashelper.scraping.eders_urls import EdersUnsafeUrlError
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.eders import EdersService
from manashelper.services.eders_formatter import format_eders_event
from manashelper.services.eders_tracking import EdersTrackingService
from manashelper.services.locale import LocaleService
from manashelper.services.obis import UserHasNoCredentialsError, UserNotFoundError

logger = logging.getLogger(__name__)


async def poll_eders_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request:
            tracking = await request.get(EdersTrackingService)
            user_ids = await tracking.get_poll_user_ids()
    except Exception:
        logger.exception("Failed to load eders recipients")
        return
    for user_id in user_ids:
        try:
            async with container() as request:
                service = await request.get(EdersService)
                tracking = await request.get(EdersTrackingService)
                locale_service = await request.get(LocaleService)
                await service.get_snapshot(user_id)
                locale = await locale_service.get_locale(user_id)
                for event in await tracking.pending_events(user_id, datetime.now(UTC)):
                    with i18n.context(), i18n.use_locale(locale.value):
                        text = format_eders_event(event)
                    try:
                        await bot.send_message(user_id, text, link_preview_options=LinkPreviewOptions(is_disabled=True))
                    except TelegramAPIError:
                        logger.warning("Failed to send eders notification to user %s", user_id, exc_info=True)
                        continue
                    await tracking.mark_sent(user_id, event.key, datetime.now(UTC))
        except (
            UserNotFoundError,
            UserHasNoCredentialsError,
            ObisLoginError,
            ObisParseError,
            EdersFetchError,
            EdersParseError,
            EdersUnsafeUrlError,
        ):
            logger.warning("Could not refresh eders for user %s", user_id)
        except Exception:
            logger.exception("Failed to poll eders for user %s", user_id)
