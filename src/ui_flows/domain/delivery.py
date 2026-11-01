from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import Field

from ui_flows.domain.contracts import DeliveryStatus
from ui_flows.domain.schema import ContractModel


class ScreenButton(ContractModel):
    id: str
    label: str
    url: str | None = None


class Screen(ContractModel):
    text: str = Field(repr=False)
    keyboard: Literal["reply", "inline", "none", "main"]
    buttons: list[list[ScreenButton]] = Field(default_factory=list)
    locale: str
    theme: str
    feature: str | None = None
    return_flow: str | None = None


@dataclass(frozen=True, slots=True)
class ScreenDelivery:
    token: str
    session_id: UUID
    revision: int
    update_id: int
    chat_id: int
    screen: Screen = field(repr=False)
    status: DeliveryStatus
    message_id: int | None
