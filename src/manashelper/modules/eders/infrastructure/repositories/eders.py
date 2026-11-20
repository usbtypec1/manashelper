from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from manashelper.modules.eders.infrastructure.models.eders import EdersNotification, EdersState
from manashelper.modules.users.infrastructure.models.user import User


class EdersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read_state(self, user_id: int) -> EdersState | None:
        # Readers must not wait for a background HTTP fetch holding the user's lock.
        return await self._session.get(EdersState, user_id)

    async def get_state(self, user_id: int) -> EdersState:
        # The user row also locks first observations, when no state row exists yet.
        await self._session.execute(select(User.id).where(User.id == user_id).with_for_update())
        state = await self._session.get(EdersState, user_id, populate_existing=True)
        if state is None:
            state = EdersState(user_id=user_id)
            self._session.add(state)
            await self._session.flush()
        return state

    async def get_notifications(self, user_id: int, *, include_payload: bool = True) -> list[EdersNotification]:
        statement = select(EdersNotification).where(EdersNotification.user_id == user_id)
        if not include_payload:
            statement = statement.options(defer(EdersNotification.payload, raiseload=True))
        result = await self._session.execute(statement)
        return list(result.scalars())

    async def get_due_notifications(self, user_id: int, now: datetime) -> list[EdersNotification]:
        result = await self._session.scalars(
            select(EdersNotification).where(
                EdersNotification.user_id == user_id,
                EdersNotification.cancelled.is_(False),
                EdersNotification.sent_at.is_(None),
                EdersNotification.due_at <= now,
            )
        )
        return list(result)

    async def cancel_day_before_notifications(self, user_id: int, activity_keys: set[str]) -> None:
        if activity_keys:
            await self._session.execute(
                update(EdersNotification)
                .where(
                    EdersNotification.user_id == user_id,
                    EdersNotification.event_type == "before_24",
                    EdersNotification.activity_key.in_(activity_keys),
                    EdersNotification.cancelled.is_(False),
                )
                .values(cancelled=True)
            )

    async def mark_sent(self, user_id: int, keys: list[str], now: datetime) -> None:
        if keys:
            await self._session.execute(
                update(EdersNotification)
                .where(EdersNotification.user_id == user_id, EdersNotification.event_key.in_(keys))
                .values(sent_at=now)
            )

    def add_notification(self, notification: EdersNotification) -> None:
        self._session.add(notification)

    async def get_poll_user_ids(self) -> list[int]:
        query = select(User.id).where(
            User.is_blocked.is_(False), User.student_number.is_not(None), User.student_number != ""
        )
        result = await self._session.execute(query)
        return list(result.scalars())
