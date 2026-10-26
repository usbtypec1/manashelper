import uuid
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, DeleteMessages, EditMessageText, GetMe, SendMediaGroup, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User

from manashelper.localization.locale import Locale
from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementDeletionResult,
    AdvertisementMediaItem,
    AdvertisementNotFoundError,
    AdvertisementPage,
    AdvertisementService,
    AdvertisementSummary,
    TooManyAdvertisementsError,
)
from manashelper.modules.advertisements.application.advertisement_contact import ContactReveal
from manashelper.modules.advertisements.domain.enums import AdvertisementMediaType, AdvertisementStatus
from manashelper.modules.advertisements.presentation.advertisement import (
    AdvertisementForm,
    on_create_requested,
    on_delete_confirmed,
    on_description_entered,
    on_expiry_selected,
    on_form_submitted,
    on_media_done,
    on_price_skipped,
    on_title_entered,
)
from manashelper.modules.advertisements.presentation.advertisement_contact import on_advertisement_deep_link
from manashelper.modules.advertisements.presentation.advertisement_moderation import (
    AdvertisementModerationForm,
    on_approve,
    on_reject_add_comment_requested,
    on_reject_comment_entered,
)
from manashelper.modules.advertisements.presentation.callbacks import (
    AdvertisementDeleteAction,
    AdvertisementDeleteCallback,
    AdvertisementExpiryCallback,
    AdvertisementExpiryOption,
    AdvertisementFormAction,
    AdvertisementFormCallback,
    AdvertisementModerationAction,
    AdvertisementModerationCallback,
)
from manashelper.modules.users.application.user_contact import ContactStatus
from manashelper.platform.i18n.catalog import i18n

USER_ID = 942_001
MODERATION_CHAT_ID = -100942001
CHANNEL_ID = -100942002
AD_ID = uuid.UUID("01234567-89ab-cdef-0123-456789abcdef")


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=USER_ID, is_bot=False, first_name="Tester", username="seller")
    message = Message(message_id=1, date=0, from_user=user, chat=Chat(id=USER_ID, type="private")).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, GetMe):
            return User(id=bot.id, is_bot=True, first_name="Bot", username="manas_test")
        if isinstance(method, SendMediaGroup):
            return [
                Message(message_id=100 + index, date=0, chat=Chat(id=method.chat_id, type="channel")).as_(bot)
                for index in range(len(method.media))
            ]
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=42, date=0, chat=Chat(id=method.chat_id, type="private")).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=USER_ID, user_id=USER_ID))
    summary = AdvertisementSummary(
        AD_ID,
        USER_ID,
        "<Book>",
        "Description & details",
        100,
        AdvertisementStatus.PENDING,
        None,
        None,
        datetime.now(),
        [],
    )
    service = AsyncMock(spec=AdvertisementService)
    service.create_advertisement.return_value = summary
    service.delete_owned.return_value = AdvertisementDeletionResult(AdvertisementStatus.PUBLISHED, [10, 11])
    service.get_page_by_user_id.return_value = AdvertisementPage([], 0, 1)
    moderation = AsyncMock()
    moderation.approve.return_value = replace(summary, status=AdvertisementStatus.PUBLISHED)
    moderation.reject.return_value = replace(summary, status=AdvertisementStatus.REJECTED)
    contacts = AsyncMock()
    contacts.get_contact_status.return_value = ContactStatus(username="seller", phone_numbers=["+996700000000"])
    reveal = AsyncMock()
    reveal.reveal_contact.return_value = ContactReveal(summary.title, contacts.get_contact_status.return_value)
    with i18n.context(), i18n.use_locale("en"):
        yield SimpleNamespace(
            bot=bot,
            message=message,
            state=state,
            request=request,
            summary=summary,
            service=service,
            moderation=moderation,
            contacts=contacts,
            reveal=reveal,
            locale=SimpleNamespace(get_locale=AsyncMock(return_value=Locale.ZH)),
            settings=SimpleNamespace(
                moderation_chat_id=MODERATION_CHAT_ID,
                advertisement_channel_id=CHANNEL_ID,
                advertisement_channel_link="https://t.me/example",
            ),
        )


def methods(context, kind):
    return [call.args[1] for call in context.request.await_args_list if isinstance(call.args[1], kind)]


def callback(context, chat_id=USER_ID):
    message = context.message.model_copy(
        update={"chat": Chat(id=chat_id, type="private" if chat_id == USER_ID else "supergroup")}
    )
    return CallbackQuery(id="ad", from_user=context.message.from_user, chat_instance="chat", message=message).as_(
        context.bot
    )


async def test_create_form_preserves_states_payloads_and_submission(context):
    assert AdvertisementForm.title.state == "AdvertisementForm:title"
    assert AdvertisementModerationForm.comment.state == "AdvertisementModerationForm:comment"
    assert AdvertisementFormCallback(action=AdvertisementFormAction.CONFIRM_SUBMIT).pack() == "ad_form:confirm_submit"
    assert AdvertisementExpiryCallback(option=AdvertisementExpiryOption.NONE).pack() == "ad_expiry:none"
    assert AdvertisementModerationCallback(id=AD_ID, action=AdvertisementModerationAction.APPROVE).pack() == (
        f"ad_moderation:{AD_ID.hex}:approve"
    )
    await on_create_requested(context.message, context.state, context.service, context.contacts)
    assert await context.state.get_state() == "AdvertisementForm:title"
    await on_title_entered(context.message.model_copy(update={"text": "  <Book>  "}), context.state)
    assert await context.state.get_state() == "AdvertisementForm:description"
    await on_description_entered(context.message.model_copy(update={"text": " Description & details "}), context.state)
    assert await context.state.get_state() == "AdvertisementForm:price"
    await on_price_skipped(callback(context), context.state)
    assert await context.state.get_state() == "AdvertisementForm:media"
    await on_media_done(callback(context), context.state)
    assert await context.state.get_state() == "AdvertisementForm:expires_at"
    await on_expiry_selected(
        callback(context), AdvertisementExpiryCallback(option=AdvertisementExpiryOption.NONE), context.state
    )
    assert await context.state.get_state() == "AdvertisementForm:confirm"
    await on_form_submitted(
        callback(context), context.state, context.bot, context.settings, context.service, context.contacts
    )
    context.service.create_advertisement.assert_awaited_once_with(
        user_id=USER_ID,
        title="<Book>",
        description="Description & details",
        price=None,
        expires_at=None,
        media_items=[],
    )
    assert await context.state.get_state() is None
    review = [message for message in methods(context, SendMessage) if message.chat_id == MODERATION_CHAT_ID][0]
    assert review.text.startswith(i18n.gettext("ads.new_review", locale="ru"))
    assert "&lt;Book&gt;" in review.text and "Description &amp; details" in review.text
    assert "@seller" in review.text and "+996700000000" in review.text


@pytest.mark.parametrize("has_contact", [False, True])
async def test_contact_requirement_selects_initial_state(context, has_contact):
    context.contacts.get_contact_status.return_value = ContactStatus(
        username="seller" if has_contact else None, phone_numbers=[]
    )
    await on_create_requested(context.message, context.state, context.service, context.contacts)
    assert await context.state.get_state() == (
        "AdvertisementForm:title" if has_contact else "AdvertisementForm:phone_number"
    )


async def test_hourly_limit_does_not_start_or_clear_form(context):
    await context.state.set_state(AdvertisementForm.confirm)
    context.service.assert_can_post.side_effect = TooManyAdvertisementsError(USER_ID)
    await on_create_requested(context.message, context.state, context.service, context.contacts)
    assert await context.state.get_state() == "AdvertisementForm:confirm"
    context.contacts.get_contact_status.assert_not_awaited()
    assert methods(context, SendMessage)[0].text == i18n.gettext("ads.hourly_limit")


@pytest.mark.parametrize("media", [False, True])
async def test_approval_preserves_channel_locale_hidden_contacts_and_message_ids(context, media):
    if media:
        context.moderation.approve.return_value = replace(
            context.moderation.approve.return_value,
            media=[
                AdvertisementMediaItem("photo", AdvertisementMediaType.PHOTO),
                AdvertisementMediaItem("video", AdvertisementMediaType.VIDEO),
            ],
        )
    await on_approve(
        callback(context, MODERATION_CHAT_ID),
        AdvertisementModerationCallback(id=AD_ID, action=AdvertisementModerationAction.APPROVE),
        context.bot,
        context.settings,
        context.service,
        context.moderation,
        context.locale,
    )
    publication = methods(context, SendMediaGroup if media else SendMessage)[0]
    caption = publication.media[0].caption if media else publication.text
    assert publication.chat_id == CHANNEL_ID
    assert f"https://t.me/manas_test?start=ad_{AD_ID}" in caption
    assert "&lt;Book&gt;" in caption and "@seller" not in caption and "+996" not in caption
    assert i18n.gettext("ads.price", locale="ru").format(price=100) in caption
    if media:
        assert publication.media[1].caption is None
    context.service.record_channel_messages.assert_awaited_once_with(AD_ID, [100, 101] if media else [42])
    owner = [message for message in methods(context, SendMessage) if message.chat_id == USER_ID][0]
    assert owner.text == i18n.gettext("ads.owner_approved", locale="zh").format(title="&lt;Book&gt;")


async def test_moderation_from_other_chat_is_rejected_before_service_call(context):
    await on_approve(
        callback(context),
        AdvertisementModerationCallback(id=AD_ID, action=AdvertisementModerationAction.APPROVE),
        context.bot,
        context.settings,
        context.service,
        context.moderation,
        context.locale,
    )
    context.moderation.approve.assert_not_awaited()
    assert not methods(context, SendMessage)
    assert methods(context, AnswerCallbackQuery)[0].show_alert


async def test_publication_failure_does_not_record_message_ids_or_notify_owner(context):
    respond = context.request.side_effect

    async def fail_channel(bot, method, **kwargs):
        if isinstance(method, SendMessage) and method.chat_id == CHANNEL_ID:
            raise TelegramBadRequest(method=method, message="test: channel unavailable")
        return await respond(bot, method, **kwargs)

    context.request.side_effect = fail_channel
    await on_approve(
        callback(context, MODERATION_CHAT_ID),
        AdvertisementModerationCallback(id=AD_ID, action=AdvertisementModerationAction.APPROVE),
        context.bot,
        context.settings,
        context.service,
        context.moderation,
        context.locale,
    )
    # Existing behavior: approve runs before publication. No compensation is performed here.
    context.moderation.approve.assert_awaited_once_with(AD_ID)
    context.service.record_channel_messages.assert_not_awaited()
    context.locale.get_locale.assert_not_awaited()
    assert methods(context, AnswerCallbackQuery)[0].text == i18n.gettext("ads.publish_failed")


async def test_rejection_comment_keeps_fsm_and_existing_storage_truncation(context):
    await on_reject_add_comment_requested(
        callback(context, MODERATION_CHAT_ID),
        AdvertisementModerationCallback(id=AD_ID, action=AdvertisementModerationAction.ADD_COMMENT),
        context.settings,
        context.state,
    )
    assert await context.state.get_state() == "AdvertisementModerationForm:comment"
    raw = "<" + "x" * 519
    message = context.message.model_copy(
        update={"text": " " + raw + " ", "chat": Chat(id=MODERATION_CHAT_ID, type="supergroup")}
    )
    await on_reject_comment_entered(message, context.state, context.bot, context.moderation, context.locale)
    context.moderation.reject.assert_awaited_once_with(AD_ID, raw[:512])
    assert await context.state.get_state() is None
    owner = [message for message in methods(context, SendMessage) if message.chat_id == USER_ID][0]
    # Existing owner message uses the complete comment, while persistence receives at most 512 characters.
    assert "&lt;" + "x" * 519 in owner.text


@pytest.mark.parametrize("payload", ["market", "ad_not-a-uuid", "unknown", f"ad_{AD_ID}"])
async def test_start_payload_routes_market_contacts_or_welcome(context, payload):
    await on_advertisement_deep_link(
        context.message, CommandObject(command="start", args=payload), context.settings, context.reveal
    )
    text = methods(context, SendMessage)[0].text
    if payload == f"ad_{AD_ID}":
        context.reveal.reveal_contact.assert_awaited_once_with(AD_ID, USER_ID)
        assert "&lt;Book&gt;" in text and "@seller" in text
    else:
        context.reveal.reveal_contact.assert_not_awaited()
        assert text == (
            i18n.gettext("ads.marketplace_intro").format(link="https://t.me/example")
            if payload == "market"
            else i18n.gettext("common.welcome")
        )


async def test_missing_contact_ad_shows_not_found(context):
    context.reveal.reveal_contact.side_effect = AdvertisementNotFoundError(AD_ID)
    await on_advertisement_deep_link(
        context.message, CommandObject(command="start", args=f"ad_{AD_ID}"), context.settings, context.reveal
    )
    assert methods(context, SendMessage)[0].text == i18n.gettext("ads.not_found")


async def test_owner_deletion_continues_after_channel_delete_failure(context):
    respond = context.request.side_effect

    async def fail_delete(bot, method, **kwargs):
        if isinstance(method, DeleteMessages):
            raise TelegramBadRequest(method=method, message="test: message unavailable")
        return await respond(bot, method, **kwargs)

    context.request.side_effect = fail_delete
    await on_delete_confirmed(
        callback(context),
        AdvertisementDeleteCallback(id=AD_ID, action=AdvertisementDeleteAction.CONFIRM, page=0),
        context.bot,
        context.settings,
        context.service,
    )
    context.service.delete_owned.assert_awaited_once_with(AD_ID, USER_ID)
    deletion = methods(context, DeleteMessages)[0]
    assert (deletion.chat_id, deletion.message_ids) == (CHANNEL_ID, [10, 11])
    context.service.get_page_by_user_id.assert_awaited_once_with(USER_ID, 0)
    assert methods(context, EditMessageText)[0].text == i18n.gettext("ads.deleted")
