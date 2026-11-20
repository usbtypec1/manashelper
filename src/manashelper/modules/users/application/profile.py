from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserProfile:
    id: int
    full_name: str
    username: str | None
