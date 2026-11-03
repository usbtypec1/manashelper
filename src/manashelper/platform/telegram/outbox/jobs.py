import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.platform.telegram.outbox.worker import REQUEST_TIMEOUT, OutboxWorker

logger = logging.getLogger(__name__)


async def deliver_outbox_job(container: AsyncContainer, bot: Bot) -> int | None:
    processed = 0
    try:
        for _ in range(50):
            async with container() as request:
                worker = await request.get(OutboxWorker)
                claim = await worker.claim(bot.id, datetime.now(UTC))
            if claim is None:
                return processed
            error = None
            expired = claim.expires_at <= datetime.now(UTC)
            if not expired:
                try:
                    await bot(claim.method, request_timeout=REQUEST_TIMEOUT)
                except Exception as failure:
                    error = failure
            async with container() as request:
                worker = await request.get(OutboxWorker)
                if expired:
                    await worker.expire(claim, datetime.now(UTC))
                elif error:
                    await worker.fail(claim, error, bot.id, datetime.now(UTC))
                else:
                    await worker.complete(claim, datetime.now(UTC))
            processed += 1
        return processed
    except Exception as error:
        # A database/commit failure leaves a recoverable lease. Do not expose payloads.
        logger.error("Outbox worker cycle failed: %s", type(error).__name__)
        return None


async def run_outbox_worker(container: AsyncContainer, bot: Bot) -> None:
    while True:
        result = await deliver_outbox_job(container, bot)
        await asyncio.sleep(1.0 if result is None else 0.05)


async def cleanup_outbox_job(container: AsyncContainer) -> None:
    try:
        async with container() as request:
            worker = await request.get(OutboxWorker)
            await worker.cleanup()
    except Exception:
        logger.error("Outbox cleanup failed", exc_info=False)
