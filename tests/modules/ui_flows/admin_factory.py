from dataclasses import dataclass

import httpx
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.core.provider import CoreProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.ui_flows.presentation.admin_provider import AdminUiFlowsProvider
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.web.auth import AdminAuthService
from manashelper.platform.web.provider import WebPlatformProvider


def admin_container(pool):
    class Pool(Provider):
        @provide(scope=Scope.APP, override=True)
        def session_pool(self) -> async_sessionmaker[AsyncSession]:
            return pool

    return make_async_container(
        CoreProvider(),
        StudentQuestionsProvider(),
        UsersProvider(),
        UiFlowsProvider(),
        WebPlatformProvider(),
        AdminUiFlowsProvider(),
        Pool(),
    )


@dataclass
class AdminHarness:
    client: httpx.AsyncClient
    container: object
    pool: object
    app: object
    user_id: int

    async def ticket(self):
        async with self.container() as request:
            return await (await request.get(AdminAuthService)).issue(self.user_id)

    async def login(self):
        response = await self.client.post("/admin/api/v1/auth/exchange", json={"ticket": await self.ticket()})
        assert response.status_code == 200, response.text
        self.client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return response
