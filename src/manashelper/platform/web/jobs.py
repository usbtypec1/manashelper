import logging

from dishka import AsyncContainer

from manashelper.platform.web.auth import AdminAuthService

logger = logging.getLogger(__name__)


async def cleanup_admin_auth_job(container: AsyncContainer) -> None:
    try:
        async with container() as request:
            deleted = await (await request.get(AdminAuthService)).purge_expired()
        logger.info("Expired administrative authentication records removed: %d", deleted)
    except Exception:
        logger.exception("Administrative authentication cleanup failed")
