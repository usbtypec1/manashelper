import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.platform.telegram.outbox.worker import REQUEST_TIMEOUT, ClaimedMessage, OutboxWorker

logger = logging.getLogger(__name__)


async def _send_claim(bot: Bot, claim: ClaimedMessage) -> tuple[bool, Exception | None]:
    if claim.expires_at <= datetime.now(UTC):
        return True, None
    try:
        await bot(claim.method, request_timeout=REQUEST_TIMEOUT)
    except Exception as error:
        return False, error
    return False, None


async def deliver_outbox_job(container: AsyncContainer, bot: Bot) -> int | None:
    processed = 0
    try:
        while processed < 50:
            async with container() as request:
                worker = await request.get(OutboxWorker)
                claims = await worker.claim_batch(bot.id, datetime.now(UTC), limit=50 - processed)
            if not claims:
                return processed
            # Lease and rate reservations commit before starting HTTP. Each
            # batch contains at most one request per recipient.
            async with asyncio.TaskGroup() as batch:
                sends: dict[asyncio.Future[tuple[bool, Exception | None]], ClaimedMessage] = {
                    batch.create_task(_send_claim(bot, claim)): claim for claim in claims
                }
                async for send in asyncio.as_completed(sends):
                    claim = sends[send]
                    expired, error = send.result()
                    async with container() as request:
                        worker = await request.get(OutboxWorker)
                        now = datetime.now(UTC)
                        if expired:
                            await worker.expire(claim, now)
                        elif error is not None:
                            await worker.fail(claim, error, bot.id, now)
                        else:
                            await worker.complete(claim, now)
            processed += len(claims)
        return processed
    except Exception as error:
        # A database/commit failure leaves a recoverable lease. Do not expose payloads.
        logger.error("Outbox worker cycle failed: %s", type(error).__name__)
        return None


async def run_outbox_worker(container: AsyncContainer, bot: Bot) -> None:
    while True:
        result = await deliver_outbox_job(container, bot)
        if result is None:
            await asyncio.sleep(1)
        elif result == 0:
            try:
                async with container() as request:
                    worker = await request.get(OutboxWorker)
                    delay = await worker.next_poll_delay(datetime.now(UTC))
            except Exception as error:
                logger.error("Could not read the next outbox attempt: %s", type(error).__name__)
                delay = 1.0
            await asyncio.sleep(delay)


async def cleanup_outbox_job(container: AsyncContainer) -> None:
    try:
        async with container() as request:
            worker = await request.get(OutboxWorker)
            await worker.cleanup()
    except Exception:
        logger.error("Outbox cleanup failed", exc_info=False)
