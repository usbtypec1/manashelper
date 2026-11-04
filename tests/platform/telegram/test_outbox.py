from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.methods import SendMessage, SendPhoto, SendRichMessage
from aiogram.types import InputRichMessage
from sqlalchemy import select

from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.platform.telegram.outbox.models import OutboxMessage, OutboxRateBucket
from manashelper.platform.telegram.outbox.rate_limit import CHAT_BUCKET, GLOBAL_BUCKET
from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import METHOD_TYPES, OutboxService, is_night
from manashelper.platform.telegram.outbox.worker import MAX_FAILURES, OutboxWorker, retry_delay
from tests.modules.users.application_factories import build_bot_status_service


@pytest.fixture
async def context(session):
    session.add_all([User(id=983001, full_name="One"), User(id=983002, full_name="Two")])
    await session.flush()
    repository = OutboxRepository(session)
    status = build_bot_status_service(UserRepository(session))
    recipients = NotificationRecipientsQuery(NotificationSettingsRepository(session))
    return SimpleNamespace(
        session=session,
        repository=repository,
        status=status,
        service=OutboxService(repository, status),
        worker=OutboxWorker(repository, SimpleNamespace(execute=status.stop), recipients),
        recipients=recipients,
        now=datetime.now(UTC),
        bot_id=983000,
    )


async def enqueue(context, user_id=983001, **kwargs):
    return await context.service.enqueue(user_id, [SendMessage(chat_id=user_id, text="Hello <b>student</b>")], **kwargs)


async def rows(context):
    return list((await context.session.scalars(select(OutboxMessage).order_by(OutboxMessage.id))).all())


def freeze_enqueue_clock(monkeypatch, now):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz)

    monkeypatch.setattr("manashelper.platform.telegram.outbox.service.datetime", Clock)


@pytest.mark.parametrize(
    ("utc_time", "silent"),
    [("01:59:59", True), ("02:00:00", False), ("15:59:59", False), ("16:00:00", True), ("23:00:00", True)],
)
@pytest.mark.parametrize("category", ["broadcast", "notification"])
async def test_night_flag_is_persisted_for_all_methods(context, monkeypatch, utc_time, silent, category):
    now = datetime.fromisoformat(f"2099-01-01T{utc_time}+00:00")
    freeze_enqueue_clock(monkeypatch, now)
    assert is_night(now) is silent
    methods = [SendMessage(chat_id=983001, text="Text"), SendPhoto(chat_id=983001, photo="photo")]
    rich = SendRichMessage(chat_id=983001, rich_message=InputRichMessage(html="Rich text"))
    methods.append(rich)
    assert await context.service.enqueue(983001, methods, category=category)
    context.session.expire_all()
    message = (await rows(context))[0]
    assert len(message.methods) == 3
    for part in message.methods:
        assert part["data"]["disable_notification"] is silent
        assert METHOD_TYPES[part["method"]].model_validate(part["data"]).disable_notification is silent


async def test_daytime_preserves_explicit_silence_and_source_deduplication(context, monkeypatch):
    day = datetime(2099, 1, 1, 15, 59, 59, tzinfo=UTC)
    freeze_enqueue_clock(monkeypatch, day)
    assert await context.service.enqueue(983001, [SendMessage(chat_id=983001, text="Quiet", disable_notification=True)])
    assert (await rows(context))[0].methods[0]["data"]["disable_notification"] is True
    assert await enqueue(context, source_keys=["same-event"])
    freeze_enqueue_clock(monkeypatch, day + timedelta(seconds=1))
    assert await enqueue(context, source_keys=["same-event"])
    assert len(await rows(context)) == 2


async def test_daytime_queue_becomes_silent_at_night_and_stays_silent_on_morning_retry(context, monkeypatch):
    day = datetime(2099, 1, 1, 15, 59, 59, tzinfo=UTC)
    freeze_enqueue_clock(monkeypatch, day)
    await context.service.enqueue(
        983001, [SendPhoto(chat_id=983001, photo="photo"), SendMessage(chat_id=983001, text="Text")]
    )
    night = day + timedelta(seconds=1)
    photo = await context.worker.claim(context.bot_id, night)
    assert photo.method.disable_notification is True
    await context.worker.fail(photo, TelegramNetworkError(photo.method, "Retry"), context.bot_id, night)
    await context.session.flush()
    context.session.expire_all()
    assert all(part["data"]["disable_notification"] is True for part in (await rows(context))[0].methods)
    morning = datetime(2099, 1, 2, 2, tzinfo=UTC)
    recreated = OutboxWorker(
        OutboxRepository(context.session), SimpleNamespace(execute=context.status.stop), context.recipients
    )
    retry = await recreated.claim(context.bot_id, morning)
    assert retry.method.disable_notification is True
    await recreated.complete(retry, morning)
    text = await recreated.claim(context.bot_id, morning + timedelta(seconds=1))
    assert isinstance(text.method, SendMessage) and text.method.disable_notification is True


async def test_atomic_enqueue_rollback_and_deduplication(context):
    async with context.session.begin_nested() as scope:
        assert await enqueue(context, deduplication_key="first")
        assert await enqueue(context, deduplication_key="first")
        assert len(await rows(context)) == 1
        await scope.rollback()
    assert await rows(context) == []
    assert await enqueue(context, deduplication_key="first")
    assert len(await rows(context)) == 1


async def test_expiration_and_stopped_recipients_never_send(context):
    assert not await enqueue(context, expires_at=context.now - timedelta(seconds=1))
    with pytest.raises(ValueError, match="timezone"):
        await enqueue(context, expires_at=datetime(2099, 1, 1))
    assert await enqueue(context)
    await context.status.stop(983001)
    assert await context.worker.claim(context.bot_id, context.now + timedelta(seconds=1)) is None
    assert (await rows(context))[0].status == "cancelled"
    assert not await enqueue(context)


async def test_expired_row_does_not_block_the_next_recipient(context):
    await enqueue(context, expires_at=context.now + timedelta(seconds=1))
    await enqueue(context, 983002)
    claim = await context.worker.claim(context.bot_id, context.now + timedelta(seconds=2))
    assert claim.method.chat_id == 983002
    assert (await rows(context))[0].status == "expired"


async def test_token_bucket_persists_global_and_per_chat_budgets(context):
    now = context.now
    assert await context.repository.reserve(context.bot_id, 983001, now) == 0
    assert await context.repository.reserve(context.bot_id, 983001, now) == pytest.approx(1)
    assert await context.repository.reserve(context.bot_id, 983002, now) == 0
    assert await context.repository.reserve(context.bot_id, 983001, now + timedelta(seconds=1)) == 0
    for offset in range(10):
        wait = await context.repository.reserve(context.bot_id + 1, 900000 + offset, now)
        assert wait == (0 if offset < 5 else pytest.approx(0.05))
    assert GLOBAL_BUCKET.refill(0, now, now + timedelta(seconds=100)) == 5
    assert CHAT_BUCKET.refill(0, now, now - timedelta(seconds=1)) == 0


async def test_retry_after_survives_worker_recreation_and_pauses_other_recipients(context):
    await enqueue(context)
    now = context.now + timedelta(seconds=1)
    claim = await context.worker.claim(context.bot_id, now)
    await context.worker.fail(
        claim, TelegramRetryAfter(claim.method, "Flood control", retry_after=10), context.bot_id, now
    )
    await enqueue(context, 983002)
    recreated = OutboxWorker(
        OutboxRepository(context.session), SimpleNamespace(execute=context.status.stop), context.recipients
    )
    assert await recreated.claim(context.bot_id, now + timedelta(seconds=9)) is None
    message = (await rows(context))[0]
    assert message.status == "pending" and message.available_at >= now + timedelta(seconds=10)
    assert not await context.status.is_stopped(983001)
    assert await recreated.claim(context.bot_id, now + timedelta(seconds=12)) is not None


@pytest.mark.parametrize("failure_type", [TelegramServerError, TelegramNetworkError])
async def test_transient_failure_backoff_and_attempt_exhaustion(context, failure_type):
    await enqueue(context)
    now = context.now + timedelta(seconds=1)
    for failure in range(1, MAX_FAILURES + 1):
        claim = await context.worker.claim(context.bot_id, now)
        assert claim is not None
        await context.worker.fail(claim, failure_type(claim.method, "Synthetic failure"), context.bot_id, now)
        message = (await rows(context))[0]
        if failure < MAX_FAILURES:
            delay = (message.available_at - now).total_seconds()
            ceiling = min(300, 2 ** min(failure, 9))
            assert ceiling / 2 <= delay <= ceiling
            now = message.available_at + timedelta(seconds=1)
        else:
            assert message.status == "failed" and message.finished_at == now
    assert not await context.status.is_stopped(983001)


async def test_retry_cannot_outlive_expiration(context):
    await enqueue(context, expires_at=context.now + timedelta(seconds=5))
    now = context.now + timedelta(seconds=1)
    claim = await context.worker.claim(context.bot_id, now)
    await context.worker.fail(claim, TelegramRetryAfter(claim.method, "Flood", retry_after=30), context.bot_id, now)
    assert (await rows(context))[0].status == "expired"


@pytest.mark.parametrize("permanent", [False, True])
async def test_permanent_and_content_failures_are_terminal(context, permanent):
    await enqueue(context)
    now = context.now + timedelta(seconds=1)
    claim = await context.worker.claim(context.bot_id, now)
    failure = (
        TelegramForbiddenError(claim.method, "Forbidden: bot was blocked by the user")
        if permanent
        else TelegramBadRequest(claim.method, "Bad Request: can't parse entities")
    )
    await context.worker.fail(claim, failure, context.bot_id, now)
    message = (await rows(context))[0]
    assert message.status == "failed" and message.last_error == type(failure).__name__
    assert await context.status.is_stopped(983001) is permanent


async def test_multipart_checkpoint_and_chat_fifo(context):
    await context.service.enqueue(
        983001, [SendPhoto(chat_id=983001, photo="cached-photo"), SendMessage(chat_id=983001, text="Body")]
    )
    await enqueue(context)
    now = context.now + timedelta(seconds=1)
    photo = await context.worker.claim(context.bot_id, now)
    assert isinstance(photo.method, SendPhoto)
    await context.worker.complete(photo, now)
    text = await context.worker.claim(context.bot_id, now + timedelta(seconds=1))
    assert isinstance(text.method, SendMessage) and text.method.text == "Body"
    await context.worker.fail(
        text, TelegramServerError(text.method, "Failure"), context.bot_id, now + timedelta(seconds=1)
    )
    assert await context.worker.claim(context.bot_id, now + timedelta(seconds=1)) is None
    text_retry = await context.worker.claim(context.bot_id, now + timedelta(seconds=5))
    assert text_retry.id == photo.id and text_retry.method.text == "Body"
    await context.worker.complete(text_retry, now + timedelta(seconds=5))
    following = await context.worker.claim(context.bot_id, now + timedelta(seconds=6))
    assert following.id > photo.id
    assert (await rows(context))[0].status == "sent"


async def test_expired_lease_recovers_and_rejects_old_ack(context):
    await enqueue(context)
    now = context.now + timedelta(seconds=1)
    first = await context.worker.claim(context.bot_id, now)
    assert await context.worker.claim(context.bot_id, now + timedelta(seconds=1)) is None
    recovered = await context.worker.claim(context.bot_id, now + timedelta(seconds=61))
    assert recovered.id == first.id and recovered.token != first.token
    await context.worker.complete(first, now + timedelta(seconds=62))
    assert (await rows(context))[0].status == "processing"
    await context.worker.complete(recovered, now + timedelta(seconds=62))
    assert (await rows(context))[0].status == "sent"


async def test_daily_cleanup_keeps_pending_and_recent_terminal_records(context):
    await enqueue(context)
    await enqueue(context, 983002, expires_at=context.now + timedelta(days=3))
    now = context.now + timedelta(seconds=1)
    claim = await context.worker.claim(context.bot_id, now)
    await context.worker.complete(claim, now)
    await context.repository.cleanup(now + timedelta(hours=12))
    assert len(await rows(context)) == 2
    await context.repository.cleanup(now + timedelta(days=1, seconds=1))
    remaining = await rows(context)
    assert len(remaining) == 1 and remaining[0].user_id == 983002 and remaining[0].status == "pending"


async def test_source_cancellation_is_transactional(context):
    await enqueue(context, source_keys=["eders-event"])
    await context.service.cancel_sources(["eders-event"])
    assert (await rows(context))[0].status == "cancelled"
    assert await context.worker.claim(context.bot_id, context.now + timedelta(seconds=1)) is None


@pytest.mark.parametrize("category", ["broadcast", "exam_grades", "lesson_skips", "schedule"])
async def test_delivery_rechecks_preferences_changed_after_enqueue(context, category):
    await enqueue(context, category=category)
    settings = NotificationSettings(
        user_id=983001,
        broadcast_muted_until=context.now + timedelta(days=14),
        exam_grades_enabled=False,
        lesson_skips_enabled=False,
        schedule_changes_enabled=False,
    )
    context.session.add(settings)
    assert await context.worker.claim(context.bot_id, context.now + timedelta(seconds=1)) is None
    assert (await rows(context))[0].status == "cancelled"


async def test_concurrent_workers_claim_distinct_rows_and_only_committed_messages(engine):
    import asyncio

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_ids = [983101, 983102]
    bot_id = 983100

    def services(session):
        repository = OutboxRepository(session)
        status = build_bot_status_service(UserRepository(session))
        recipients = NotificationRecipientsQuery(NotificationSettingsRepository(session))
        return OutboxService(repository, status), OutboxWorker(
            repository, SimpleNamespace(execute=status.stop), recipients
        )

    try:
        async with sessions.begin() as setup:
            setup.add_all(User(id=user_id, full_name="Concurrent recipient") for user_id in user_ids)
        async with sessions() as producer, sessions() as observer:
            service, _ = services(producer)
            for user_id in user_ids:
                await service.enqueue(user_id, [SendMessage(chat_id=user_id, text="Committed only")])
            _, worker = services(observer)
            assert await worker.claim(bot_id, datetime.now(UTC)) is None
            await observer.commit()
            await producer.commit()

        async with sessions() as first, sessions() as second:
            _, first_worker = services(first)
            _, second_worker = services(second)
            claim = await first_worker.claim(bot_id, datetime.now(UTC))
            other_task = asyncio.create_task(second_worker.claim(bot_id, datetime.now(UTC)))
            await asyncio.sleep(0)
            await first.commit()
            other = await asyncio.wait_for(other_task, timeout=5)
            await second.commit()
            assert claim is not None and other is not None and claim.id != other.id
            assert {claim.method.chat_id, other.method.chat_id} == set(user_ids)
    finally:
        async with sessions.begin() as cleanup:
            await cleanup.execute(delete(User).where(User.id.in_(user_ids)))
            await cleanup.execute(delete(OutboxRateBucket).where(OutboxRateBucket.key.like(f"bot:{bot_id}%")))


def test_jitter_is_bounded_and_exponential_until_capped():
    for attempt in range(1, 15):
        ceiling = min(300, 2 ** min(attempt, 9))
        assert ceiling / 2 <= retry_delay(attempt) <= ceiling
