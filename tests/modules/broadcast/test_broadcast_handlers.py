from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageCaption, EditMessageText, SendMessage, SendPhoto
from aiogram.types import BotCommandScopeChat, CallbackQuery, Chat, Message, PhotoSize, User

from manashelper.localization.locale import Locale
from manashelper.modules.broadcast import router as handlers
from manashelper.modules.broadcast.callbacks import BroadcastAction, BroadcastCallback
from manashelper.modules.broadcast.keyboards import build_broadcast_confirm_keyboard
from manashelper.modules.broadcast.service import SendBroadcast
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.commands import setup_commands

ADMIN_CHAT_ID = -100947000
ACTOR_ID = 947_001
RECIPIENT_IDS = [947_101, 947_102, 947_103, 947_104, 947_105]
LOCALES = dict(zip(RECIPIENT_IDS, Locale, strict=True))
BODY = "  <News> & details\n "
ESCAPED_BODY = "  &lt;News&gt; &amp; details\n "


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    message = Message(
        message_id=1,
        date=0,
        from_user=User(id=ACTOR_ID, is_bot=False, first_name="Admin"),
        chat=Chat(id=ADMIN_CHAT_ID, type="supergroup"),
        text=BODY,
    ).as_(bot)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=ADMIN_CHAT_ID, user_id=ACTOR_ID))
    sending_states = []

    async def respond(_bot, method, **kwargs):
        if isinstance(method, SendMessage) and method.chat_id in RECIPIENT_IDS:
            sending_states.append((await state.get_state(), await state.get_data()))
        if isinstance(method, (SendMessage, EditMessageText, SendPhoto, EditMessageCaption)):
            return Message(message_id=42, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    users = AsyncMock(spec=UsersQuery)
    users.get_active_ids.return_value = RECIPIENT_IDS
    locales = AsyncMock(spec=LocaleService)
    locales.get_locale.side_effect = LOCALES.__getitem__
    callback = CallbackQuery(id="broadcast", from_user=message.from_user, chat_instance="chat", message=message).as_(
        bot
    )
    with i18n.context(), i18n.use_locale("tr"):
        yield SimpleNamespace(
            bot=bot,
            message=message,
            state=state,
            request=request,
            users=users,
            service=SendBroadcast(users),
            status=AsyncMock(spec=BotStatusService, is_stopped=AsyncMock(return_value=False)),
            locales=locales,
            callback=callback,
            settings=SimpleNamespace(admin_chat_id=ADMIN_CHAT_ID),
            sending_states=sending_states,
        )


def methods(context, kind):
    return [call.args[1] for call in context.request.await_args_list if isinstance(call.args[1], kind)]


async def draft(context, body=BODY):
    await context.state.set_state(handlers.BroadcastForm.message)
    await context.state.update_data(body=body)


async def confirm(context, callback=None):
    await handlers.on_broadcast_confirmed(
        callback or context.callback,
        context.state,
        context.bot,
        context.settings,
        context.service,
        context.locales,
        context.status,
    )


def test_fsm_payload_and_group_support_contracts(context):
    assert handlers.BroadcastForm.message.state == "BroadcastForm:message"
    assert handlers._BODY_STATE_KEY == "body"
    assert BroadcastCallback(action=BroadcastAction.CONFIRM).pack() == "broadcast:confirm"
    assert BroadcastCallback(action=BroadcastAction.CANCEL).pack() == "broadcast:cancel"
    keyboard = build_broadcast_confirm_keyboard()
    assert [button.callback_data for button in keyboard.inline_keyboard[0]] == ["broadcast:confirm", "broadcast:cancel"]
    for observer in (handlers.router.message, handlers.router.callback_query):
        assert all(not handler.flags.get("private_chat_only") for handler in observer.handlers)


async def test_command_starts_form_in_admin_locale(context):
    await context.state.set_state("Other:state")
    await handlers.on_broadcast_command(context.message, context.state, context.settings)
    assert await context.state.get_state() == "BroadcastForm:message"
    assert methods(context, SendMessage)[0].text == i18n.gettext("broadcast.message_prompt", locale="ru")
    context.users.get_active_ids.assert_not_awaited()


@pytest.mark.parametrize("action", ["command", "message", "cancel", "confirm"])
async def test_other_chat_cannot_start_preview_cancel_or_send(context, action):
    await context.state.set_state("Other:state")
    await context.state.update_data(body="keep")
    message = context.message.model_copy(update={"chat": Chat(id=ACTOR_ID, type="private")})
    callback = context.callback.model_copy(update={"message": message})
    if action == "command":
        await handlers.on_broadcast_command(message, context.state, context.settings)
    elif action == "message":
        await handlers.on_broadcast_message_entered(message, context.state, context.settings)
    elif action == "cancel":
        await handlers.on_broadcast_cancelled(callback, context.state, context.settings)
    else:
        await confirm(context, callback)
    assert await context.state.get_state() == "Other:state"
    assert await context.state.get_data() == {"body": "keep"}
    context.users.get_active_ids.assert_not_awaited()
    assert not methods(context, SendMessage) and not methods(context, EditMessageText)
    assert len(methods(context, AnswerCallbackQuery)) == int(action in {"cancel", "confirm"})


@pytest.mark.parametrize(
    ("text", "caption", "expected_body"), [(BODY, None, BODY), (None, BODY, BODY), ("", BODY, BODY), (" ", None, " ")]
)
async def test_preview_preserves_raw_text_caption_fallback_whitespace_and_html(context, text, caption, expected_body):
    await context.state.set_state(handlers.BroadcastForm.message)
    message = context.message.model_copy(update={"text": text, "caption": caption})
    await handlers.on_broadcast_message_entered(message, context.state, context.settings)
    assert await context.state.get_data() == {"body": expected_body, "photo_id": None}
    assert await context.state.get_state() == "BroadcastForm:message"
    preview = methods(context, SendMessage)[0]
    assert preview.text == i18n.gettext("broadcast.preview", locale="ru").format(
        body=ESCAPED_BODY if expected_body == BODY else " "
    )
    assert [button.callback_data for button in preview.reply_markup.inline_keyboard[0]] == [
        "broadcast:confirm",
        "broadcast:cancel",
    ]
    context.users.get_active_ids.assert_not_awaited()


@pytest.mark.parametrize("body", [None, ""])
async def test_empty_preview_keeps_existing_draft(context, body):
    await draft(context, "previous")
    await handlers.on_broadcast_message_entered(
        context.message.model_copy(update={"text": body}), context.state, context.settings
    )
    assert await context.state.get_data() == {"body": "previous"}
    assert methods(context, SendMessage)[0].text == i18n.gettext("broadcast.text_required", locale="ru")
    context.users.get_active_ids.assert_not_awaited()


async def test_cancel_clears_form_and_uses_admin_locale(context):
    await draft(context)
    await handlers.on_broadcast_cancelled(context.callback, context.state, context.settings)
    assert await context.state.get_state() is None and await context.state.get_data() == {}
    assert methods(context, EditMessageText)[0].text == i18n.gettext("broadcast.cancelled", locale="ru")
    assert len(methods(context, AnswerCallbackQuery)) == 1
    context.users.get_active_ids.assert_not_awaited()


@pytest.mark.parametrize("failed_recipient", [None, RECIPIENT_IDS[1]])
async def test_delivery_keeps_recipient_order_locales_state_clear_and_success_count(context, failed_recipient):
    await draft(context)
    respond = context.request.side_effect

    async def deliver(_bot, method, **kwargs):
        if isinstance(method, SendMessage) and method.chat_id == failed_recipient:
            raise TelegramBadRequest(method=method, message="test: recipient unavailable")
        return await respond(_bot, method, **kwargs)

    async def recipients():
        assert await context.state.get_state() is None and await context.state.get_data() == {}
        return RECIPIENT_IDS

    context.request.side_effect = deliver
    context.users.get_active_ids.side_effect = recipients
    await confirm(context)
    sent = methods(context, SendMessage)
    assert [method.chat_id for method in sent] == [*RECIPIENT_IDS, ADMIN_CHAT_ID]
    for method in sent[:-1]:
        assert method.text == i18n.gettext("broadcast.admin_message", locale=LOCALES[method.chat_id].value).format(
            body=ESCAPED_BODY
        )
    assert sent[-1].text == i18n.gettext("broadcast.sent", locale="ru").format(
        sent=5 - int(failed_recipient is not None), total=5
    )
    assert context.sending_states and all(state is None and data == {} for state, data in context.sending_states)
    calls = [call.args[1] for call in context.request.await_args_list]
    assert isinstance(calls[0], AnswerCallbackQuery) and isinstance(calls[1], EditMessageText)
    assert calls[1].text == i18n.gettext("broadcast.sending", locale="ru")
    assert i18n.current_locale == "tr"
    context.users.get_active_ids.assert_awaited_once()


async def test_duplicate_confirmation_does_not_send_again(context):
    await draft(context)
    await confirm(context)
    sent_count = len(methods(context, SendMessage))
    await confirm(context)
    assert len(methods(context, SendMessage)) == sent_count
    context.users.get_active_ids.assert_awaited_once()
    assert len(methods(context, AnswerCallbackQuery)) == 2


@pytest.mark.parametrize("body", [None, ""])
async def test_empty_confirmation_clears_state_without_loading_recipients(context, body):
    await draft(context, body)
    await confirm(context)
    assert await context.state.get_state() is None and await context.state.get_data() == {}
    context.users.get_active_ids.assert_not_awaited()
    assert not methods(context, SendMessage) and not methods(context, EditMessageText)
    assert len(methods(context, AnswerCallbackQuery)) == 1


async def test_empty_recipient_list_still_reports_zero_statistics(context):
    await draft(context)
    context.users.get_active_ids.return_value = []
    await confirm(context)
    assert methods(context, SendMessage)[0].text == i18n.gettext("broadcast.sent", locale="ru").format(sent=0, total=0)
    context.locales.get_locale.assert_not_awaited()


@pytest.mark.parametrize("action", ["cancel", "confirm"])
async def test_missing_callback_message_only_answers_callback(context, action):
    await draft(context)
    callback = context.callback.model_copy(update={"message": None})
    if action == "cancel":
        await handlers.on_broadcast_cancelled(callback, context.state, context.settings)
    else:
        await confirm(context, callback)
    assert await context.state.get_data() == {"body": BODY}
    context.users.get_active_ids.assert_not_awaited()
    assert len(methods(context, AnswerCallbackQuery)) == 1
    assert not methods(context, SendMessage)


@pytest.mark.parametrize("failure", ["recipients", "locale", "transport"])
async def test_unexpected_failure_aborts_without_summary_after_state_clear(context, failure):
    await draft(context)
    if failure == "recipients":
        context.users.get_active_ids.side_effect = RuntimeError("test: unexpected")
    elif failure == "locale":
        context.locales.get_locale.side_effect = RuntimeError("test: unexpected")
    else:
        respond = context.request.side_effect

        async def fail_transport(_bot, method, **kwargs):
            if isinstance(method, SendMessage):
                raise RuntimeError("test: unexpected")
            return await respond(_bot, method, **kwargs)

        context.request.side_effect = fail_transport
    with pytest.raises(RuntimeError, match="test: unexpected"):
        await confirm(context)
    assert await context.state.get_state() is None and await context.state.get_data() == {}
    sent = methods(context, SendMessage)
    assert [method.chat_id for method in sent] == ([RECIPIENT_IDS[0]] if failure == "transport" else [])
    assert context.locales.get_locale.await_count == int(failure != "recipients")


async def test_broadcast_command_is_registered_only_in_configured_admin_chat():
    bot = SimpleNamespace(set_my_commands=AsyncMock())
    await setup_commands(bot, SimpleNamespace(admin_chat_id=ADMIN_CHAT_ID))
    for call in bot.set_my_commands.await_args_list:
        commands = {command.command for command in call.kwargs["commands"]}
        scope = call.kwargs["scope"]
        if isinstance(scope, BotCommandScopeChat):
            assert scope.chat_id == ADMIN_CHAT_ID and commands == {"broadcast"}
        else:
            assert "broadcast" not in commands


async def test_photo_with_buttons_is_previewed_and_delivered(context):
    photo = PhotoSize(file_id="photo-file", file_unique_id="unique-photo", width=640, height=480)
    message = context.message.model_copy(update={"text": None, "caption": BODY, "photo": [photo]})
    await handlers.on_broadcast_message_entered(message, context.state, context.settings)
    assert methods(context, SendPhoto)[0].photo == "photo-file"
    assert (await context.state.get_data())["photo_id"] == "photo-file"
    await handlers.on_broadcast_buttons_requested(context.callback, context.state, context.settings)
    assert await context.state.get_state() == handlers.BroadcastForm.buttons.state
    buttons = context.message.model_copy(update={"text": "Site | https://example.com\nMenu | callback:food_menu:0"})
    await handlers.on_broadcast_buttons_entered(buttons, context.state, context.settings)
    assert await context.state.get_state() == handlers.BroadcastForm.message.state
    context.request.reset_mock()
    callback = context.callback.model_copy(update={"message": message})
    await confirm(context, callback)
    photos = methods(context, SendPhoto)
    assert [entry.chat_id for entry in photos] == RECIPIENT_IDS
    for entry in photos:
        assert entry.photo == "photo-file"
        assert entry.caption == i18n.gettext("broadcast.admin_message", locale=LOCALES[entry.chat_id].value).format(
            body=ESCAPED_BODY
        )
        rows = entry.reply_markup.inline_keyboard
        assert rows[0][0].url == "https://example.com"
        assert rows[1][0].callback_data == "food_menu:0"
        assert all(button.callback_data != "broadcast:confirm" for row in rows for button in row)
    assert methods(context, EditMessageCaption)[0].caption == i18n.gettext("broadcast.sending", locale="ru")
    assert await context.state.get_data() == {}


async def test_photo_without_caption_can_be_sent(context):
    photo = PhotoSize(file_id="photo-file", file_unique_id="unique-photo", width=640, height=480)
    message = context.message.model_copy(update={"text": None, "caption": None, "photo": [photo]})
    await handlers.on_broadcast_message_entered(message, context.state, context.settings)
    await confirm(context)
    assert len(methods(context, SendPhoto)) == 1 + len(RECIPIENT_IDS)


async def test_invalid_buttons_keep_editor_and_do_not_load_recipients(context):
    await draft(context)
    await handlers.on_broadcast_buttons_requested(context.callback, context.state, context.settings)
    before = await context.state.get_data()
    await handlers.on_broadcast_buttons_entered(
        context.message.model_copy(update={"text": "Broken | callback:"}), context.state, context.settings
    )
    assert await context.state.get_state() == handlers.BroadcastForm.buttons.state
    assert await context.state.get_data() == before
    context.users.get_active_ids.assert_not_awaited()


async def test_photo_failure_marks_recipient_stopped(context):
    from aiogram.exceptions import TelegramForbiddenError

    await draft(context)
    await context.state.update_data(photo_id="photo-file")
    respond = context.request.side_effect

    async def fail_photo(bot, method, **kwargs):
        if isinstance(method, SendPhoto) and method.chat_id == RECIPIENT_IDS[0]:
            raise TelegramForbiddenError(method=method, message="Forbidden: user is deactivated")
        return await respond(bot, method, **kwargs)

    context.request.side_effect = fail_photo
    await confirm(context)
    context.status.stop.assert_awaited_once_with(RECIPIENT_IDS[0])
    assert len(methods(context, SendPhoto)) == len(RECIPIENT_IDS)


async def test_without_buttons_returns_to_preview_and_removes_draft_buttons(context):
    await draft(context)
    await context.state.update_data(buttons=[{"text": "Site", "url": "https://example.com"}])
    await handlers.on_broadcast_without_buttons(context.callback, context.state, context.settings)
    assert (await context.state.get_data())["buttons"] == []
    assert await context.state.get_state() == handlers.BroadcastForm.message.state


async def test_long_photo_caption_keeps_buttons_on_following_text(context):
    await draft(context, "x" * 1024)
    await context.state.update_data(photo_id="photo-file", buttons=[{"text": "Site", "url": "https://example.com"}])
    await confirm(context)
    photos = methods(context, SendPhoto)
    texts = [entry for entry in methods(context, SendMessage) if entry.chat_id in RECIPIENT_IDS]
    assert len(photos) == len(texts) == len(RECIPIENT_IDS)
    assert all(photo.caption is None and photo.reply_markup is None for photo in photos)
    assert all(text.reply_markup.inline_keyboard[0][0].url == "https://example.com" for text in texts)


@pytest.mark.parametrize("action", ["request_buttons", "without_buttons", "buttons_input"])
async def test_other_chat_cannot_edit_broadcast_buttons(context, action):
    await draft(context, "keep")
    message = context.message.model_copy(update={"chat": Chat(id=ACTOR_ID, type="private")})
    callback = context.callback.model_copy(update={"message": message})
    if action == "request_buttons":
        await handlers.on_broadcast_buttons_requested(callback, context.state, context.settings)
    elif action == "without_buttons":
        await handlers.on_broadcast_without_buttons(callback, context.state, context.settings)
    else:
        await handlers.on_broadcast_buttons_entered(message, context.state, context.settings)
    assert await context.state.get_data() == {"body": "keep"}
    context.users.get_active_ids.assert_not_awaited()
    assert not methods(context, SendMessage) and not methods(context, SendPhoto)
