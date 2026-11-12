import logging

from dishka import AsyncContainer

from manashelper.platform.telegram.webhook_service import WebhookReceiptService

logger = logging.getLogger(__name__)


async def cleanup_webhook_receipts_job(container: AsyncContainer) -> None:
    try:
        async with container() as request:
            receipts = await request.get(WebhookReceiptService)
            await receipts.cleanup()
    except Exception:
        logger.error("Webhook receipt cleanup failed", exc_info=False)
