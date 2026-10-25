from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User

from manashelper.modules.donations import router as handlers
from manashelper.modules.donations.callbacks import DonationBankCallback
from manashelper.modules.donations.catalog import DonationBank
from manashelper.modules.donations.keyboards import build_donations_keyboard
from manashelper.modules.donations.qr import DonationQrService
from manashelper.modules.donations.service import DonationService
from manashelper.platform.i18n.catalog import i18n

USER_ID = 946_001


@pytest.fixture
def context(tmp_path, monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    message = Message(
        message_id=1,
        date=0,
        from_user=User(id=USER_ID, is_bot=False, first_name="Tester"),
        chat=Chat(id=USER_ID, type="private"),
    ).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=42, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    path = tmp_path / "Bank.png"
    path.write_bytes(b"qr")
    bank = DonationBank("bank", "Bank & Co", path)
    monkeypatch.setattr(handlers, "list_donation_banks", lambda: [bank])
    service = AsyncMock(spec=DonationService)
    service.other_users_count.return_value = 8
    callback = CallbackQuery(id="donate", from_user=message.from_user, chat_instance="chat", message=message).as_(bot)
    with i18n.context(), i18n.use_locale("en"):
        yield SimpleNamespace(
            bot=bot,
            message=message,
            request=request,
            bank=bank,
            service=service,
            callback=callback,
            qr=AsyncMock(spec=DonationQrService),
        )


def methods(context, kind):
    return [call.args[1] for call in context.request.await_args_list if isinstance(call.args[1], kind)]


def test_callback_payload_keyboard_and_private_handler_flags(context):
    assert DonationBankCallback(bank_id="0123456789abcdef").pack() == "donate:0123456789abcdef"
    keyboard = build_donations_keyboard([context.bank])
    assert keyboard.inline_keyboard[0][0].text == "Bank & Co"
    assert keyboard.inline_keyboard[0][0].callback_data == "donate:bank"
    assert keyboard.inline_keyboard[-1][0].callback_data == "settings:back_to_settings"
    assert handlers.router.message.handlers[0].flags["private_chat_only"]
    assert all(handler.flags["private_chat_only"] for handler in handlers.router.callback_query.handlers)


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
@pytest.mark.parametrize("has_banks", [False, True])
async def test_donate_command_preserves_localized_intro_and_bank_availability(context, monkeypatch, locale, has_banks):
    if not has_banks:
        monkeypatch.setattr(handlers, "list_donation_banks", lambda: [])
    with i18n.use_locale(locale):
        await handlers.cmd_donate(context.message, context.service)
        expected = i18n.gettext("donations.intro").format(others=8)
        expected += "\n\n" + i18n.gettext("donations.choose_bank" if has_banks else "donations.qr_coming_soon")
    sent = methods(context, SendMessage)[0]
    assert sent.text == expected
    assert len(sent.reply_markup.inline_keyboard) == (2 if has_banks else 1)
    context.service.other_users_count.assert_awaited_once()


async def test_settings_entry_edits_existing_message_and_answers_callback(context):
    await handlers.on_open_donations(context.callback, context.service)
    edited = methods(context, EditMessageText)[0]
    assert edited.message_id == 1
    assert edited.text.startswith(i18n.gettext("donations.intro").format(others=8))
    assert len(methods(context, AnswerCallbackQuery)) == 1


async def test_bank_selection_uses_the_app_qr_service_and_current_chat(context):
    await handlers.on_donation_bank(context.callback, DonationBankCallback(bank_id="bank"), context.bot, context.qr)
    context.qr.send_bank_qr.assert_awaited_once_with(context.bot, USER_ID, context.bank)
    assert len(methods(context, AnswerCallbackQuery)) == 1


@pytest.mark.parametrize("missing_file", [False, True])
async def test_unknown_or_disappeared_bank_shows_unavailable_alert(context, missing_file):
    if missing_file:
        context.qr.send_bank_qr.side_effect = FileNotFoundError("test: file removed")
    await handlers.on_donation_bank(
        context.callback, DonationBankCallback(bank_id="bank" if missing_file else "missing"), context.bot, context.qr
    )
    answer = methods(context, AnswerCallbackQuery)[0]
    assert answer.text == i18n.gettext("donations.qr_unavailable") and answer.show_alert
    assert context.qr.send_bank_qr.await_count == int(missing_file)


async def test_inaccessible_callback_message_only_answers_callback(context):
    callback = context.callback.model_copy(update={"message": None})
    await handlers.on_donation_bank(callback, DonationBankCallback(bank_id="bank"), context.bot, context.qr)
    context.qr.send_bank_qr.assert_not_awaited()
    assert len(methods(context, AnswerCallbackQuery)) == 1
