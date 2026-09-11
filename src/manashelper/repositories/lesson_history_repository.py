from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import LessonHistory


class LessonHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, entry: LessonHistory) -> None:
        self._session.add(entry)
