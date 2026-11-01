import asyncio
import re

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import select

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiScreenDelivery
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.platform.telegram.audit.orm import ActionLog
from manashelper.platform.web.auth import token_digest
from manashelper.platform.web.orm import AdminLoginTicket
from tests.modules.ui_flows.telegram_factory import container_for
from ui_flows.application.dialogs import DialogService
from ui_flows.domain.state import RuntimeUser


async def active(container, user_id):
    async with container() as request:
        return await (await request.get(DialogService)).active(RuntimeUser(user_id, user_id))


async def test_first_profile_commits_before_runtime_and_delivery(telegram_flow):
    harness, container, pool = telegram_flow
    observed = []

    async def network(method):
        if isinstance(method, SendMessage):
            async with pool() as session:
                delivery = await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.status == "unknown"))
                state = await session.scalar(select(UiDialogSession))
                assert delivery is not None and state.node_id == "menu"
                observed.append(delivery.status)

    harness.network_hook = network
    await asyncio.wait_for(harness.message("/flow_demo", 100), 5)
    assert observed == ["unknown"]
    assert (await active(container, harness.user_id)).node_id == "menu"
    async with pool() as session:
        assert (await session.scalar(select(UiScreenDelivery))).status == "sent"


async def test_reply_input_inline_and_old_callback_with_masked_audit(telegram_flow):
    harness, container, pool = telegram_flow
    await harness.message("/flow_demo", 110)
    label = next(method for method in harness.calls if isinstance(method, SendMessage)).reply_markup.keyboard[0][0].text
    await harness.message(label, 111)
    assert (await active(container, harness.user_id)).node_id == "answer"
    first = next(
        method
        for method in harness.calls
        if isinstance(method, SendMessage) and isinstance(method.reply_markup, InlineKeyboardMarkup)
    )
    async with pool() as session:
        first_delivery = await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 111))
    old_payload = first.reply_markup.inline_keyboard[0][0].callback_data
    await harness.message("<private answer>", 112)
    assert (await active(container, harness.user_id)).node_id == "confirm"
    current = [
        method
        for method in harness.calls
        if isinstance(method, SendMessage) and isinstance(method.reply_markup, InlineKeyboardMarkup)
    ][-1]
    async with pool() as session:
        current_delivery = await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 112))
    await harness.callback(old_payload, first_delivery.message_id, 113)
    assert isinstance(harness.calls[-1], AnswerCallbackQuery) and harness.calls[-1].show_alert
    assert (await active(container, harness.user_id)).node_id == "confirm"
    await harness.callback(current.reply_markup.inline_keyboard[0][0].callback_data, current_delivery.message_id, 114)
    assert not any(isinstance(method, EditMessageReplyMarkup) for method in harness.calls)
    assert await active(container, harness.user_id) is None
    assert any("&lt;private answer&gt;" in method.text for method in harness.calls if isinstance(method, SendMessage))
    async with pool() as session:
        texts = list(await session.scalars(select(ActionLog.message_text)))
        assert "<private answer>" not in texts and "[masked]" in texts


async def test_resume_in_new_container_does_not_repeat_entry_action(telegram_flow):
    harness, container, pool = telegram_flow
    await harness.message("/flow_demo", 120)
    await harness.message("Open form", 121)
    before = await active(container, harness.user_id)
    async with container_for(pool) as recreated:
        coordinator = await recreated.get(FlowTelegramCoordinator)
        await coordinator.demo(harness.bot, harness.user_id, 122)
        assert await active(recreated, harness.user_id) == before
    assert isinstance(harness.calls[-1], SendMessage)
    assert isinstance(harness.calls[-1].reply_markup, InlineKeyboardMarkup)


async def test_locale_change_keeps_form_and_back_cancels_it(telegram_flow):
    harness, container, _ = telegram_flow
    await harness.message("/flow_demo", 130)
    await harness.message("Open form", 131)
    before = await active(container, harness.user_id)
    from manashelper.localization.locale import Locale
    from manashelper.modules.users.presentation.callbacks import LocaleCallback

    await harness.callback(LocaleCallback(locale=Locale.RU).pack(), 500, 132)
    assert await active(container, harness.user_id) == before
    assert any("Введите короткий текст" in method.text for method in harness.calls if isinstance(method, SendMessage))
    from manashelper.platform.i18n.catalog import i18n

    with i18n.context(), i18n.use_locale("ru"):
        back = i18n.gettext("common.back_to_menu")
    await harness.message(back, 133)
    current = await active(container, harness.user_id)
    assert current.flow_id == "main_menu" and current.node_id == "main"
    async with container() as request:
        assert (
            await (await request.get(DialogService)).get(before.id, RuntimeUser(harness.user_id, harness.user_id))
        ).status == "cancelled"


async def test_failed_delivery_is_not_retried_and_resume_restores_step(telegram_flow):
    harness, container, pool = telegram_flow

    async def fail(method):
        if isinstance(method, SendMessage):
            raise TelegramNetworkError(method=method, message="Synthetic timeout")

    harness.network_hook = fail
    await harness.message("/flow_demo", 140)
    state = await active(container, harness.user_id)
    assert state.node_id == "menu"
    async with pool() as session:
        assert (await session.scalar(select(UiScreenDelivery))).status == "unknown"
    await harness.message("/flow_demo", 140)
    assert len([method for method in harness.calls if isinstance(method, SendMessage)]) == 1
    harness.network_hook = None
    await harness.message("/flow_demo", 141)
    assert await active(container, harness.user_id) == state
    assert len([method for method in harness.calls if isinstance(method, SendMessage)]) == 2


async def test_non_admin_and_group_cannot_start_demo(telegram_flow):
    harness, container, pool = telegram_flow
    await harness.message("/flow_demo", 150, user_id=harness.user_id + 1)
    await harness.message("/flow_demo", 151, chat_type="group")
    async with pool() as session:
        assert await session.scalar(select(UiDialogSession)) is None


async def test_chat_ordering_includes_network_delivery(telegram_flow):
    harness, container, _ = telegram_flow
    sending, release = asyncio.Event(), asyncio.Event()

    async def pause(method):
        if isinstance(method, SendMessage) and not release.is_set():
            sending.set()
            await release.wait()

    harness.network_hook = pause
    first = asyncio.create_task(harness.message("/flow_demo", 160))
    await asyncio.wait_for(sending.wait(), 5)
    second = asyncio.create_task(harness.message("Open form", 161))
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), 0.05)
        assert (await active(container, harness.user_id)).node_id == "menu"
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 5)
    assert (await active(container, harness.user_id)).node_id == "answer"


async def test_commit_failure_never_sends_prepared_screen(telegram_flow, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from tests.modules.ui_flows.telegram_factory import TelegramHarness, dispatcher_for

    harness, _, pool = telegram_flow

    class FailIntentCommit(AsyncSession):
        async def commit(self):
            if await self.scalar(select(UiScreenDelivery)) is not None:
                raise RuntimeError("synthetic commit failure")
            await super().commit()

    failing_pool = async_sessionmaker(pool.kw["bind"], class_=FailIntentCommit, expire_on_commit=False)
    async with container_for(failing_pool) as container:
        test = TelegramHarness(harness.bot, dispatcher_for(container, harness.user_id), harness.user_id)
        monkeypatch.setattr(harness.bot.session, "make_request", test.respond)
        with pytest.raises((RuntimeError, ExceptionGroup)):
            await test.message("/flow_demo", 170)
        assert not test.calls
    async with pool() as session:
        assert await session.scalar(select(UiScreenDelivery)) is None
        assert await session.scalar(select(UiDialogSession)) is None


async def test_editor_link_is_private_and_sent_after_ticket_commit(telegram_flow, monkeypatch):
    from manashelper.core.config import get_settings

    harness, _, pool = telegram_flow
    monkeypatch.setenv("MANASHELPER_ADMIN_WEB_ORIGIN", "https://admin.test")
    monkeypatch.setenv("MANASHELPER_ADMIN_WEB_SIGNING_KEY", "synthetic-admin-signing-key-only-for-tests")
    get_settings.cache_clear()
    tickets = []

    async def network(method):
        if isinstance(method, SendMessage):
            match = re.search(r"#ticket=([A-Za-z0-9_-]+)", method.text)
            assert match is not None
            tickets.append(match[1])
            async with pool() as session:
                assert await session.get(AdminLoginTicket, token_digest(match[1])) is not None
            assert method.disable_web_page_preview

    harness.network_hook = network
    await asyncio.wait_for(harness.message("/editor", 180), 5)
    assert len(tickets) == 1
    await harness.message("/editor", 181, user_id=harness.user_id + 1)
    await harness.message("/editor", 182, chat_type="group")
    assert len(tickets) == 1


async def test_editor_without_configuration_explains_unavailability(telegram_flow, monkeypatch):
    from manashelper.core.config import get_settings

    for name in ("MANASHELPER_ADMIN_WEB_ORIGIN", "MANASHELPER_ADMIN_WEB_SIGNING_KEY"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    harness, _, pool = telegram_flow
    await harness.message("/editor", 190)
    response = next(method for method in harness.calls if isinstance(method, SendMessage))
    assert "#ticket=" not in response.text
    async with pool() as session:
        assert await session.scalar(select(AdminLoginTicket)) is None


async def test_named_pilot_uses_published_schema_without_python_changes(telegram_flow):
    from manashelper.modules.ui_flows.demo import demo_document
    from ui_flows.application.flows import FlowService

    harness, container, _ = telegram_flow
    # Establish the profile before creating the published scenario, as production middleware does.
    await harness.message("/editor", 200)
    document = demo_document().model_copy(update={"id": "authored_in_editor"})
    async with container() as request:
        service = await request.get(FlowService)
        await service.create(document)
        await service.publish(document.id, 0, harness.user_id)
    await harness.message("/flow_demo authored_in_editor", 201)
    state = await active(container, harness.user_id)
    assert state.flow_id == document.id and state.node_id == "menu"
    await harness.message("/flow_demo missing_scenario", 202)
    assert await active(container, harness.user_id) == state
