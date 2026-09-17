from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.repositories.food_menu_cleanup_settings_repository import FoodMenuCleanupSettingsRepository
from manashelper.repositories.scheduled_message_deletion_repository import ScheduledMessageDeletionRepository
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupOption, FoodMenuCleanupSettingsService
from manashelper.services.message_deletion import MessageDeletionService


def _make_service(session: AsyncSession) -> FoodMenuCleanupSettingsService:
    return FoodMenuCleanupSettingsService(
        FoodMenuCleanupSettingsRepository(session),
        MessageDeletionService(ScheduledMessageDeletionRepository(session)),
    )


async def test_get_option_defaults_to_three_hours_when_no_row_exists(session: AsyncSession) -> None:
    service = _make_service(session)
    assert await service.get_option(chat_id=700_001) is FoodMenuCleanupOption.HOURS_3


async def test_set_option_persists_the_new_choice(session: AsyncSession) -> None:
    service = _make_service(session)

    await service.set_option(700_002, FoodMenuCleanupOption.MINUTES_15)
    await session.flush()

    assert await service.get_option(700_002) is FoodMenuCleanupOption.MINUTES_15


async def test_schedule_cleanup_uses_the_configured_delay(session: AsyncSession) -> None:
    service = _make_service(session)
    scheduled_message_deletion_repository = ScheduledMessageDeletionRepository(session)

    await service.set_option(700_003, FoodMenuCleanupOption.MINUTES_15)
    await service.schedule_cleanup(700_003, [1, 2])
    await session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    due = await scheduled_message_deletion_repository.get_due_grouped_by_chat(now + timedelta(minutes=16))
    assert sorted(message_id for _, message_id in due[700_003]) == [1, 2]

    not_yet_due = await scheduled_message_deletion_repository.get_due_grouped_by_chat(now + timedelta(minutes=10))
    assert 700_003 not in not_yet_due


async def test_schedule_cleanup_does_nothing_when_disabled(session: AsyncSession) -> None:
    service = _make_service(session)
    scheduled_message_deletion_repository = ScheduledMessageDeletionRepository(session)

    await service.set_option(700_004, FoodMenuCleanupOption.DISABLED)
    await service.schedule_cleanup(700_004, [1])
    await session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    due = await scheduled_message_deletion_repository.get_due_grouped_by_chat(now + timedelta(days=365))
    assert 700_004 not in due
