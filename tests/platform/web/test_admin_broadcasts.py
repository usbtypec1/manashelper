from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from aiogram import Bot, Dispatcher
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from manashelper.core.config import get_settings
from manashelper.modules.broadcast.application.campaigns import Audience, CampaignDraft, MessageVariant
from manashelper.modules.broadcast.application.queries import CampaignsQuery
from manashelper.modules.broadcast.application.use_cases.create_campaign import CreateCampaignUseCase
from manashelper.modules.broadcast.application.use_cases.retry_campaign import RetryCampaignUseCase
from manashelper.modules.broadcast.infrastructure.repositories.campaign import CampaignRepository
from manashelper.modules.broadcast.sender import TelegramCampaignDelivery
from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.users.application.bot_status import BotStatusQuery
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.telegram.outbox.models import OutboxMessage
from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import OutboxService
from manashelper.platform.web.server import create_web_app
from tests.platform.web.factories import TOKEN, USER_ID, authorization


def test_audience_modes_select_the_requested_users():
    variants = (MessageVariant(None, None, "Test"),)
    for audience, included in [(Audience.ALL, {1, 2}), (Audience.ALLOWLIST, {1}), (Audience.BLOCKLIST, {2})]:
        draft = CampaignDraft(uuid4(), audience, frozenset({1}) if audience != Audience.ALL else frozenset(), variants)
        assert {user_id for user_id in (1, 2) if draft.includes(user_id)} == included


async def test_admin_queues_localized_broadcast_and_retries_only_eligible_deliveries(session):
    users = [
        User(id=910_100, full_name="Exact", locale="en", theme="gta_vi"),
        User(id=910_101, full_name="Language only", locale="en", theme="basic"),
        User(id=910_102, full_name="Theme only", locale="ky", theme="gta_vi"),
        User(id=910_103, full_name="Fallback", locale="tr", theme="basic"),
        User(id=910_104, full_name="Stopped", bot_stopped=True),
        User(id=910_105, full_name="Muted"),
        User(id=910_107, full_name="Blocked", is_blocked=True),
        User(id=910_106, full_name="Not selected"),
    ]
    session.add_all(users)
    await session.flush()
    session.add(NotificationSettings(user_id=910_105, broadcast_muted_until=datetime.now(UTC) + timedelta(days=1)))
    outbox = OutboxRepository(session)
    recipients = NotificationRecipientsQuery(NotificationSettingsRepository(session))
    campaigns = CampaignRepository(session)
    user_repository = UserRepository(session)
    sender = TelegramCampaignDelivery(OutboxService(outbox, BotStatusQuery(user_repository)))
    services = {
        UsersQuery: UsersQuery(user_repository),
        CreateCampaignUseCase: CreateCampaignUseCase(campaigns, recipients, sender),
        CampaignsQuery: CampaignsQuery(campaigns, outbox),
        RetryCampaignUseCase: RetryCampaignUseCase(campaigns, recipients, outbox),
    }

    @asynccontextmanager
    async def container():
        async def get(service):
            return services[service]

        yield SimpleNamespace(get=get)

    settings = get_settings().model_copy(update={"telegram_bot_token": TOKEN, "admin_user_ids": frozenset({USER_ID})})
    campaign_id = uuid4()
    draft = {
        "id": str(campaign_id),
        "audience": "allowlist",
        "user_ids": [str(user.id) for user in users[:-1]],
        "variants": [
            {"locale": "en", "theme": "gta_vi", "text": "Exact <first>"},
            {"locale": "en", "theme": None, "text": "Language only"},
            {"locale": None, "theme": "gta_vi", "text": "Theme only"},
        ],
    }
    path = "/api/admin/broadcasts"
    detail_path = f"{path}/{campaign_id}"
    credentials = {"Authorization": authorization()}
    async with (
        Bot(TOKEN) as bot,
        TestClient(TestServer(create_web_app(bot, Dispatcher(), container, settings))) as client,
    ):
        response = await client.post(path, json=draft)
        assert response.status == 401
        denied = {"Authorization": authorization(USER_ID + 1)}
        assert (await client.post(path, json=draft, headers=denied)).status == 403
        assert (await client.get(path, headers=denied)).status == 403
        assert (await client.post(detail_path + "/retry", headers=denied)).status == 403
        invalid = {**draft, "variants": [draft["variants"][0]] * 2}
        assert (await client.post(path, json=invalid, headers=credentials)).status == 400
        invalid_audience = {**draft, "user_ids": []}
        assert (await client.post(path, json=invalid_audience, headers=credentials)).status == 400

        for _ in range(2):
            response = await client.post(path, json=draft, headers=credentials)
            assert response.status == 201
            assert await response.json() == {"id": str(campaign_id)}
        conflict = {**draft, "variants": [{"text": "Different"}]}
        assert (await client.post(path, json=conflict, headers=credentials)).status == 409

        statement = select(OutboxMessage).where(OutboxMessage.batch_id == campaign_id).order_by(OutboxMessage.user_id)
        deliveries = list(await session.scalars(statement))
        assert [row.user_id for row in deliveries] == [user.id for user in users[:4]]
        for row, text in zip(
            deliveries, ["Exact &lt;first&gt;", "Language only", "Theme only", "Exact &lt;first&gt;"], strict=True
        ):
            assert row.category == "broadcast"
            assert text in row.methods[0]["data"]["text"]
            assert row.methods[0]["data"]["reply_markup"]["inline_keyboard"]
            assert "disable_notification" in row.methods[0]["data"]

        now = datetime.now(UTC)
        for row, status in zip(deliveries, ("sent", "failed", "expired", "cancelled"), strict=True):
            row.status = status
            row.finished_at = now - timedelta(days=2)
            row.attempts = 2
        users[2].bot_stopped = True
        await session.flush()
        await outbox.cleanup(now)
        assert len(list(await session.scalars(statement))) == 4
        response = await client.get(detail_path, headers=credentials)
        assert response.headers["Cache-Control"] == "no-store"
        detail = await response.json()
        assert detail["variants"] == draft["variants"]
        assert detail["counts"] == {"sent": 1, "failed": 1, "expired": 1, "cancelled": 1}
        response = await client.get(path, headers=credentials)
        page = await response.json()
        assert any(item["id"] == str(campaign_id) for item in page["campaigns"])

        response = await client.post(detail_path + "/retry", headers=credentials)
        assert await response.json() == {"retried": 2}
        response = await client.post(detail_path + "/retry", headers=credentials)
        assert await response.json() == {"retried": 0}
        response = await client.get(detail_path + "/deliveries", headers=credentials)
        page = await response.json()
        assert [row["status"] for row in page["deliveries"]] == ["sent", "pending", "expired", "pending"]
        assert all(row["attempts"] == 2 for row in page["deliveries"])
