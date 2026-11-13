from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select

from manashelper.core.config import get_settings
from manashelper.localization.theme import Theme
from manashelper.modules.gamification.application.catalog import ACHIEVEMENT_KEYS
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase
from manashelper.modules.gamification.application.use_cases.record_attendance import RecordAttendanceUseCase
from manashelper.modules.gamification.application.use_cases.record_transcript import RecordTranscriptUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.presentation import sender as sender_module
from manashelper.modules.obis.application.models import (
    LessonAttendanceModel,
    Transcript,
    TranscriptCourse,
    TranscriptSemester,
)
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.outbox.models import OutboxMessage
from tests.modules.gamification.factories import build_awards


async def setup_user(session, *, enabled=True, stopped=False, locale="ru", theme=Theme.BASIC):
    session.add(User(id=991101, full_name="Award recipient", locale=locale, theme=theme.value, bot_stopped=stopped))
    await session.flush()
    repository = AchievementRepository(session)
    if enabled:
        await repository.set_enabled(991101, True)
    return repository


async def queued(session):
    return list((await session.scalars(select(OutboxMessage).where(OutboxMessage.user_id == 991101))).all())


async def test_all_achievement_sources_enqueue_once_on_first_award(session):
    repository = await setup_user(session)
    awards = build_awards(session)
    activity = RecordActivityUseCase(repository, awards)
    transcript = RecordTranscriptUseCase(repository, awards)
    attendance = RecordAttendanceUseCase(repository, awards)
    start = datetime(2026, 11, 1, 20, tzinfo=UTC)
    for index in range(100):
        await activity.execute(991101, "food", observed_at=start + timedelta(minutes=10 * index))
    for day in range(3):
        await activity.execute(991101, "grades", observed_at=start + timedelta(days=day))
    for _ in range(2):
        await activity.execute(991101, "published")
        for gpa in ("3.20", "2.80"):
            await transcript.execute(
                991101,
                "fixture-student",
                Transcript(
                    (
                        TranscriptSemester(
                            "2024-2025:fall", Decimal(30), Decimal(90), (TranscriptCourse("PHY", "Физика", "FF"),)
                        ),
                        TranscriptSemester(
                            "2024-2025:spring",
                            Decimal(30),
                            Decimal(90),
                            tuple(TranscriptCourse(f"C{code}", "Example", "AA") for code in range(3))
                            + (TranscriptCourse("C3", "Example", "F1"),),
                        ),
                        TranscriptSemester(
                            "2025-2026:fall", Decimal(30), Decimal(90), (TranscriptCourse("PHY", "Физика", "BB"),)
                        ),
                        TranscriptSemester("2025-2026:spring", None, None, ()),
                    ),
                    Decimal(gpa),
                ),
            )
        await attendance.execute(
            991101,
            "fixture-student",
            [LessonAttendanceModel("Subject", str(index), 20, None, None, None) for index in range(5)],
        )
        await attendance.execute(
            991101,
            "fixture-student",
            [LessonAttendanceModel("Subject", "0", 0, 0, None, None)],
            observed_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
    for _ in range(100):
        await activity.execute(991101, "rating")
    # Repeated food and night checks after the thresholds must not notify again.
    await activity.execute(991101, "food", observed_at=start + timedelta(days=4))
    await activity.execute(991101, "grades", observed_at=start + timedelta(days=3))
    rows = await queued(session)
    assert len(rows) == len(ACHIEVEMENT_KEYS) == 15
    assert {row.deduplication_key for row in rows} == {f"achievement:991101:{key}" for key in ACHIEVEMENT_KEYS}
    assert set(await repository.get_awards(991101)) == set(ACHIEVEMENT_KEYS)
    assert all(row.category == "achievement" and row.status == "pending" for row in rows)
    assert all(row.methods[0]["method"] == "sendMessage" for row in rows)
    assert all(row.methods[0]["data"]["chat_id"] == 991101 for row in rows)


async def test_award_and_notification_roll_back_together_and_retry(session):
    repository = await setup_user(session)
    activity = RecordActivityUseCase(repository, build_awards(session))
    async with session.begin_nested() as transaction:
        await activity.execute(991101, "published")
        assert len(await queued(session)) == 1
        assert "seller" in await repository.get_awards(991101)
        await transaction.rollback()
    assert await queued(session) == []
    assert await repository.get_awards(991101) == {}
    await activity.execute(991101, "published")
    assert len(await queued(session)) == 1
    assert "seller" in await repository.get_awards(991101)


async def test_enqueue_failure_propagates_and_does_not_lose_award_notification(session, monkeypatch):
    from manashelper.platform.telegram.outbox.repository import OutboxRepository

    repository = await setup_user(session)
    activity = RecordActivityUseCase(repository, build_awards(session))
    with monkeypatch.context() as patch:
        patch.setattr(OutboxRepository, "add", AsyncMock(side_effect=RuntimeError("Queue unavailable")))
        with pytest.raises(RuntimeError, match="Queue unavailable"):
            async with session.begin_nested():
                await activity.execute(991101, "published")
    assert await repository.get_awards(991101) == {}
    assert await queued(session) == []
    await activity.execute(991101, "published")
    assert len(await queued(session)) == 1


@pytest.mark.parametrize("stopped", [False, True])
async def test_disabled_and_stopped_users_do_not_receive_notifications(session, stopped):
    repository = await setup_user(session, enabled=stopped, stopped=stopped)
    awards = build_awards(session)
    await awards.execute(991101, "seller", datetime.now(UTC))
    await awards.execute(991101, "pokemon", datetime.now(UTC))
    assert await queued(session) == []
    assert set(await repository.get_awards(991101)) == ({"seller"} if stopped else set())


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
@pytest.mark.parametrize("theme", list(Theme))
async def test_notification_uses_recipient_locale_theme_and_escaped_copy(session, monkeypatch, locale, theme):
    await setup_user(session, locale=locale, theme=theme)
    original = sender_module.achievement_strings
    with i18n.context(), i18n.use_locale(locale), i18n.use_theme(theme):
        name, description = original()["seller"]
        expected = i18n.gettext("gamification.award_notification").format(name=name, description=description)
    assert "gamification." not in expected

    def strings():
        assert i18n.current_locale == locale and i18n.current_theme == theme
        return original()

    monkeypatch.setattr(sender_module, "achievement_strings", strings)
    # Notification rendering must override the initiating update's context.
    with i18n.context(), i18n.use_locale("tr" if locale != "tr" else "en"), i18n.use_theme(Theme.BASIC):
        await build_awards(session).execute(991101, "seller", datetime.now(UTC))
    assert (await queued(session))[0].methods[0]["data"]["text"] == expected


async def test_notification_escapes_catalog_values_before_html_interpolation(session, monkeypatch):
    await setup_user(session)
    monkeypatch.setattr(sender_module, "achievement_strings", lambda: {"seller": ("<seller>", "A & B <condition>")})
    await build_awards(session).execute(991101, "seller", datetime.now(UTC))
    text = (await queued(session))[0].methods[0]["data"]["text"]
    assert "<b>&lt;seller&gt;</b>" in text
    assert "A &amp; B &lt;condition&gt;" in text


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
@pytest.mark.parametrize("public_url", ["https://example.com", None])
async def test_notification_persists_localized_web_app_button_in_outbox(session, monkeypatch, locale, public_url):
    monkeypatch.setattr(get_settings(), "public_url", public_url)
    await setup_user(session, locale=locale)
    await build_awards(session).execute(991101, "seller", datetime.now(UTC))
    # Recreate the Telegram method from persisted JSON, as the outbox worker does.
    method = SendMessage.model_validate((await queued(session))[0].methods[0]["data"])
    if public_url:
        assert method.reply_markup is not None
        buttons = [button for row in method.reply_markup.inline_keyboard for button in row]
        [button] = [button for button in buttons if button.web_app is not None]
        assert button.web_app.url == "https://example.com/app/"
        with i18n.context(), i18n.use_locale(locale):
            assert button.text == i18n.gettext("gamification.view_all")
            [menu] = [button for button in buttons if button.callback_data is not None]
            assert menu.text == i18n.gettext("common.back_to_menu")
            assert menu.callback_data == "navigation:main"
        assert button.url is None and button.callback_data is None
    else:
        assert method.reply_markup is None
