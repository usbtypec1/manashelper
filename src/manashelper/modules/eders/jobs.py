import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.eders.application.polling import PollEdersUser
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.errors import EdersFetchError, EdersParseError, EdersUnsafeUrlError
from manashelper.modules.eders.presentation.sender import TelegramEdersNotificationSender
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError

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
                poll = await request.get(PollEdersUser)
                await poll.execute(user_id, TelegramEdersNotificationSender(bot))
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
