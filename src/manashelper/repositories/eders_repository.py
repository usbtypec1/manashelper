from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models.eders import EdersNotification, EdersState
from manashelper.db.models.user import User


class EdersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_state(self, user_id: int) -> EdersState:
        # The user row also locks first observations, when no state row exists yet.
        await self._session.execute(select(User.id).where(User.id == user_id).with_for_update())
        state = await self._session.get(EdersState, user_id, populate_existing=True)
        if state is None:
            state = EdersState(user_id=user_id)
            self._session.add(state)
            await self._session.flush()
        return state

    async def get_notifications(self, user_id: int) -> list[EdersNotification]:
        result = await self._session.execute(select(EdersNotification).where(EdersNotification.user_id == user_id))
        return list(result.scalars())

    def add_notification(self, notification: EdersNotification) -> None:
        self._session.add(notification)

    async def get_poll_user_ids(self) -> list[int]:
        result = await self._session.execute(
            select(User.id).where(User.student_number.is_not(None), User.encrypted_password.is_not(None))
        )
        return list(result.scalars())
