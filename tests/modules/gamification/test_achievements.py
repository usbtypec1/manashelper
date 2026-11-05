from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.filters import CommandObject
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.core.config import get_settings
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.grant_pokemon import GrantPokemonUseCase
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase
from manashelper.modules.gamification.application.use_cases.record_attendance import RecordAttendanceUseCase
from manashelper.modules.gamification.application.use_cases.record_transcript import RecordTranscriptUseCase
from manashelper.modules.gamification.application.use_cases.set_gamification_enabled import (
    SetGamificationEnabledUseCase,
)
from manashelper.modules.gamification.infrastructure.models.achievement import UserAchievement
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.presentation import router
from manashelper.modules.obis.application.models import LessonAttendanceModel, Transcript, TranscriptSemester
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.navigation import build_main_keyboard


async def seed(session: AsyncSession, user_id: int = 991001) -> AchievementRepository:
    session.add(User(id=user_id, full_name="Synthetic achiever", student_number="fixture-student"))
    await session.flush()
    repo = AchievementRepository(session)
    await repo.set_enabled(user_id, True)
    return repo


async def test_food_cooldown_is_since_last_counted_view_and_both_thresholds(session):
    repo = await seed(session)
    record = RecordActivityUseCase(repo)
    start = datetime(2026, 11, 1, tzinfo=UTC)
    for index in range(100):
        now = start + timedelta(minutes=10 * index)
        await record.execute(991001, "food", observed_at=now)
        await record.execute(991001, "food", observed_at=now + timedelta(minutes=9, seconds=59))
    assert (await repo.get_progress(991001))[0] == 100
    assert set(await repo.get_awards(991001)) == {"foodie", "cafeteria_boss"}


async def test_night_window_bishkek_dates_duplicates_and_gaps(session):
    repo = await seed(session)
    record = RecordActivityUseCase(repo)
    # 20:00 UTC is 02:00 the next day in Bishkek; 23:00 is excluded.
    start = datetime(2026, 10, 31, 20, tzinfo=UTC)
    await record.execute(991001, "grades", observed_at=start - timedelta(seconds=1))
    assert (await repo.get_progress(991001))[1] == 0
    for day in (0, 1, 1, 3):
        await record.execute(991001, "grades", observed_at=start + timedelta(days=day))
    assert (await repo.get_progress(991001))[1] == 1
    await record.execute(991001, "grades", observed_at=start + timedelta(days=4, hours=3))
    assert (await repo.get_progress(991001))[1] == 1
    for day in (4, 5):
        await record.execute(991001, "grades", observed_at=start + timedelta(days=day))
    assert "night_owl" in await repo.get_awards(991001)


async def test_manual_award_authorization_and_idempotency(session):
    repo = await seed(session)
    grant = GrantPokemonUseCase(repo, get_settings())
    with pytest.raises(PermissionError):
        await grant.execute(991001, admin_chat_id=1, actor_id=5)
    assert await grant.execute(991001, admin_chat_id=get_settings().admin_chat_id, actor_id=5)
    assert not await grant.execute(991001, admin_chat_id=get_settings().admin_chat_id, actor_id=5)


@pytest.mark.parametrize("gpa,award", [("3.20", "comeback"), ("2.80", "fall")])
async def test_official_transcript_thresholds_decimal_and_account_marker(session, gpa, award):
    repo = await seed(session)
    record = RecordTranscriptUseCase(repo)
    transcript = Transcript(
        (
            TranscriptSemester("2025-2026:spring", Decimal(30), Decimal(90), ("F1", "FF")),
            TranscriptSemester("2026-2027:fall", None, None, ()),
        ),
        Decimal(gpa),
    )
    await record.execute(991001, "fixture-student", transcript)
    assert set(await repo.get_awards(991001)) == {"formula_one", "champion", award}
    profile = await GamificationQuery(repo).profile(991001)
    assert all(card.available for card in profile.achievements if card.key != "thin_ice")
    user = await session.get(User, 991001)
    user.student_number = "another-student"
    await session.flush()
    assert not (await repo.academic_progress(991001))[0]


async def test_first_semester_has_no_invented_baseline(session):
    repo = await seed(session)
    transcript = Transcript((TranscriptSemester("2026-2027:fall", Decimal(30), Decimal(90), ()),), Decimal(3))
    await RecordTranscriptUseCase(repo).execute(991001, "fixture-student", transcript)
    profile = await GamificationQuery(repo).profile(991001)
    assert all(card.blocked_reason == "baseline" for card in profile.achievements if card.key in {"comeback", "fall"})
    assert not await repo.get_awards(991001)


async def test_ranking_ties_top_ten_and_own_position(session):
    # This fixture rolls the deletion back, preserving existing local awards.
    await session.execute(delete(UserAchievement))
    repo = await seed(session)
    now = datetime.now(UTC)
    for index in range(12):
        user_id = 991002 + index
        await seed(session, user_id)
        await repo.award(user_id, "seller", now + timedelta(seconds=index))
    await repo.award(991001, "seller", now)
    await repo.award(991001, "pokemon", now)
    rows = await repo.ranking()
    assert len(rows) == 10
    assert rows[0][0] == 991001 and rows[0][3] == 1
    assert all(row[3] == 2 for row in rows[1:])
    assert (await repo.ranking(991013))[0][3] == 2


async def test_default_off_blocks_all_writers_and_opt_out_preserves_progress(session):
    session.add(User(id=991001, full_name="Disabled", student_number="fixture-student"))
    await session.flush()
    repo = AchievementRepository(session)
    query = GamificationQuery(repo)
    access = SetGamificationEnabledUseCase(repo, get_settings())
    activity = RecordActivityUseCase(repo)
    transcript = Transcript((TranscriptSemester("term", None, None, ("AA", "AA", "AA", "F1")),), Decimal(3))
    assert not await query.is_enabled(991001)
    await activity.execute(991001, "food")
    await activity.execute(991001, "grades")
    await activity.execute(991001, "published")
    await RecordTranscriptUseCase(repo).execute(991001, "fixture-student", transcript)
    await RecordAttendanceUseCase(repo).execute(991001, "fixture-student", [])
    assert not await repo.award(991001, "pokemon", datetime.now(UTC))
    assert await repo.get_progress(991001) == (0, 0, None)
    assert not await repo.get_awards(991001)
    assert not (await repo.academic_progress(991001))[0]
    with pytest.raises(LookupError):
        await GrantPokemonUseCase(repo, get_settings()).execute(
            991001, admin_chat_id=get_settings().admin_chat_id, actor_id=5
        )
    with pytest.raises(PermissionError):
        await access.execute(991001, True, admin_chat_id=0)
    with pytest.raises(LookupError):
        await access.execute(991099, True, admin_chat_id=get_settings().admin_chat_id)
    await access.execute(991001, True, admin_chat_id=get_settings().admin_chat_id)
    assert await query.is_enabled(991001)
    await activity.execute(991001, "food")
    await activity.execute(991001, "published")
    assert (await repo.ranking(991001))[0][2] == 1
    await access.execute(991001, False, admin_chat_id=get_settings().admin_chat_id)
    await activity.execute(991001, "food", observed_at=datetime.now(UTC) + timedelta(hours=1))
    assert not await repo.ranking(991001)
    assert (await repo.get_progress(991001))[0] == 1
    assert set(await repo.get_awards(991001)) == {"seller"}
    await access.execute(991001, True, admin_chat_id=get_settings().admin_chat_id)
    assert (await repo.ranking(991001))[0][2] == 1


async def test_aa_requires_three_in_same_semester_and_progress_uses_best_semester(session):
    repo = await seed(session)
    record = RecordTranscriptUseCase(repo)
    semesters = (
        TranscriptSemester("spring", Decimal(30), Decimal(90), ("AA", "AA")),
        TranscriptSemester("fall", None, None, ("AA",)),
    )
    await record.execute(991001, "fixture-student", Transcript(semesters, Decimal(3)))
    assert "eldin_balasy" not in await repo.get_awards(991001)
    card = next(
        card for card in (await GamificationQuery(repo).profile(991001)).achievements if card.key == "eldin_balasy"
    )
    assert (card.current, card.target, card.available) == (2, 3, True)
    semesters = (TranscriptSemester("spring", Decimal(30), Decimal(90), ("AA", "AA", "AA")), semesters[1])
    await record.execute(991001, "fixture-student", Transcript(semesters, Decimal(3)))
    before = await repo.get_awards(991001)
    assert "eldin_balasy" in before
    await record.execute(991001, "fixture-student", Transcript(semesters, Decimal(3)))
    assert await repo.get_awards(991001) == before


async def test_attendance_counts_distinct_subjects_theory_or_practice_in_one_snapshot(session):
    repo = await seed(session)
    record = RecordAttendanceUseCase(repo)
    lessons = [
        LessonAttendanceModel("Theory", "A", 18.75, None, None, None),
        LessonAttendanceModel("Practice", "B", None, 18.75, None, None),
        LessonAttendanceModel("Both", "C", 25, 25, None, None),
        LessonAttendanceModel("Duplicate", "C", 25, 25, None, None),
        LessonAttendanceModel("Below", "D", 18.74, 18.74, None, None),
        LessonAttendanceModel("Missing", "E", None, None, None, None),
    ]
    await record.execute(991001, "fixture-student", lessons)
    assert await repo.attendance_progress(991001) == (True, 3)
    assert not await repo.get_awards(991001)
    # Another snapshot must replace counts rather than accumulate earlier subjects.
    await record.execute(991001, "fixture-student", [LessonAttendanceModel("New", "Z", 20, None, None, None)])
    assert await repo.attendance_progress(991001) == (True, 1)
    lessons += [
        LessonAttendanceModel("Fourth", "F", 19, None, None, None),
        LessonAttendanceModel("Fifth", "G", None, 20, None, None),
    ]
    await record.execute(991001, "fixture-student", lessons)
    assert set(await repo.get_awards(991001)) == {"thin_ice"}
    card = next(card for card in (await GamificationQuery(repo).profile(991001)).achievements if card.key == "thin_ice")
    assert (card.current, card.target, card.available) == (5, 5, True)
    user = await session.get(User, 991001)
    user.student_number = "changed-account"
    await session.flush()
    assert await repo.attendance_progress(991001) == (False, 0)
    assert "thin_ice" in await repo.get_awards(991001)


async def test_admin_command_and_hidden_keyboard_for_disabled_user(session, monkeypatch):
    repo = await seed(session)
    settings = get_settings()
    monkeypatch.setattr(settings, "public_url", "https://example.com")
    access = SetGamificationEnabledUseCase(repo, settings)
    message = SimpleNamespace(chat=SimpleNamespace(id=0), from_user=SimpleNamespace(id=10), answer=AsyncMock())
    command = CommandObject(command="gamification", args="991001 off")
    with i18n.context(), i18n.use_locale("ru"):
        # A foreign chat cannot change access, even if it knows the command and user ID.
        await router.set_gamification(message, command, access, settings)
        assert await repo.is_enabled(991001)
        message.answer.assert_not_awaited()
        message.chat.id = settings.admin_chat_id
        await router.set_gamification(message, command, access, settings)
        assert not await repo.is_enabled(991001)
        labels = [button.text for row in build_main_keyboard().keyboard for button in row]
        assert i18n.gettext("menu.achievements") not in labels
        command = CommandObject(command="gamification", args="991001 on")
        await router.set_gamification(message, command, access, settings)
        assert await repo.is_enabled(991001)
        labels = [button.text for row in build_main_keyboard(achievements_enabled=True).keyboard for button in row]
        assert i18n.gettext("menu.achievements") in labels


async def test_transcript_fetch_is_skipped_for_disabled_users(session):
    from manashelper.modules.obis.application.use_cases.refresh_obis_transcript import RefreshObisTranscriptUseCase

    repo = await seed(session)
    await repo.set_enabled(991001, False)
    source, credentials, store = AsyncMock(), AsyncMock(), AsyncMock()
    refresh = RefreshObisTranscriptUseCase(
        credentials, store, source, RecordTranscriptUseCase(repo), GamificationQuery(repo)
    )
    await refresh.execute(991001)
    source.fetch_transcript.assert_not_awaited()
    store.lock.assert_not_awaited()
