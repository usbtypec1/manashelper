import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.application.use_cases.poll_eders_user import PollEdersUserUseCase
from manashelper.modules.eders.errors import EdersFetchError, EdersParseError, EdersUnsafeUrlError
from manashelper.modules.eders.presentation.sender import TelegramEdersNotificationSender
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.telegram.outbox.service import OutboxService

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
                poll_eders_user = await request.get(PollEdersUserUseCase)
                themes = await request.get(ThemeQuery)
                outbox = await request.get(OutboxService)
                await poll_eders_user.execute(user_id, TelegramEdersNotificationSender(outbox, themes))
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
            logger.exception("Failed to poll_eders_user eders for user %s", user_id)
