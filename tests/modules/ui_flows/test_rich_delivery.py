import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.exceptions import TelegramServerError
from aiogram.methods import SendMediaGroup, SendMessage, SendPhoto, SendVideo
from aiogram.types import Chat, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from manashelper.modules.ui_flows.presentation.sender import send_screen
from ui_flows.domain.delivery import Screen, ScreenButton, ScreenDelivery, ScreenMedia


def delivery(*, media=(), messages=(), inline=True):
    return ScreenDelivery(
        token="synthetic-token",
        session_id=uuid4(),
        revision=0,
        update_id=41,
        chat_id=991_760,
        screen=Screen(
            text="<b>Primary screen</b>",
            keyboard="inline" if inline else "none",
            buttons=[[ScreenButton(id="next", label="Continue")]] if inline else [],
            locale="en",
            theme="basic",
            media=list(media),
            messages=list(messages),
        ),
        status="unknown",
        message_id=None,
    )


@pytest_asyncio.fixture
async def telegram_transport(monkeypatch):
    bot = Bot(token="123456:synthetic-rich-delivery")
    calls = []
    transport = {"fail_at": None, "next_id": 200}

    async def respond(bot, method, **kwargs):
        calls.append(method)
        if len(calls) == transport["fail_at"]:
            raise TelegramServerError(method=method, message="Modeled delivery failure")

        def sent():
            transport["next_id"] += 1
            return Message(message_id=transport["next_id"], date=0, chat=Chat(id=991_760, type="private"))

        return [sent() for _ in method.media] if isinstance(method, SendMediaGroup) else sent()

    monkeypatch.setattr(bot.session, "make_request", respond)
    try:
        yield bot, calls, transport
    finally:
        await bot.session.close()


@pytest.mark.parametrize("kind,expected", [("photo", SendPhoto), ("video", SendVideo)])
async def test_single_media_follows_chunks_and_inline_buttons_use_their_own_message(telegram_transport, kind, expected):
    bot, calls, _ = telegram_transport
    captured = []
    screen = delivery(
        messages=("<b>First chunk</b>", "Escaped &lt;source&gt;"),
        media=(ScreenMedia(kind=kind, file_id="cached-file", caption="<b>Caption</b>"),),
    )
    message_id = await send_screen(bot, screen, delivered=captured)
    assert [type(call) for call in calls] == [SendMessage, SendMessage, expected, SendMessage, SendMessage]
    assert [call.text for call in calls[:2]] == screen.screen.messages
    assert calls[2].caption == "<b>Caption</b>" and calls[2].parse_mode == "HTML"
    assert getattr(calls[2], kind) == "cached-file" and calls[2].reply_markup is None
    assert isinstance(calls[3].reply_markup, ReplyKeyboardRemove)
    assert calls[3].text == screen.screen.text
    assert isinstance(calls[4].reply_markup, InlineKeyboardMarkup)
    assert calls[4].reply_markup.inline_keyboard[0][0].callback_data == "uf:synthetic-token:0"
    assert captured == [201, 202, 203, 204, 205] and message_id == captured[-1]


@pytest.mark.parametrize("count", [2, 10])
async def test_album_keeps_media_order_html_captions_and_every_returned_message_id(telegram_transport, count):
    bot, calls, _ = telegram_transport
    media = [
        ScreenMedia(kind="photo" if index % 2 == 0 else "video", file_id=f"file-{index}", caption=f"Item {index}")
        for index in range(count)
    ]
    captured = [99]
    message_id = await send_screen(bot, delivery(media=media, inline=False), delivered=captured)
    assert [type(call) for call in calls] == [SendMediaGroup, SendMessage]
    assert [item.type for item in calls[0].media] == [item.kind for item in media]
    assert [item.media for item in calls[0].media] == [item.file_id for item in media]
    assert all(item.parse_mode == "HTML" for item in calls[0].media)
    assert [item.caption for item in calls[0].media] == [item.caption for item in media]
    assert "reply_markup" not in calls[0].model_dump()
    assert captured == [99, *range(201, 202 + count)]
    assert message_id == 201 + count


@pytest.mark.parametrize("fail_at", [2, 3, 4])
async def test_partial_failure_retains_already_delivered_ids_and_does_not_retry(telegram_transport, fail_at):
    bot, calls, transport = telegram_transport
    transport["fail_at"] = fail_at
    captured = []
    screen = delivery(
        messages=("First chunk",),
        media=(ScreenMedia(kind="photo", file_id="cached-file", caption=None),),
    )
    with pytest.raises(TelegramServerError, match="Modeled delivery failure"):
        await send_screen(bot, screen, delivered=captured)
    assert len(calls) == fail_at
    assert captured == list(range(201, 200 + fail_at))


async def test_album_success_is_retained_when_the_following_primary_message_fails(telegram_transport):
    bot, calls, transport = telegram_transport
    transport["fail_at"] = 2
    captured = []
    screen = delivery(media=(ScreenMedia(kind="photo", file_id="photo"), ScreenMedia(kind="video", file_id="video")))
    with pytest.raises(TelegramServerError):
        await send_screen(bot, screen, delivered=captured)
    assert [type(call) for call in calls] == [SendMediaGroup, SendMessage]
    assert captured == [201, 202]


@pytest.mark.parametrize("failure", ["telegram", "unexpected", "cancelled"])
async def test_coordinator_persists_partial_ids_across_failure_restart_and_replay(telegram_flow, failure):
    from aiogram.methods import SendMessage
    from sqlalchemy import select

    from manashelper.modules.ui_flows.infrastructure.orm import UiScreenDelivery
    from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
    from tests.modules.ui_flows.telegram_factory import container_for
    from ui_flows.application.delivery import ScreenDeliveryService

    harness, container, pool = telegram_flow
    await harness.message("/flow_demo", 7510)
    # The demo's next screen sends a keyboard-removal message followed by inline actions.
    # Interrupt the second call after the first response has returned its durable message ID.
    count = 0

    async def interrupt(method):
        nonlocal count
        if not isinstance(method, SendMessage):
            return
        count += 1
        if count == 2:
            if failure == "telegram":
                raise TelegramServerError(method=method, message="Modeled partial screen failure")
            if failure == "unexpected":
                raise RuntimeError("Modeled partial screen failure")
            asyncio.current_task().cancel()
            await asyncio.sleep(0)

    harness.network_hook = interrupt
    coordinator = await container.get(FlowTelegramCoordinator)
    attempt = coordinator.message(harness.bot, harness.user_id, 7511, "Open form")
    if failure == "telegram":
        await attempt
    else:
        with pytest.raises(RuntimeError if failure == "unexpected" else asyncio.CancelledError):
            await asyncio.create_task(attempt)
    async with pool() as observer:
        saved = await observer.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 7511))
        assert saved.status == "unknown" and saved.message_id is None
        assert saved.message_ids == [harness.next_id]
        token, message_ids = saved.token, saved.message_ids
    calls = len(harness.calls)
    harness.network_hook = None
    async with container_for(pool) as restarted:
        async with restarted() as request:
            assert await (await request.get(ScreenDeliveryService)).claim(token) is None
        await (await restarted.get(FlowTelegramCoordinator)).message(harness.bot, harness.user_id, 7511, "Open form")
    assert len(harness.calls) == calls
    async with pool() as observer:
        assert (await observer.get(UiScreenDelivery, token)).message_ids == message_ids
