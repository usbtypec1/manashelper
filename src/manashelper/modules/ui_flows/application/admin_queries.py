from manashelper.modules.ui_flows.infrastructure.admin_queries import AdminQueriesRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.web.cursors import CursorCodec, InvalidCursorError
from ui_flows.domain.admin import FlowInfo, LocationInfo, TransitionInfo, VersionInfo
from ui_flows.errors import FlowNotFoundError


class AdminQueries:
    def __init__(self, repository: AdminQueriesRepository, cursors: CursorCodec, users: UsersQuery) -> None:
        self._repository = repository
        self._cursors = cursors
        self._users = users

    def _anchor(self, cursor: str | None, scope: str, *, string: bool = False) -> str | int | None:
        value = self._cursors.decode(cursor, scope)
        if value is not None and type(value) is not (str if string else int):
            raise InvalidCursorError("Cursor anchor type is invalid")
        return value

    async def flows(self, cursor: str | None, limit: int) -> tuple[list[FlowInfo], str | None]:
        anchor = self._anchor(cursor, "flows", string=True)
        rows = await self._repository.flows(anchor if isinstance(anchor, str) else None, limit + 1)
        return rows[:limit], self._cursors.encode("flows", rows[limit - 1].id) if len(rows) > limit else None

    async def versions(self, flow_id: str, cursor: str | None, limit: int) -> tuple[list[VersionInfo], str | None]:
        scope = "versions:" + flow_id
        anchor = self._anchor(cursor, scope)
        rows = await self._repository.versions(flow_id, anchor if isinstance(anchor, int) else None, limit + 1)
        return rows[:limit], self._cursors.encode(scope, rows[limit - 1].version) if len(rows) > limit else None

    async def locations(self, cursor: str | None, limit: int) -> tuple[list[LocationInfo], str | None]:
        scope = "locations:v2"
        anchor = self._anchor(cursor, scope)
        user_ids = await self._users.ids_after(anchor if isinstance(anchor, int) else None, limit + 1)
        observed = {row.user_id: row for row in await self._repository.locations(user_ids)}
        rows = [
            observed.get(user_id) or LocationInfo(user_id, user_id, None, None, None, None, None, None)
            for user_id in user_ids
        ]
        return rows[:limit], self._cursors.encode(scope, rows[limit - 1].user_id) if len(rows) > limit else None

    async def transitions(
        self, user_id: int, cursor: str | None, limit: int
    ) -> tuple[list[TransitionInfo], str | None]:
        scope = "transitions:v2:" + str(user_id)
        anchor = self._anchor(cursor, scope)
        rows = await self._repository.transitions(user_id, anchor if isinstance(anchor, int) else None, limit + 1)
        return rows[:limit], self._cursors.encode(scope, rows[limit - 1].id) if len(rows) > limit else None

    async def location(self, user_id: int) -> LocationInfo:
        if not await self._users.exists(user_id):
            raise FlowNotFoundError("User does not exist")
        rows = await self._repository.locations([user_id])
        return rows[0] if rows else LocationInfo(user_id, user_id, None, None, None, None, None, None)
