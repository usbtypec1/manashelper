from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
from aiohttp.test_utils import TestClient, TestServer

from manashelper.core.config import get_settings
from manashelper.modules.users.application.use_cases.set_user_blocked import SetUserBlockedUseCase
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.web.server import create_web_app
from tests.platform.web.factories import TOKEN, USER_ID, authorization


async def test_admin_users_authenticates_and_pages_through_public_profile_fields(session):
    settings = get_settings().model_copy(
        update={"telegram_bot_token": TOKEN, "admin_chat_id": -100123, "admin_user_ids": frozenset({USER_ID})}
    )
    query = UsersQuery(UserRepository(session))
    get = AsyncMock(return_value=query)

    @asynccontextmanager
    async def container():
        yield SimpleNamespace(get=get)

    first_id = 2**63 - 52
    for user_id in range(first_id, 2**63):
        session.add(
            User(
                id=user_id,
                full_name=f"Fixture <{user_id}>",
                username="fixture" if user_id == first_id else None,
                bot_stopped=user_id == first_id,
                student_number="not-for-the-panel",
                encrypted_password="not-for-the-panel",
            )
        )
    await session.flush()

    async with (
        Bot(TOKEN) as bot,
        TestClient(TestServer(create_web_app(bot, Dispatcher(), container, settings))) as client,
    ):
        path = "/api/admin/users"
        for header, expected in (
            ("", 401),
            (authorization(age=3601), 401),
            (authorization() + "0", 401),
            (authorization(-100123), 403),
            (authorization(USER_ID + 1), 403),
        ):
            response = await client.get(path, headers={"Authorization": header})
            assert response.status == expected
            assert response.headers["Cache-Control"] == "no-store"
        get.assert_not_awaited()

        headers = {"Authorization": authorization()}
        for cursor in ("none", str(2**63), str(-(2**63) - 1)):
            response = await client.get(path, params={"after": cursor}, headers=headers)
            assert response.status == 400

        response = await client.get(path, params={"after": str(first_id - 1)}, headers=headers)
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        page = await response.json()
        assert [row["id"] for row in page["users"]] == [str(user_id) for user_id in range(first_id, first_id + 50)]
        assert page["users"][0] == {
            "id": str(first_id),
            "full_name": f"Fixture <{first_id}>",
            "username": "fixture",
            "locale": "ru",
            "theme": "basic",
            "bot_stopped": True,
            "is_blocked": False,
        }
        assert page["next_cursor"] == str(first_id + 49)
        response = await client.get(path, params={"after": page["next_cursor"]}, headers=headers)
        last_page = await response.json()
        assert [row["id"] for row in last_page["users"]] == [str(first_id + 50), str(first_id + 51)]
        assert last_page["users"][0]["username"] is None
        assert last_page["next_cursor"] is None

        response = await client.get(
            path,
            params={"after": str(first_id - 1), "q": "@fix", "status": "stopped", "locale": "ru", "theme": "basic"},
            headers=headers,
        )
        assert (await response.json())["users"] == [page["users"][0]]
        response = await client.get(path, params={"after": str(first_id - 1), "locale": "en"}, headers=headers)
        assert (await response.json())["users"] == []
        for params in ({"theme": "unknown"}, {"status": "invalid"}, {"q": "x" * 129}):
            assert (await client.get(path, params=params, headers=headers)).status == 400


async def test_blocking_from_admin_closes_private_apis_until_admin_unblocks(session):
    actor_id, target_id = USER_ID, USER_ID + 1
    session.add_all([User(id=actor_id, full_name="Admin"), User(id=target_id, full_name="Target")])
    await session.flush()
    settings = get_settings().model_copy(
        update={"telegram_bot_token": TOKEN, "admin_user_ids": frozenset({actor_id, target_id})}
    )
    repository = UserRepository(session)
    services = {UsersQuery: UsersQuery(repository), SetUserBlockedUseCase: SetUserBlockedUseCase(repository)}

    @asynccontextmanager
    async def container():
        yield SimpleNamespace(get=AsyncMock(side_effect=services.__getitem__))

    admin = {"Authorization": authorization(actor_id)}
    target = {"Authorization": authorization(target_id)}
    outsider = {"Authorization": authorization(target_id + 1)}
    path = f"/api/admin/users/{target_id}/blocked"
    async with (
        Bot(TOKEN) as bot,
        TestClient(TestServer(create_web_app(bot, Dispatcher(), container, settings))) as client,
    ):
        assert (await client.put(path, json={"blocked": True}, headers=outsider)).status == 403
        assert (await client.put(path, json={"blocked": "true"}, headers=admin)).status == 400
        self_block = f"/api/admin/users/{actor_id}/blocked"
        assert (await client.put(self_block, json={"blocked": True}, headers=admin)).status == 403
        for _ in range(2):
            response = await client.put(path, json={"blocked": True}, headers=admin)
            assert response.status == 200 and await response.json() == {"is_blocked": True}

        for api in (
            "/api/settings",
            "/api/studies/faculties",
            "/api/gamification/me",
            "/api/gamification/leaderboard",
            "/api/admin/users",
            "/api/admin/broadcasts",
        ):
            response = await client.get(api, headers=target)
            assert response.status == 403 and response.headers["Cache-Control"] == "no-store"
        assert (await client.put(path, json={"blocked": False}, headers=target)).status == 403
        response = await client.get(
            "/api/admin/users", params={"status": "blocked", "q": str(target_id)}, headers=admin
        )
        assert [user["id"] for user in (await response.json())["users"]] == [str(target_id)]

        response = await client.put(path, json={"blocked": False}, headers=admin)
        assert response.status == 200 and await response.json() == {"is_blocked": False}
        assert (await client.get("/api/admin/users", headers=target)).status == 200
