"""Data exchanged with a future interpreter and registered Python delegates."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import Field

from ui_flows.domain.schema import (
    ContractModel,
    DataField,
    DelegateId,
    Identifier,
    Scalar,
)

SessionStatus = Literal["running", "waiting_button", "waiting_input", "completed", "cancelled", "handed_off", "failed"]
DeliveryStatus = Literal["pending", "sent", "failed", "unknown"]


class DelegateParameter(DataField):
    required: bool = True


class DelegateDefinition(ContractModel):
    id: DelegateId
    version: Annotated[int, Field(ge=1)] = 1
    effect: Literal["read", "database_write"]
    inputs: dict[Identifier, DelegateParameter] = Field(default_factory=dict)
    outputs: dict[Identifier, DataField] = Field(default_factory=dict)
    outcomes: Annotated[list[Identifier], Field(min_length=1)]


@dataclass(frozen=True, slots=True)
class DelegateContext:
    user_id: int
    chat_id: int
    session_id: str
    event_id: str


@dataclass(frozen=True, slots=True)
class DelegateResult:
    outcome: str
    values: Mapping[str, Scalar]


class Delegate(Protocol):
    async def __call__(self, context: DelegateContext, arguments: Mapping[str, Scalar]) -> DelegateResult: ...


class EventIdentity(ContractModel):
    update_id: Annotated[int, Field(ge=0)]
    user_id: int
    chat_id: int
    session_id: Annotated[str, Field(min_length=1, max_length=64)]
    expected_revision: Annotated[int, Field(ge=0)]


class ButtonEvent(EventIdentity):
    kind: Literal["button"]
    button_id: Identifier


class InputEvent(EventIdentity):
    kind: Literal["input"]
    text: Annotated[str, Field(max_length=4096, repr=False)]


class NavigationEvent(EventIdentity):
    kind: Literal["navigation"]
    action: Literal["main_menu", "cancel", "resume"]


FlowEvent = Annotated[ButtonEvent | InputEvent | NavigationEvent, Field(discriminator="kind")]


class ContractIssue(ContractModel):
    code: str
    path: str
    message: str
    node_id: str | None = None
    button_id: str | None = None
