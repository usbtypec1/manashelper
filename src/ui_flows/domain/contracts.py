"""Data exchanged with a future interpreter and registered Python delegates."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, Literal, Protocol

from pydantic import Field

from ui_flows.domain.schema import (
    ContractModel,
    DataField,
    DataValue,
    DelegateId,
    Identifier,
)

SessionStatus = Literal[
    "running", "waiting_button", "waiting_input", "waiting_effect", "completed", "cancelled", "handed_off", "failed"
]
DeliveryStatus = Literal["pending", "sent", "failed", "unknown"]


class DelegateParameter(DataField):
    required: bool = True


class DelegateDefinition(ContractModel):
    id: DelegateId
    version: Annotated[int, Field(ge=1)] = 1
    effect: Literal["read", "database_write", "external"]
    inputs: dict[Identifier, DelegateParameter] = Field(default_factory=dict)
    outputs: dict[Identifier, DataField] = Field(default_factory=dict)
    outcomes: Annotated[list[Identifier], Field(min_length=1)]


@dataclass(frozen=True, slots=True)
class DelegateContext:
    user_id: int
    chat_id: int
    session_id: str
    event_id: str
    secrets: Mapping[str, str] = field(default_factory=dict, repr=False)
    locale: str = "en"
    theme: Literal["basic", "halloween"] = "basic"


@dataclass(frozen=True, slots=True)
class DelegateResult:
    outcome: str
    values: Mapping[str, DataValue]


class Delegate(Protocol):
    async def __call__(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult: ...


class EventIdentity(ContractModel):
    update_id: Annotated[int, Field(ge=0)]
    user_id: int
    chat_id: int
    session_id: Annotated[str, Field(min_length=1, max_length=64)]
    expected_revision: Annotated[int, Field(ge=0)]


class ActionSnapshot(ContractModel):
    template_id: Identifier
    target: Identifier
    assignments: dict[Identifier, DataValue] = Field(default_factory=dict)
    item: dict[Identifier, DataValue] = Field(default_factory=dict)


class ButtonEvent(EventIdentity):
    kind: Literal["button"]
    button_id: Identifier
    snapshot: ActionSnapshot | None = None


class InputEvent(EventIdentity):
    kind: Literal["input"]
    text: Annotated[str, Field(max_length=4096, repr=False)]


class ContactEvent(EventIdentity):
    kind: Literal["contact"]
    owner_id: int | None
    phone: Annotated[str, Field(min_length=1, max_length=128, repr=False)]


class MediaEvent(EventIdentity):
    kind: Literal["media"]
    message_id: int
    media_type: Literal["photo", "video"]
    file_id: Annotated[str, Field(min_length=1, max_length=512, repr=False)]
    media_group_id: str | None = None
    caption: Annotated[str | None, Field(max_length=1024, repr=False)] = None


class SecretEvent(EventIdentity):
    kind: Literal["secret"]
    handle: Annotated[str, Field(min_length=36, max_length=36, repr=False)]


class NavigationEvent(EventIdentity):
    kind: Literal["navigation"]
    action: Literal["main_menu", "cancel", "resume"]


FlowEvent = Annotated[
    ButtonEvent | InputEvent | ContactEvent | MediaEvent | SecretEvent | NavigationEvent, Field(discriminator="kind")
]


class ContractIssue(ContractModel):
    code: str
    path: str
    message: str
    node_id: str | None = None
    button_id: str | None = None
