import os
import re

import httpx
import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiohttp.test_utils import TestClient, TestServer
from pydantic import SecretStr
from sqlalchemy import func, select

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiScreenDelivery
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.users.infrastructure.user import User
from tests.modules.ui_flows.telegram_factory import container_for, dispatcher_for

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


async def test_real_http_delivery_uses_pinned_db_texts_without_file_translations(isolated_flow_pool, monkeypatch):
    from contextvars import ContextVar

    from manashelper.platform.i18n import catalog
    from manashelper.platform.i18n.repository import TextCatalogRepository
    from manashelper.platform.i18n.service import TextCatalogService

    def forbid_file_catalog(*args, **kwargs):
        raise AssertionError("User delivery must not read file translations")

    monkeypatch.setattr(catalog, "translation", forbid_file_catalog)
    # Unlike pure formatter fixtures, the real coordinator starts without an ambient snapshot.
    monkeypatch.setattr(catalog.CatalogI18n, "_catalog", ContextVar("http_catalog", default=None))
    pool, user_id = isolated_flow_pool, 910008
    async with pool.begin() as session:
        session.add(User(id=user_id, full_name="DB text delivery", locale="en"))

    async def publish_label(text):
        async with pool.begin() as session:
            service = TextCatalogService(TextCatalogRepository(session))
            draft = await service.draft()
            entry = next(item for item in draft.document.entries if item.key == "menu.food")
            entry = entry.model_copy(
                update={
                    "variants": tuple(
                        variant.model_copy(update={"text": text})
                        if variant.locale == "en" and variant.theme == "basic"
                        else variant
                        for variant in entry.variants
                    )
                }
            )
            saved = await service.save_entry(entry.key, entry, draft.revision)
            await service.publish(saved.revision, user_id)

    await publish_label("Pinned DB cafeteria")
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
            await coordinator.menu(bot, user_id, 119001)
            await publish_label("New current cafeteria")
            await coordinator.menu(bot, user_id, 119002)
            calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert len(calls) == 2
            assert all(call["reply_markup"]["keyboard"][0][0]["text"] == "Pinned DB cafeteria" for call in calls)
            async with pool() as session:
                deliveries = (await session.scalars(select(UiScreenDelivery))).all()
                assert {row.screen["text_catalog_release"] for row in deliveries} == {2}
            await coordinator.callback(bot, user_id, 119003, "expired-delivery", 0, 1, "expired-query")
            calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
            assert calls[-1]["method"] == "answerCallbackQuery" and calls[-1]["text"]


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


@pytest.mark.parametrize(
    "kinds,fail_inline",
    [
        (["photo"], False),
        (["video"], False),
        (["photo", "video"], False),
        (["photo"] * 10, False),
        (["photo", "video"], True),
    ],
)
async def test_rich_screen_real_http_serialization_ids_and_partial_failure(isolated_flow_pool, kinds, fail_inline):
    from manashelper.platform.i18n.request import catalog_request
    from ui_flows.application.dialogs import DialogService
    from ui_flows.application.flows import FlowService
    from ui_flows.domain.schema import FlowDocument
    from ui_flows.domain.state import RuntimeUser

    user = RuntimeUser(910008, 910008)
    async with isolated_flow_pool.begin() as session:
        session.add(User(id=user.id, full_name="Rich HTTP screen", locale="en"))
    document = FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "rich_http",
            "entry": "show",
            "fields": {
                "media": {
                    "type": "list",
                    "max_items": 10,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "text"},
                            "file_id": {"type": "text"},
                            "caption": {"type": "text"},
                        },
                    },
                }
            },
            "initial_data": {
                "media": [
                    {"type": kind, "file_id": f"file-{index}", "caption": "<safe & caption>"}
                    for index, kind in enumerate(kinds)
                ]
            },
            "nodes": [
                {
                    "kind": "menu",
                    "id": "show",
                    "keyboard": "inline",
                    "text": [{"kind": "inline", "translations": {"en": "Main screen"}}],
                    "messages": [{"kind": "inline", "translations": {"en": "<b>Before media</b>"}}],
                    "media": {"kind": "ref", "scope": "data", "field": "media"},
                    "buttons": [
                        [
                            {
                                "kind": "transition",
                                "id": "again",
                                "target": "show",
                                "label": {"kind": "inline", "translations": {"en": "Again"}},
                            }
                        ]
                    ],
                }
            ],
        }
    )
    async with (
        httpx.AsyncClient() as http,
        Bot(
            token="123456:development-placeholder",
            session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
        ) as bot,
        container_for(isolated_flow_pool) as container,
    ):
        (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
        if fail_inline:
            (await http.post(f"{SIMULATION_URL}/_fail_inline", json={"chat_id": user.chat_id})).raise_for_status()
        coordinator = await container.get(FlowTelegramCoordinator)
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            await flows.create(document)
            await flows.publish(document.id, 0, user.id)
            result = await (await request.get(DialogService)).start(document.id, user, 930)
            pending = await coordinator._prepare(request, result, user, 930)
        await coordinator._deliver(bot, pending)
        await coordinator._deliver(bot, pending)
        calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
        media_method = "sendMediaGroup" if len(kinds) > 1 else ("sendPhoto" if kinds[0] == "photo" else "sendVideo")
        assert [call["method"] for call in calls] == ["sendMessage", media_method, "sendMessage", "sendMessage"]
        assert calls[0]["text"] == "<b>Before media</b>"
        assert calls[2]["reply_markup"] == {"remove_keyboard": True}
        if len(kinds) > 1:
            assert [item["type"] for item in calls[1]["media"]] == kinds
            assert all(item["caption"] == "&lt;safe &amp; caption&gt;" for item in calls[1]["media"])
            media_ids = calls[1]["message_ids"]
        else:
            assert calls[1][kinds[0]] == "file-0" and calls[1]["caption"] == "&lt;safe &amp; caption&gt;"
            media_ids = [calls[1]["message_id"]]
        async with isolated_flow_pool() as observer:
            delivery = await observer.get(UiScreenDelivery, pending.token)
            assert delivery.status == ("unknown" if fail_inline else "sent")
            expected_ids = [calls[0]["message_id"], *media_ids, calls[2]["message_id"]]
            if not fail_inline:
                expected_ids.append(calls[3]["message_id"])
            assert delivery.message_ids == expected_ids
            assert delivery.message_id == (None if fail_inline else expected_ids[-1])


async def test_real_http_settings_scenario_is_not_repeated(isolated_flow_pool):
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
            assert [call["method"] for call in calls] == ["sendMessage", "sendMessage", "sendMessage"]
            assert calls[-2]["reply_markup"] == {"remove_keyboard": True}
            assert calls[-1]["reply_markup"]["inline_keyboard"]
            async with pool() as session:
                location = await session.get(UiUserLocation, user_id)
                assert location.owner == "runtime"
                assert (await session.get(UiDialogSession, location.session_id)).flow_id == "settings"
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


async def test_editor_opens_miniapp_and_preserves_single_use_browser_ticket_over_real_telegram_http(
    isolated_flow_pool, monkeypatch
):
    from manashelper.core.config import get_settings
    from manashelper.platform.web.auth import AdminAuthService, AuthenticationError, token_digest
    from manashelper.platform.web.login import AdminLoginCoordinator
    from manashelper.platform.web.orm import AdminLoginTicket

    pool, user_id = isolated_flow_pool, 910008
    monkeypatch.setenv("MANASHELPER_ADMIN_CHAT_ID", str(user_id))
    monkeypatch.setenv("MANASHELPER_ADMIN_WEB_ORIGIN", "https://admin.test")
    monkeypatch.setenv("MANASHELPER_ADMIN_WEB_SIGNING_KEY", "synthetic-admin-signing-key-only-for-tests")
    get_settings.cache_clear()
    try:
        async with pool.begin() as session:
            session.add(User(id=user_id, full_name="HTTP editor administrator", locale="en"))
        async with httpx.AsyncClient() as http:
            (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
            async with (
                Bot(
                    token="123456:development-placeholder",
                    session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
                ) as bot,
                container_for(pool) as container,
            ):
                await (await container.get(AdminLoginCoordinator)).open(bot, user_id)
                calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
                assert len(calls) == 1 and calls[0]["method"] == "sendMessage"
                assert calls[0]["chat_id"] == user_id
                button = calls[0]["reply_markup"]["inline_keyboard"][0][0]
                assert button["web_app"] == {"url": "https://admin.test/admin/"}
                assert "callback_data" not in button and "url" not in button
                match = re.search(r"https://admin\.test/admin/#ticket=([A-Za-z0-9_-]+)", calls[0]["text"])
                assert match is not None
                ticket = match.group(1)
                async with pool() as session:
                    row = await session.get(AdminLoginTicket, token_digest(ticket))
                    assert row is not None and row.user_id == user_id
                    assert ticket not in row.digest
                async with container() as request:
                    login = await (await request.get(AdminAuthService)).exchange(ticket)
                    assert login.admin.user_id == user_id
                async with container() as request:
                    with pytest.raises(AuthenticationError):
                        await (await request.get(AdminAuthService)).exchange(ticket)
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("unified", [False, True])
async def test_webhook_survey_final_callback_replay_preserves_one_response_and_delivery(
    isolated_flow_pool, monkeypatch, unified
):
    from manashelper.core.config import get_settings
    from manashelper.modules.student_questions.orm import StudentQuestionsResponse
    from manashelper.modules.ui_flows.infrastructure.orm import UiFlowEvent, UiUserLocation
    from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
    from manashelper.platform.telegram.dispatcher import on_error
    from manashelper.platform.web.application import create_admin_app
    from manashelper.platform.web.webhook import install_webhook
    from ui_flows.domain.delivery import Screen

    pool, user_id = isolated_flow_pool, 910008
    monkeypatch.setenv("MANASHELPER_ADMIN_CHAT_ID", str(user_id))
    get_settings.cache_clear()
    try:
        settings = get_settings().model_copy(update={"telegram_webhook_secret": SecretStr("synthetic-webhook-secret")})
        async with pool.begin() as session:
            session.add(User(id=user_id, full_name="HTTP webhook student", locale="en"))
        async with httpx.AsyncClient() as http:
            (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
            async with (
                Bot(
                    token="123456:development-placeholder",
                    session=AiohttpSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
                ) as bot,
                container_for(pool) as container,
            ):
                if unified:
                    await (await container.get(FlowTelegramCoordinator)).install_defaults(user_id)
                dispatch = dispatcher_for(container, user_id, ingress=unified)
                dispatch.errors.register(on_error)
                app = create_admin_app(settings, container)
                install_webhook(app, bot, dispatch, settings)
                headers = {"X-Telegram-Bot-Api-Secret-Token": "synthetic-webhook-secret"}
                user = {"id": user_id, "is_bot": False, "first_name": "Webhook student", "language_code": "en"}
                async with TestClient(TestServer(app)) as client:
                    started = await client.post(
                        "/telegram/webhook",
                        headers=headers,
                        json={
                            "update_id": 980,
                            "message": {
                                "message_id": 980,
                                "date": 0,
                                "chat": {"id": user_id, "type": "private"},
                                "from": user,
                                "text": "/start student_questions",
                            },
                        },
                    )
                    assert started.status == 200, await started.text()
                    for previous, update_id, button_id in ((980, 981, "year_1"), (981, 982, "no"), (982, 983, "yes")):
                        async with pool() as session:
                            delivery = await session.scalar(
                                select(UiScreenDelivery).where(UiScreenDelivery.update_id == previous)
                            )
                            screen = Screen.model_validate(delivery.screen)
                            index = [button.id for row in screen.buttons for button in row].index(button_id)
                        payload = {
                            "update_id": update_id,
                            "callback_query": {
                                "id": f"webhook-{update_id}",
                                "from": user,
                                "chat_instance": "webhook-survey",
                                "data": UiFlowCallback(token=delivery.token, index=index).pack(),
                                "message": {
                                    "message_id": delivery.message_id,
                                    "date": 0,
                                    "chat": {"id": user_id, "type": "private"},
                                    "from": {"id": bot.id, "is_bot": True, "first_name": "Bot"},
                                    "text": "Displayed survey screen",
                                },
                            },
                        }
                        response = await client.post("/telegram/webhook", headers=headers, json=payload)
                        assert response.status == 200, await response.text()
                    calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
                    messages = [call for call in calls if call["method"] == "sendMessage"]
                    assert len(messages) == 7 and "Thank you" in messages[-1]["text"]
                    repeated = await client.post("/telegram/webhook", headers=headers, json=payload)
                    assert repeated.status == 200, await repeated.text()
                    after_repeat = (await http.get(f"{SIMULATION_URL}/_requests")).json()
                    assert len([call for call in after_repeat if call["method"] == "sendMessage"]) == len(messages)
                    async with pool() as session:
                        assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 1
                        assert (await session.get(StudentQuestionsResponse, user_id)).wants_beta
                        assert (
                            await session.scalar(
                                select(func.count()).select_from(UiFlowEvent).where(UiFlowEvent.update_id == 983)
                            )
                            == 1
                        )
                        location = await session.get(UiUserLocation, user_id)
                        state = await session.get(UiDialogSession, location.session_id)
                        assert location.owner == "runtime" and state.flow_id == "main_menu"
                        if unified:
                            from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiIngressReceipt

                            assert state.trigger_release == 1
                            assert await session.scalar(select(func.count()).select_from(UiIngressReceipt)) == 4
                await dispatch.storage.close()
    finally:
        get_settings.cache_clear()
