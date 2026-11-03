from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from ui_flows.domain.contracts import ActionSnapshot, DeliveryStatus
from ui_flows.domain.schema import ContractModel


class ScreenButton(ContractModel):
    id: str
    label: str
    url: str | None = None
    snapshot: ActionSnapshot | None = None


class ScreenMedia(ContractModel):
    kind: Literal["photo", "video"]
    file_id: Annotated[str, Field(min_length=1, max_length=512, repr=False)]
    # HTML entities can occupy up to six source characters per displayed character.
    # The Telegram adapter validates the rendered UTF-16 caption length separately.
    caption: Annotated[str | None, Field(max_length=6144, repr=False)] = None


class Screen(ContractModel):
    text: str = Field(repr=False)
    keyboard: Literal["reply", "inline", "none", "main"]
    buttons: list[list[ScreenButton]] = Field(default_factory=list)
    locale: str
    theme: str
    feature: str | None = None
    return_flow: str | None = None
    text_catalog_release: int | None = None
    media: Annotated[list[ScreenMedia], Field(max_length=10)] = Field(default_factory=list)
    messages: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list, repr=False)
    contact_request: str | None = None


@dataclass(frozen=True, slots=True)
class ScreenDelivery:
    token: str
    session_id: UUID
    revision: int
    update_id: int | None
    chat_id: int
    screen: Screen = field(repr=False)
    status: DeliveryStatus
    message_id: int | None
    operation_id: UUID | None = None
    message_ids: tuple[int, ...] = ()
