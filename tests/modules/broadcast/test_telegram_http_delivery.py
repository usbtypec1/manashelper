import os

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from manashelper.modules.broadcast.sender import TelegramBroadcastSender
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository

SIMULATION_URL = os.getenv("MANASHELPER_TELEGRAM_SIMULATION_URL")
pytestmark = pytest.mark.skipif(not SIMULATION_URL, reason="Optional local Postman Telegram simulation")


async def test_real_client_serialization_and_delivery_failure_flags(session):
    ids = list(range(910001, 910008))
    session.add_all(User(id=user_id, full_name="Synthetic recipient", locale="en") for user_id in ids)
    await session.flush()
    users = UserRepository(session)
    status = BotStatusService(users)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Site", url="https://example.com")],
            [InlineKeyboardButton(text="Menu", callback_data="food_menu:0")],
        ]
    )
    async with httpx.AsyncClient() as http:
        response = await http.post(f"{SIMULATION_URL}/_reset")
        response.raise_for_status()
        api = TelegramAPIServer.from_base(SIMULATION_URL)
        async with Bot(
            token="123456:development-placeholder",
            session=AiohttpSession(api=api),
            default=DefaultBotProperties(parse_mode="HTML"),
        ) as bot:
            sender = TelegramBroadcastSender(
                bot, LocaleService(users), status, photo_id="cached-photo-id", keyboard=keyboard
            )
            assert await sender.send(ids[0], "Hello <students>") is True
            for user_id in ids[1:]:
                assert await sender.send(user_id, "Hello") is False
            for user_id in ids[1:4]:
                assert await status.is_stopped(user_id)
                assert await sender.send(user_id, "Do not send again") is False
            for user_id in [ids[0], *ids[4:]]:
                assert not await status.is_stopped(user_id)
            requests = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert len(requests) == 7
            first = requests[0]
            assert first["method"] == "sendPhoto" and first["photo"] == "cached-photo-id"
            assert "Hello &lt;students&gt;" in first["caption"]
            assert first["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://example.com"
            assert first["reply_markup"]["inline_keyboard"][1][0]["callback_data"] == "food_menu:0"

            # The text path uses the same status tracking and preserves native keyboard serialization.
            text_sender = TelegramBroadcastSender(bot, LocaleService(users), status, keyboard=keyboard)
            assert await text_sender.send(ids[0], "Text only") is True
            requests = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert len(requests) == 8 and requests[-1]["method"] == "sendMessage"
