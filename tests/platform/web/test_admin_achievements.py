from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from manashelper.core.config import get_settings
from manashelper.modules.gamification.application.catalog import ACHIEVEMENT_KEYS
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.grant_achievement import GrantAchievementUseCase
from manashelper.modules.gamification.application.use_cases.set_achievement_display import SetAchievementDisplayUseCase
from manashelper.modules.gamification.infrastructure.models.achievement import UserAchievement
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.queries import UsersQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.platform.telegram.outbox.models import OutboxMessage
from manashelper.platform.web.server import create_web_app
from tests.modules.gamification.factories import build_awards
from tests.platform.web.factories import TOKEN, USER_ID, authorization


async def test_admin_achievement_display_and_grant_use_signed_identity_and_persist(session):
    recipient_id = 2**63 - 1
    disabled_id = USER_ID + 1
    hidden_recipient_id = USER_ID + 2
    actor = User(id=USER_ID, full_name="Admin", locale="en")
    session.add_all(
        [
            actor,
            User(id=recipient_id, full_name="Recipient", locale="en"),
            User(id=disabled_id, full_name="Disabled"),
            User(id=hidden_recipient_id, full_name="Second recipient"),
        ]
    )
    await session.flush()
    settings = get_settings().model_copy(update={"telegram_bot_token": TOKEN, "admin_user_ids": frozenset({USER_ID})})
    repository = AchievementRepository(session)
    for user_id in (recipient_id, hidden_recipient_id):
        await repository.set_enabled(user_id, True)
    gamification = GamificationQuery(repository)
    users_repo = UserRepository(session)
    users = UsersQuery(users_repo)
    services = {
        GamificationQuery: gamification,
        UsersQuery: users,
        LocaleQuery: LocaleQuery(users_repo),
        ThemeQuery: ThemeQuery(users_repo),
        SetAchievementDisplayUseCase: SetAchievementDisplayUseCase(repository),
        GrantAchievementUseCase: GrantAchievementUseCase(build_awards(session), gamification, users),
    }

    @asynccontextmanager
    async def container():
        yield SimpleNamespace(get=AsyncMock(side_effect=services.__getitem__))

    prefix = "/api/admin/achievements"
    display_path = f"{prefix}/pokemon"
    grant_path = f"{display_path}/grants/{recipient_id}"
    admin = {"Authorization": authorization()}
    recipient = {"Authorization": authorization(recipient_id)}
    display = {"custom_name": "<Team award>", "hidden": False}
    async with (
        Bot(TOKEN) as bot,
        TestClient(TestServer(create_web_app(bot, Dispatcher(), container, settings))) as client,
    ):
        assert (await client.get(prefix)).status == 401
        assert (await client.get(prefix, headers=recipient)).status == 403
        assert (await client.put(display_path, json=display, headers=recipient)).status == 403
        assert (await client.put(grant_path, headers=recipient)).status == 403
        response = await client.get(prefix, headers=admin)
        assert response.status == 200 and response.headers["Cache-Control"] == "no-store"
        catalog = {entry["key"]: entry for entry in (await response.json())["achievements"]}
        assert set(catalog) == set(ACHIEVEMENT_KEYS)
        assert catalog["pokemon"]["custom_name"] is None and catalog["pokemon"]["hidden"] is False

        for body in (
            {"hidden": True},
            {**display, "hidden": "false"},
            {**display, "custom_name": "x" * 81},
            {**display, "custom_name": "First\x00Second"},
        ):
            assert (await client.put(display_path, json=body, headers=admin)).status == 400
        assert (await client.put(f"{prefix}/unknown", json=display, headers=admin)).status == 404
        assert (await client.put(f"{display_path}/grants/-1", headers=admin)).status == 400
        assert (await client.put(f"{display_path}/grants/{2**63}", headers=admin)).status == 400
        assert (await client.put(f"{display_path}/grants/{disabled_id}", headers=admin)).status == 409
        assert (await client.put(f"{display_path}/grants/{USER_ID + 3}", headers=admin)).status == 404

        response = await client.put(display_path, json=display, headers=admin)
        assert response.status == 200 and await response.json() == display
        for expected in ("granted", "already_granted"):
            response = await client.put(grant_path, headers=admin)
            assert response.status == 200 and (await response.json())["status"] == expected

        profile = await (await client.get("/api/gamification/me", headers=recipient)).json()
        assert profile["score"] == 1
        assert next(item for item in profile["achievements"] if item["key"] == "pokemon")["name"] == "<Team award>"
        leaderboard = await (await client.get("/api/gamification/leaderboard", headers=recipient)).json()
        assert leaderboard["entries"][0]["achievements"][0]["name"] == "<Team award>"

        award = await session.get(UserAchievement, (recipient_id, "pokemon"))
        assert award is not None and award.granted_by == USER_ID
        outbox = list(await session.scalars(select(OutboxMessage).where(OutboxMessage.user_id == recipient_id)))
        assert len(outbox) == 1 and "&lt;Team award&gt;" in outbox[0].methods[0]["data"]["text"]

        assert (await client.put(display_path, json={**display, "hidden": True}, headers=admin)).status == 200
        hidden_grant = await client.put(f"{display_path}/grants/{hidden_recipient_id}", headers=admin)
        assert (await hidden_grant.json())["status"] == "granted"
        assert await session.get(UserAchievement, (hidden_recipient_id, "pokemon")) is not None
        assert await session.scalar(select(OutboxMessage).where(OutboxMessage.user_id == hidden_recipient_id)) is None
        profile = await (await client.get("/api/gamification/me", headers=recipient)).json()
        assert (profile["score"], profile["total"], profile["rank"]) == (0, len(ACHIEVEMENT_KEYS) - 1, None)
        assert all(item["key"] != "pokemon" for item in profile["achievements"])
        leaderboard = await (await client.get("/api/gamification/leaderboard", headers=recipient)).json()
        assert all(entry["full_name"] != "Recipient" for entry in leaderboard["entries"])

        response = await client.put(display_path, json={"custom_name": None, "hidden": False}, headers=admin)
        assert response.status == 200
        profile = await (await client.get("/api/gamification/me", headers=recipient)).json()
        assert (profile["score"], profile["total"]) == (1, len(ACHIEVEMENT_KEYS))
        assert (
            next(item for item in profile["achievements"] if item["key"] == "pokemon")["name"]
            == (catalog["pokemon"]["default_name"])
        )

        actor.is_blocked = True
        await session.flush()
        assert (await client.get(prefix, headers=admin)).status == 403
