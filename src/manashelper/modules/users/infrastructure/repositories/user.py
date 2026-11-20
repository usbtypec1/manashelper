from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.localization.theme import Theme
from manashelper.modules.users.application.profile import ProfileFilter, UserProfile
from manashelper.modules.users.infrastructure.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def upsert(self, user_id: int, full_name: str, username: str | None) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            user = User(id=user_id, full_name=full_name, username=username)
            self._session.add(user)
        else:
            user.full_name = full_name
            user.username = username
        return user

    async def set_locale(self, user_id: int, locale: str) -> None:
        user = await self._session.get(User, user_id)
        if user is not None:
            user.locale = locale

    async def set_theme(self, user_id: int, theme: str) -> None:
        user = await self._session.get(User, user_id)
        if user is not None:
            user.theme = theme

    async def get_all_ids(self) -> list[int]:
        result = await self._session.execute(select(User.id))
        return list(result.scalars().all())

    async def get_active_ids(self) -> list[int]:
        result = await self._session.execute(select(User.id).where(User.delivery_enabled()))
        return list(result.scalars().all())

    async def blocking_status(self, user_id: int) -> bool | None:
        return (await self._session.scalars(select(User.is_blocked).where(User.id == user_id))).one_or_none()

    async def delivery_disabled(self, user_id: int) -> bool:
        enabled = await self._session.scalar(select(User.delivery_enabled()).where(User.id == user_id))
        return enabled is False

    async def set_blocked(self, user_id: int, blocked: bool) -> bool:
        target = await self._session.scalar(
            update(User).where(User.id == user_id).values(is_blocked=blocked).returning(User.id)
        )
        return target is not None

    async def list_profiles(self, *, after: int | None, limit: int, filters: ProfileFilter) -> list[UserProfile]:
        locale = func.coalesce(User.locale, DEFAULT_LOCALE.value)
        query = select(User.id, User.full_name, User.username, locale, User.theme, User.bot_stopped, User.is_blocked)
        if filters.search:
            search = filters.search
            if search.startswith("@") and len(search) > 1:
                query = query.where(User.username.icontains(search[1:], autoescape=True))
            else:
                query = query.where(
                    or_(
                        User.full_name.icontains(search, autoescape=True),
                        User.username.icontains(search, autoescape=True),
                        cast(User.id, String).contains(search, autoescape=True),
                    )
                )
        if filters.locale is not None:
            query = query.where(locale == filters.locale)
        if filters.theme is not None:
            query = query.where(User.theme == filters.theme)
        if filters.bot_stopped is not None:
            query = query.where(User.bot_stopped.is_(filters.bot_stopped))
        if filters.is_blocked is not None:
            query = query.where(User.is_blocked.is_(filters.is_blocked))
        if after is not None:
            query = query.where(User.id > after)
        result = await self._session.execute(query.order_by(User.id).limit(limit))
        return [
            UserProfile(user_id, full_name, username, Locale(language), Theme(theme), bot_stopped, is_blocked)
            for user_id, full_name, username, language, theme, bot_stopped, is_blocked in result.tuples()
        ]

    async def set_bot_stopped(self, user_id: int, stopped: bool) -> None:
        user = await self.get_by_id(user_id)
        if user is not None:
            user.bot_stopped = stopped

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(User))
        return result.scalar_one()
