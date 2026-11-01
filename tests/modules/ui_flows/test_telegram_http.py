import os

import httpx
import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from sqlalchemy import select

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiScreenDelivery
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.users.infrastructure.user import User
from tests.modules.ui_flows.telegram_factory import container_for

SIMULATION_URL = os.getenv("MANASHELPER_TELEGRAM_SIMULATION_URL")
pytestmark = pytest.mark.skipif(not SIMULATION_URL, reason="Optional local Postman Telegram simulation")


@pytest_asyncio.fixture(autouse=True)
async def allow_http_test_launches(isolated_flow_pool):
    from manashelper.modules.ui_flows.infrastructure.orm import UiFlowRollout

    async with isolated_flow_pool.begin() as session:
        session.add(UiFlowRollout(id=1, mode="all", revision=0))


async def test_simulation_rejects_editing_a_reply_keyboard_removal_message():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

    async with httpx.AsyncClient() as http:
        (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
    async with Bot(
        token="123456:development-placeholder", session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL))
    ) as bot:
        message = await bot.send_message(910008, "Documented editing restriction", reply_markup=ReplyKeyboardRemove())
        with pytest.raises(TelegramBadRequest, match="message can't be edited"):
            await bot.edit_message_reply_markup(
                chat_id=910008,
                message_id=message.message_id,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Action", callback_data="uf:test:0")]]
                ),
            )


@pytest.mark.parametrize("user_id, expected_status", [(910008, "sent"), (910006, "unknown"), (910002, "failed")])
async def test_real_aiogram_client_and_persisted_delivery_outcome(isolated_flow_pool, user_id, expected_status):
    pool = isolated_flow_pool
    async with pool.begin() as session:
        session.add(User(id=user_id, full_name="HTTP flow", locale="en"))
    async with httpx.AsyncClient() as http:
        (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
        async with (
            Bot(
                token="123456:development-placeholder",
                session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
            ) as bot,
            container_for(pool) as container,
        ):
            coordinator = await container.get(FlowTelegramCoordinator)
            await coordinator.demo(bot, user_id, 900)
            await coordinator.demo(bot, user_id, 900)
            requests = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert len(requests) == 1  # No retry, including after the synthetic HTTP 500.
            async with pool() as session:
                state = await session.scalar(select(UiDialogSession))
                delivery = await session.scalar(select(UiScreenDelivery))
                assert state.node_id == "menu"
                assert delivery.status == expected_status
                assert (await session.get(User, user_id)).bot_stopped is (expected_status == "failed")
            if expected_status == "sent":
                await coordinator.message(bot, user_id, 901, "Open form")
                requests = (await http.get(f"{SIMULATION_URL}/_requests")).json()
                assert [call["method"] for call in requests] == ["sendMessage", "sendMessage", "sendMessage"]
                assert requests[-2]["reply_markup"] == {"remove_keyboard": True}
                data = requests[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                assert data.startswith("uf:") and len(data.encode()) <= 64
                from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback

                callback = UiFlowCallback.unpack(data)
                await coordinator.callback(
                    bot, user_id, 902, callback.token, callback.index, int(requests[-1]["message_id"]), "http-query"
                )
                requests = (await http.get(f"{SIMULATION_URL}/_requests")).json()
                assert [call["method"] for call in requests][-2:] == ["answerCallbackQuery", "sendMessage"]


async def test_partial_inline_delivery_and_explicit_resume(isolated_flow_pool):
    pool, user_id = isolated_flow_pool, 910009
    async with pool.begin() as session:
        session.add(User(id=user_id, full_name="Partial HTTP flow", locale="en"))
    async with httpx.AsyncClient() as http:
        await http.post(f"{SIMULATION_URL}/_reset")
        async with (
            Bot(
                token="123456:development-placeholder",
                session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
            ) as bot,
            container_for(pool) as container,
        ):
            coordinator = await container.get(FlowTelegramCoordinator)
            await coordinator.demo(bot, user_id, 910)
            await http.post(f"{SIMULATION_URL}/_fail_inline", json={"chat_id": user_id})
            await coordinator.message(bot, user_id, 911, "Open form")
            async with pool() as session:
                assert (await session.scalar(select(UiDialogSession))).node_id == "answer"
                delivery = await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 911))
                assert delivery.status == "unknown"
            before = len((await http.get(f"{SIMULATION_URL}/_requests")).json())
            await coordinator.message(bot, user_id, 911, "Open form")
            assert len((await http.get(f"{SIMULATION_URL}/_requests")).json()) == before
            await http.post(f"{SIMULATION_URL}/_reset")
            await coordinator.demo(bot, user_id, 912)
            requests = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert [call["method"] for call in requests] == ["sendMessage", "sendMessage"]


async def test_real_http_handoff_to_settings_is_not_repeated(isolated_flow_pool):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Chat, Message

    from manashelper.modules.ui_flows.infrastructure.orm import UiUserLocation
    from manashelper.modules.ui_flows.presentation.features import TelegramFlowContext
    from ui_flows.domain.delivery import Screen

    pool, user_id = isolated_flow_pool, 910008
    async with pool.begin() as session:
        session.add(User(id=user_id, full_name="HTTP menu pilot", locale="en"))
    async with httpx.AsyncClient() as http:
        await http.post(f"{SIMULATION_URL}/_reset")
        async with (
            Bot(
                token="123456:development-placeholder",
                session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
            ) as bot,
            container_for(pool) as container,
        ):
            coordinator = await container.get(FlowTelegramCoordinator)
            await coordinator.menu(bot, user_id, 950)
            async with pool() as session:
                delivery = await session.scalar(select(UiScreenDelivery))
                screen = Screen.model_validate(delivery.screen)
                label = next(button.label for row in screen.buttons for button in row if button.id == "settings")
            state = FSMContext(MemoryStorage(), StorageKey(bot.id, user_id, user_id))
            incoming = Message(message_id=951, date=0, chat=Chat(id=user_id, type="private"), text=label).as_(bot)
            context = TelegramFlowContext(incoming, state)
            await coordinator.message(bot, user_id, 951, label, context)
            await coordinator.message(bot, user_id, 951, label, context)
            calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert [call["method"] for call in calls] == ["sendMessage", "sendMessage"]
            assert calls[-1]["reply_markup"]["inline_keyboard"]
            async with pool() as session:
                assert (await session.get(UiUserLocation, user_id)).owner == "legacy"
                assert (
                    await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 951))
                ).status == "sent"


@pytest.mark.parametrize("rollback", [False, True])
async def test_real_http_survey_saves_once_and_returns_to_runtime_menu(isolated_flow_pool, rollback):
    from manashelper.modules.student_questions.orm import StudentQuestionsResponse
    from manashelper.modules.ui_flows.infrastructure.orm import UiUserLocation
    from ui_flows.domain.delivery import Screen

    pool, user_id = isolated_flow_pool, 910008
    async with pool.begin() as session:
        session.add(User(id=user_id, full_name="HTTP survey pilot", locale="en"))
    async with httpx.AsyncClient() as http:
        (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
        async with (
            Bot(
                token="123456:development-placeholder",
                session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
            ) as bot,
            container_for(pool) as container,
        ):
            coordinator = await container.get(FlowTelegramCoordinator)
            await coordinator.survey(bot, user_id, 970)
            for previous_update, update_id, id in ((970, 971, "year_1"), (971, 972, "no"), (972, 973, "yes")):
                if rollback and update_id == 973:
                    from manashelper.modules.ui_flows.application.rollout import RolloutService

                    async with container() as request:
                        await (await request.get(RolloutService)).set("off", 0, user_id)
                async with pool() as session:
                    delivery = await session.scalar(
                        select(UiScreenDelivery).where(UiScreenDelivery.update_id == previous_update)
                    )
                    screen = Screen.model_validate(delivery.screen)
                    index = [button.id for row in screen.buttons for button in row].index(id)
                await coordinator.callback(
                    bot, user_id, update_id, delivery.token, index, delivery.message_id, f"survey-{update_id}"
                )
            calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            messages = [call for call in calls if call["method"] == "sendMessage"]
            assert len(messages) == 7
            assert "Thank you" in messages[-1]["text"]
            assert messages[-1]["reply_markup"]["keyboard"]
            await coordinator.callback(
                bot, user_id, 973, delivery.token, index, delivery.message_id, "repeat-survey-final"
            )
            repeated = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert len([call for call in repeated if call["method"] == "sendMessage"]) == 7
            async with pool() as session:
                assert (await session.get(StudentQuestionsResponse, user_id)).wants_beta
                location = await session.get(UiUserLocation, user_id)
                state = await session.get(UiDialogSession, location.session_id)
                if rollback:
                    assert location.owner == "unknown" and state.flow_id == "student_questions"
                    assert state.status == "completed"
                else:
                    assert location.owner == "runtime" and state.flow_id == "main_menu" and state.node_id == "main"
