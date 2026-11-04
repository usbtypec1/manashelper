import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Message

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.eders.application.models import ActivityKind, EdersSnapshot
from manashelper.modules.eders.application.tracking import EdersEvent
from manashelper.modules.eders.application.use_cases.set_activity_completion import SetActivityCompletionUseCase
from manashelper.modules.eders.errors import (
    EdersCompletionUnavailableError,
    EdersFetchError,
    EdersLoginError,
    EdersSnapshotNotReadyError,
)
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.eders.presentation.callbacks import EdersCompletionCallback
from manashelper.modules.eders.presentation.keyboards import build_eders_completion_keyboard
from manashelper.modules.eders.presentation.router import on_eders_completion
from manashelper.modules.eders.presentation.sender import TelegramEdersNotificationSender
from manashelper.platform.i18n.catalog import i18n
from tests.modules.eders.factories import NOW, item


@pytest.fixture(autouse=True)
def english():
    with i18n.context(), i18n.use_locale("en"):
        yield


def scenario(completed=False):
    credentials, client, tracking = AsyncMock(), AsyncMock(), AsyncMock()
    credentials.get_student_number.return_value = "fake-student"
    credentials.get_credentials.return_value = SimpleNamespace(plain_password="fake-password")
    tracking.get_snapshot.return_value = EdersSnapshot((item(manual_completion=True, completed=completed),), NOW)
    return SetActivityCompletionUseCase(credentials, client, tracking)


@pytest.mark.parametrize("completed", [True, False])
async def test_use_case_updates_only_after_remote_success_and_uses_target_state(completed):
    service = scenario(not completed)
    marker = hashlib.sha256(b"fake-student").hexdigest()
    calls = []
    service.eders_client.set_activity_completion.side_effect = lambda *args: calls.append("remote")
    service.tracking.set_activity_completion.side_effect = lambda *args: calls.append("local")
    await service.execute(42, 20, completed)
    assert calls == ["remote", "local"]
    service.tracking.lock.assert_awaited_once_with(42)
    service.tracking.get_snapshot.assert_awaited_once_with(42, marker)
    service.eders_client.set_activity_completion.assert_awaited_once_with("fake-student", 20, completed)
    service.tracking.set_activity_completion.assert_awaited_once_with(42, marker, 20, completed)
    service.credentials.get_credentials.assert_not_awaited()


@pytest.mark.parametrize("completed", [True, False])
async def test_repeated_target_state_still_updates_remote_without_inverting(completed):
    service = scenario(completed)
    await service.execute(42, 20, completed)
    await service.execute(42, 20, completed)
    assert service.eders_client.set_activity_completion.await_count == 2
    assert all(
        call.args == ("fake-student", 20, completed)
        for call in service.eders_client.set_activity_completion.await_args_list
    )


@pytest.mark.parametrize("activity", [item(id=999), item(), item(kind=ActivityKind.RESOURCE, manual_completion=True)])
async def test_foreign_missing_or_automatic_activity_is_rejected_before_http(activity):
    service = scenario()
    service.tracking.get_snapshot.return_value = EdersSnapshot((activity,), NOW)
    with pytest.raises(EdersCompletionUnavailableError):
        await service.execute(42, 20, True)
    service.eders_client.set_activity_completion.assert_not_awaited()


@pytest.mark.parametrize("error", [EdersFetchError, EdersSnapshotNotReadyError])
async def test_failed_completion_preserves_local_state(error):
    service = scenario()
    if error is EdersFetchError:
        service.eders_client.set_activity_completion.side_effect = error
    else:
        service.tracking.get_snapshot.side_effect = error
    with pytest.raises(error):
        await service.execute(42, 20, True)
    service.tracking.set_activity_completion.assert_not_awaited()
    service.credentials.get_credentials.assert_not_awaited()


async def test_only_direct_login_failure_decrypts_obis_password():
    service = scenario()
    service.eders_client.set_activity_completion.side_effect = [EdersLoginError(), None]
    await service.execute(42, 20, True)
    service.credentials.get_credentials.assert_awaited_once_with(42)
    assert service.eders_client.set_activity_completion.await_args_list[-1].args == (
        "fake-student",
        20,
        True,
        "fake-password",
    )


async def test_persisted_toggle_cancels_reminders_and_can_reopen(tracking, outbox, session):
    now = datetime.now(UTC)
    activity = item(manual_completion=True, closes=replace(item().closes, instant=now + timedelta(days=3)))
    snapshot = await tracking.observe(980_001, "account", EdersSnapshot((activity,), now))
    events = await EdersRepository(session).get_notifications(980_001)
    assert events
    assert await outbox.enqueue(
        980_001, [SendMessage(chat_id=980_001, text="Reminder")], source_keys=[events[0].event_key]
    )
    await session.flush()
    await tracking.set_activity_completion(980_001, "account", 20, True)
    saved = await tracking.get_snapshot(980_001, "account")
    assert saved.activities[0].completed and saved.fetched_at == snapshot.fetched_at
    assert all(event.cancelled for event in events)
    assert await tracking.pending_events(980_001, now + timedelta(days=2)) == []
    from sqlalchemy import select

    from manashelper.platform.telegram.outbox.models import OutboxMessage

    queued = (await session.execute(select(OutboxMessage).where(OutboxMessage.user_id == 980_001))).scalars().all()
    assert queued and all(delivery.status == "cancelled" for delivery in queued)
    await tracking.set_activity_completion(980_001, "account", 20, False)
    reopened = await tracking.get_snapshot(980_001, "account")
    assert not reopened.activities[0].completed and reopened.fetched_at == snapshot.fetched_at
    await tracking.observe(980_001, "account", replace(reopened, fetched_at=now + timedelta(minutes=15)))
    assert await tracking.pending_events(980_001, now + timedelta(days=2))


def callback_message(completed=False):
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = SimpleNamespace(id=42)
    callback.answer = AsyncMock()
    callback.message = AsyncMock(spec=Message)
    callback.message.chat = SimpleNamespace(id=42)
    callback.message.text = "Reminder"
    callback.message.html_text = (
        '<b>Course</b>\n<a href="https://eders.manas.edu.kg/mod/quiz/view.php?id=20">Task &amp; title</a>'
    )
    if completed:
        callback.message.html_text += "\n\n[marked as done]"
    callback.message.reply_markup = build_eders_completion_keyboard(20, completed)
    callback.message.edit_text = AsyncMock()
    return callback


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("completed", [True, False])
async def test_callback_alerts_then_switches_button_preserving_message_html(locale, completed):
    callback = callback_message(not completed)
    service = AsyncMock()
    order = []
    callback.answer.side_effect = lambda *args, **kwargs: order.append("alert")
    callback.message.edit_text.side_effect = lambda *args, **kwargs: order.append("edit")
    with i18n.use_locale(locale.value):
        await on_eders_completion(callback, EdersCompletionCallback(activity_id=20, completed=completed), service)
        alert = i18n.gettext("eders.completion_done" if completed else "eders.completion_undone")
        callback.answer.assert_awaited_once_with(alert, show_alert=True)
        call = callback.message.edit_text.call_args
        assert call.args[0].startswith("<b>Course</b>\n<a href=") and "Task &amp; title</a>" in call.args[0]
        assert (
            call.args[0].endswith(i18n.gettext("eders.marked_done"))
            if completed
            else "marked as done" not in call.args[0]
        )
        button = call.kwargs["reply_markup"].inline_keyboard[0][0]
        assert button.text == i18n.gettext("eders.mark_undone" if completed else "eders.mark_done")
        assert EdersCompletionCallback.unpack(button.callback_data).completed is not completed
    assert order == ["alert", "edit"]
    service.execute.assert_awaited_once_with(42, 20, completed)


@pytest.mark.parametrize("error", [EdersFetchError, EdersCompletionUnavailableError, EdersSnapshotNotReadyError])
async def test_callback_failure_keeps_text_and_button(error):
    callback = callback_message()
    await on_eders_completion(
        callback,
        EdersCompletionCallback(activity_id=20, completed=True),
        AsyncMock(execute=AsyncMock(side_effect=error)),
    )
    callback.message.edit_text.assert_not_awaited()
    assert callback.answer.call_args.kwargs["show_alert"] is True


async def test_foreign_chat_callback_never_writes():
    callback = callback_message()
    callback.message.chat.id = 999
    service = AsyncMock()
    await on_eders_completion(callback, EdersCompletionCallback(activity_id=20, completed=True), service)
    service.execute.assert_not_awaited()


async def test_telegram_edit_failure_does_not_raise_after_remote_success():
    callback = callback_message()
    callback.message.edit_text.side_effect = TelegramBadRequest(method=EditMessageText(text="x"), message="cannot edit")
    await on_eders_completion(callback, EdersCompletionCallback(activity_id=20, completed=True), AsyncMock())
    callback.answer.assert_awaited_once_with("Marked as done in Eders.", show_alert=True)


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("manual,event_type", [(True, "before_2"), (False, "before_2"), (True, "material_new")])
async def test_notification_button_uses_recipient_locale_only_for_manual_reminders(locale, manual, event_type):
    now = datetime.now(UTC)
    activity = item(manual_completion=manual, closes=replace(item().closes, instant=now + timedelta(hours=2)))
    event = EdersEvent("key", activity, event_type, now, now)
    outbox = AsyncMock(enqueue=AsyncMock(return_value=True))
    themes = AsyncMock(get_theme=AsyncMock(return_value=Theme.BASIC))
    assert [sent async for sent in TelegramEdersNotificationSender(outbox, themes).send(42, locale, [event])] == [event]
    message = outbox.enqueue.call_args.args[1][0]
    if manual and event_type == "before_2":
        assert message.reply_markup.inline_keyboard[0][0].text == i18n.gettext("eders.mark_done", locale=locale.value)
    else:
        assert message.reply_markup is None
