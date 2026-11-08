from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Message

from manashelper.modules.broadcast.application.use_cases.send_broadcast import SendBroadcastUseCase
from manashelper.modules.broadcast.keyboards import build_broadcast_delivery_keyboard
from manashelper.modules.broadcast.service import BroadcastSender
from manashelper.modules.notifications import router
from manashelper.modules.notifications.callbacks import BroadcastMuteCallback
from manashelper.modules.notifications.keyboards import build_notifications_keyboard
from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import UserNotFoundError
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from tests.modules.notifications.application_factories import build_notification_settings_service


def service(session):
    return build_notification_settings_service(
        NotificationSettingsRepository(session), UsersQuery(UserRepository(session))
    )


async def test_mute_persists_for_14_days_and_reset_preserves_other_preferences(session):
    user_id = 972101
    session.add(User(id=user_id, full_name="Muted"))
    await session.flush()
    session.add(NotificationSettings(user_id=user_id, exam_grades_enabled=False))
    await session.flush()
    before = datetime.now(UTC)
    summary = await service(session).set_broadcast_mute(user_id, True)
    after = datetime.now(UTC)
    assert before + timedelta(days=14) <= summary.broadcast_muted_until <= after + timedelta(days=14)
    await session.commit()
    session.expire_all()
    assert await service(session).get_settings(user_id) == summary
    recipients = NotificationRecipientsQuery(NotificationSettingsRepository(session))
    assert user_id not in await recipients.for_broadcasts()
    with i18n.context(), i18n.use_locale("ru"):
        keyboard = build_notifications_keyboard(summary)
    assert any(b.callback_data == "broadcast_mute:0" for row in keyboard.inline_keyboard for b in row)
    reset = await service(session).set_broadcast_mute(user_id, False)
    assert reset.broadcast_muted_until is None
    assert reset.exam_grades_enabled is False
    await session.commit()
    session.expire_all()
    assert await service(session).get_settings(user_id) == reset
    assert user_id in await recipients.for_broadcasts()


async def test_recipient_selection_covers_missing_null_expired_boundary_future_and_stopped(session):
    now = datetime.now(UTC)
    ids = list(range(972110, 972116))
    session.add_all(User(id=uid, full_name="Recipient", bot_stopped=uid == ids[-1]) for uid in ids)
    await session.flush()
    session.add_all(
        [
            NotificationSettings(user_id=ids[1]),
            NotificationSettings(user_id=ids[2], broadcast_muted_until=now - timedelta(seconds=1)),
            NotificationSettings(user_id=ids[3], broadcast_muted_until=now),
            NotificationSettings(user_id=ids[4], broadcast_muted_until=now + timedelta(days=14)),
        ]
    )
    await session.flush()
    repository = NotificationSettingsRepository(session)
    assert set(await repository.get_broadcast_recipient_ids(now)) & set(ids) == set(ids[:4])
    # Broadcast mutes do not change academic notification eligibility.
    assert ids[4] in await repository.get_user_ids_with_exam_grades_enabled()
    sender = AsyncMock(spec=BroadcastSender)
    sender.send.return_value = True
    await SendBroadcastUseCase(NotificationRecipientsQuery(repository)).execute("body", sender)
    delivered = {call.args[0] for call in sender.send.await_args_list}
    assert delivered & set(ids) == set(ids[:4])


@pytest.mark.parametrize("muted", [True, False])
async def test_unknown_user_cannot_create_mute_settings(session, muted):
    with pytest.raises(UserNotFoundError):
        await service(session).set_broadcast_mute(972199, muted)
    assert await session.get(NotificationSettings, 972199) is None


@pytest.mark.parametrize("from_settings", [False, True])
async def test_callbacks_mute_actor_show_alert_and_reset_from_settings(session, from_settings):
    from manashelper.modules.notifications.keyboards import build_notifications_keyboard

    session.add(User(id=972120, full_name="Recipient"))
    await session.flush()
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = SimpleNamespace(id=972120)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.reply_markup = None
    with i18n.context(), i18n.use_locale("ru"):
        if from_settings:
            callback.message.reply_markup = build_notifications_keyboard(await service(session).get_settings(972120))
        await router.on_broadcast_mute(
            callback, BroadcastMuteCallback(muted=True), SimpleNamespace(execute=service(session).set_broadcast_mute)
        )
        callback.answer.assert_awaited_once_with("Вы отписались от рассылок на 14 дней", show_alert=True)
        if from_settings:
            callback.message.edit_text.assert_awaited_once()
        else:
            callback.message.edit_text.assert_not_awaited()
        await router.on_open_notifications(callback, SimpleNamespace(execute=service(session).get_settings))
        assert "Рассылки отключены до" in callback.message.edit_text.await_args.args[0]
        await router.on_broadcast_mute(
            callback, BroadcastMuteCallback(muted=False), SimpleNamespace(execute=service(session).set_broadcast_mute)
        )
        assert callback.message.edit_text.await_args.args[0] == i18n.gettext("notifications.title")
    assert (await service(session).get_settings(972120)).broadcast_muted_until is None


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
def test_delivery_keyboard_is_localized_and_does_not_change_admin_buttons(locale):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    original = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Site", url="https://example.com")],
            [InlineKeyboardButton(text="Menu", callback_data="food_menu:0")],
        ]
    )
    with i18n.context(), i18n.use_locale(locale):
        result = build_broadcast_delivery_keyboard(original)
        empty = build_broadcast_delivery_keyboard(None)
        assert result.inline_keyboard[-1][0].text == i18n.gettext("notifications.mute_broadcasts")
        assert result.inline_keyboard[-1][0].text != "notifications.mute_broadcasts"
    assert len(original.inline_keyboard) == 2
    assert result.inline_keyboard[:2] == original.inline_keyboard
    assert result.inline_keyboard[-1][0].callback_data == "broadcast_mute:1"
    assert empty.inline_keyboard == result.inline_keyboard[-1:]
