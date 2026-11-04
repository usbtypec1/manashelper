import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.core.config import get_settings
from manashelper.modules.advertisements.application.expiry import PublicationRemover
from manashelper.modules.advertisements.application.use_cases.expire_advertisements import ExpireAdvertisementsUseCase
from manashelper.modules.advertisements.presentation.publications import TelegramPublicationRemover

logger = logging.getLogger(__name__)


async def cleanup_expired_advertisements_job(container: AsyncContainer, bot: Bot) -> None:
    """Run expire_advertisements in its own request scope with the Telegram publication adapter."""
    try:
        publications: PublicationRemover = TelegramPublicationRemover(bot, get_settings())
        async with container(context={PublicationRemover: publications}) as request_container:
            expire_advertisements = await request_container.get(ExpireAdvertisementsUseCase)
            await expire_advertisements.execute()
    except Exception:
        logger.exception("Failed to clean up expired advertisements")
