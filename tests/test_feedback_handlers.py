import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User

from manashelper.core.config import Settings
from manashelper.localization.i18n import i18n
from manashelper.modules.feedback.callbacks import FeedbackAction, FeedbackCallback
from manashelper.modules.feedback.router import (
    FeedbackForm,
    on_admin_reply,
    on_feedback_cancelled,
    on_feedback_entered,
    on_open_feedback,
    router,
)
from manashelper.modules.feedback.service import BODY_MAX_LENGTH, FeedbackService, FeedbackSummary
from manashelper.modules.users.application.locale import LocaleService

USER_ID = 941_001
ADMIN_CHAT_ID = -100941001


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=USER_ID, is_bot=False, first_name="Tester", username="tester")
    message = Message(
        message_id=1, date=0, from_user=user, chat=Chat(id=USER_ID, type="private"), text="  A <question> & idea  "
    ).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=42, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=USER_ID, user_id=USER_ID))
    service = AsyncMock(spec=FeedbackService)
    summary = FeedbackSummary(id=uuid.uuid4(), user_id=USER_ID, body="A <question> & idea")
    service.submit.return_value = summary
    service.get_by_admin_chat_message_id.return_value = summary
    locale_service = SimpleNamespace(get_locale=AsyncMock(return_value=SimpleNamespace(value="zh")))
    with i18n.context(), i18n.use_locale("en"):
        yield SimpleNamespace(
            bot=bot,
            message=message,
            state=state,
            request=request,
            service=service,
            summary=summary,
            locale_service=locale_service,
            settings=SimpleNamespace(admin_chat_id=ADMIN_CHAT_ID),
        )


def sent_methods(context, kind):
    return [call.args[1] for call in context.request.await_args_list if isinstance(call.args[1], kind)]


def callback(context):
    return CallbackQuery(
        id="feedback", from_user=context.message.from_user, chat_instance="chat", message=context.message
    ).as_(context.bot)


def admin_message(context, *, chat_id=ADMIN_CHAT_ID, text="  <Answer> & details  ", caption=None):
    return Message(
        message_id=2,
        date=0,
        chat=Chat(id=chat_id, type="supergroup"),
        text=text,
        caption=caption,
        reply_to_message=Message(message_id=42, date=0, chat=Chat(id=chat_id, type="supergroup")),
    ).as_(context.bot)


async def test_open_cancel_preserves_fsm_and_callback_contract(context):
    assert FeedbackForm.message.state == "FeedbackForm:message"
    assert FeedbackCallback(action=FeedbackAction.CANCEL).pack() == "feedback:cancel"

    await on_open_feedback(callback(context), context.state)
    assert await context.state.get_state() == "FeedbackForm:message"
    prompt = sent_methods(context, EditMessageText)[0]
    assert prompt.text == i18n.gettext("feedback.message_prompt")
    assert prompt.reply_markup.inline_keyboard[0][0].callback_data == "feedback:cancel"
    await context.state.update_data(temporary="discard")

    await on_feedback_cancelled(callback(context), context.state)
    assert await context.state.get_state() is None
    assert await context.state.get_data() == {}
    assert sent_methods(context, EditMessageText)[-1].text == i18n.gettext("settings.title")
    assert len(sent_methods(context, AnswerCallbackQuery)) == 2
    context.service.submit.assert_not_awaited()


@pytest.mark.parametrize("body", [None, "", " \n ", "x" * (BODY_MAX_LENGTH + 1)])
async def test_invalid_body_keeps_form_without_submission(context, body):
    await context.state.set_state(FeedbackForm.message)
    await on_feedback_entered(
        context.message.model_copy(update={"text": body}),
        context.state,
        context.bot,
        context.settings,
        context.service,
    )
    context.service.submit.assert_not_awaited()
    assert await context.state.get_state() == "FeedbackForm:message"
    messages = sent_methods(context, SendMessage)
    assert len(messages) == 1
    assert messages[0].text == i18n.gettext("feedback.invalid_message").format(max=2000)
    assert messages[0].reply_markup.inline_keyboard[0][0].callback_data == "feedback:cancel"


@pytest.mark.parametrize("username", ["tester", None])
async def test_submit_strips_body_and_forwards_escaped_text_in_admin_locale(context, username):
    await context.state.set_state(FeedbackForm.message)
    user = context.message.from_user.model_copy(update={"username": username})
    await on_feedback_entered(
        context.message.model_copy(update={"from_user": user}),
        context.state,
        context.bot,
        context.settings,
        context.service,
    )
    context.service.submit.assert_awaited_once_with(USER_ID, "A <question> & idea")
    context.service.record_admin_chat_message.assert_awaited_once_with(context.summary.id, 42)
    assert await context.state.get_state() is None
    messages = sent_methods(context, SendMessage)
    assert [message.chat_id for message in messages] == [USER_ID, ADMIN_CHAT_ID]
    assert messages[0].text == i18n.gettext("feedback.sent", locale="en")
    assert messages[1].text == i18n.gettext("feedback.admin_message", locale="ru").format(
        sender="@tester" if username else str(USER_ID), body="A &lt;question&gt; &amp; idea"
    )


async def test_boundary_body_length_is_accepted(context):
    await on_feedback_entered(
        context.message.model_copy(update={"text": "x" * BODY_MAX_LENGTH}),
        context.state,
        context.bot,
        context.settings,
        context.service,
    )
    context.service.submit.assert_awaited_once_with(USER_ID, "x" * 2000)


async def test_forward_failure_preserves_existing_acknowledgement_and_cleared_state(context):
    respond = context.request.side_effect

    async def fail_admin(_bot, method, **kwargs):
        if isinstance(method, SendMessage) and method.chat_id == ADMIN_CHAT_ID:
            raise TelegramBadRequest(method=method, message="test: admin unavailable")
        return await respond(_bot, method, **kwargs)

    context.request.side_effect = fail_admin
    await context.state.set_state(FeedbackForm.message)
    await on_feedback_entered(context.message, context.state, context.bot, context.settings, context.service)
    context.service.submit.assert_awaited_once()
    context.service.record_admin_chat_message.assert_not_awaited()
    assert await context.state.get_state() is None
    assert sent_methods(context, SendMessage)[0].text == i18n.gettext("feedback.sent")


@pytest.mark.parametrize("chat_id", [ADMIN_CHAT_ID, -100999999])
async def test_router_restricts_admin_reply_to_configured_group(context, chat_id):
    message = admin_message(context, chat_id=chat_id)
    dependencies = {
        Settings: context.settings,
        FeedbackService: context.service,
        LocaleService: context.locale_service,
    }

    async def resolve(dependency, component=""):
        return dependencies[dependency]

    await router.message.trigger(
        message,
        bot=context.bot,
        settings=context.settings,
        feedback_service=context.service,
        locale_service=context.locale_service,
        dishka_container=SimpleNamespace(get=resolve),
    )
    if chat_id != ADMIN_CHAT_ID:
        context.service.get_by_admin_chat_message_id.assert_not_awaited()
        assert not sent_methods(context, SendMessage)
        return
    context.service.get_by_admin_chat_message_id.assert_awaited_once_with(42)
    context.locale_service.get_locale.assert_awaited_once_with(USER_ID)
    messages = sent_methods(context, SendMessage)
    assert [message.chat_id for message in messages] == [USER_ID, ADMIN_CHAT_ID]
    assert messages[0].text == i18n.gettext("feedback.admin_reply", locale="zh").format(
        text="  &lt;Answer&gt; &amp; details  "
    )
    assert messages[1].text == i18n.gettext("feedback.reply_sent", locale="ru")


@pytest.mark.parametrize("has_feedback, text", [(False, "Reply"), (True, None)])
async def test_unmatched_or_empty_admin_reply_sends_nothing(context, has_feedback, text):
    if not has_feedback:
        context.service.get_by_admin_chat_message_id.return_value = None
    await on_admin_reply(
        admin_message(context, text=text), context.bot, context.settings, context.service, context.locale_service
    )
    assert not sent_methods(context, SendMessage)
    context.locale_service.get_locale.assert_not_awaited()


async def test_admin_caption_is_relayed_when_text_is_absent(context):
    await on_admin_reply(
        admin_message(context, text=None, caption="Caption <reply>"),
        context.bot,
        context.settings,
        context.service,
        context.locale_service,
    )
    assert sent_methods(context, SendMessage)[0].text == i18n.gettext("feedback.admin_reply", locale="zh").format(
        text="Caption &lt;reply&gt;"
    )


async def test_failed_admin_reply_reports_failure_in_admin_locale(context):
    respond = context.request.side_effect

    async def fail_recipient(_bot, method, **kwargs):
        if isinstance(method, SendMessage) and method.chat_id == USER_ID:
            raise TelegramBadRequest(method=method, message="test: recipient unavailable")
        return await respond(_bot, method, **kwargs)

    context.request.side_effect = fail_recipient
    await on_admin_reply(admin_message(context), context.bot, context.settings, context.service, context.locale_service)
    messages = sent_methods(context, SendMessage)
    assert messages[-1].chat_id == ADMIN_CHAT_ID
    assert messages[-1].text == i18n.gettext("feedback.delivery_failed", locale="ru")
