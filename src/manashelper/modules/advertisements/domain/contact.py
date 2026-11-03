import re
from dataclasses import dataclass

PHONE_NUMBER_PATTERN = re.compile(r"^\+?\d[\d\s\-()]{5,19}$")


def is_valid_phone_number(value: str) -> bool:
    return bool(PHONE_NUMBER_PATTERN.fullmatch(value))


class InvalidPhoneNumberError(ValueError):
    pass


class MissingContactError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ContactStatus:
    username: str | None
    phone_numbers: list[str]

    @property
    def has_contact(self) -> bool:
        return bool(self.username) or bool(self.phone_numbers)
