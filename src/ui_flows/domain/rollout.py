from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RolloutMode = Literal["admin", "all", "off"]


@dataclass(frozen=True, slots=True)
class RolloutState:
    mode: RolloutMode = "admin"
    revision: int = 0
    updated_at: datetime | None = None
    updated_by: int | None = None
