from dataclasses import dataclass

from manashelper.repositories.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.repositories.user_repository import UserRepository


class UserNotFoundError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


@dataclass(frozen=True, slots=True)
class ContactStatus:
    username: str | None
    phone_numbers: list[str]

    @property
    def has_contact(self) -> bool:
        return self.username is not None or bool(self.phone_numbers)


class UserContactService:
    def __init__(
        self, user_repository: UserRepository, user_phone_number_repository: UserPhoneNumberRepository
    ) -> None:
        self._user_repository = user_repository
        self._user_phone_number_repository = user_phone_number_repository

    async def get_contact_status(self, user_id: int) -> ContactStatus:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        phone_numbers = await self._user_phone_number_repository.get_all_by_user_id(user_id)
        return ContactStatus(username=user.username, phone_numbers=[p.phone_number for p in phone_numbers])

    async def add_phone_number(self, user_id: int, phone_number: str) -> ContactStatus:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        await self._user_phone_number_repository.add_if_missing(user_id, phone_number)
        return await self.get_contact_status(user_id)
