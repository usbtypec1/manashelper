"""Plain application snapshots. No SQLAlchemy instances cross repository boundaries."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from ui_flows.domain.contracts import SessionStatus
from ui_flows.domain.schema import DataValue, FlowDocument, LocaleCode, Node

ACTIVE_STATUSES = ("running", "waiting_button", "waiting_input", "waiting_effect")


@dataclass(frozen=True, slots=True)
class RuntimeUser:
    id: int
    chat_id: int
    locale: LocaleCode = "en"
    theme: Literal["basic", "halloween"] = "basic"


@dataclass(frozen=True, slots=True)
class Draft:
    document: FlowDocument
    revision: int
    published_version: int | None


@dataclass(frozen=True, slots=True)
class PublishedFlow:
    document: FlowDocument
    version: int
    draft_revision: int
    author_id: int
    published_at: datetime
    text_catalog_release: int | None = None
    dependencies: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CallFrame:
    flow_id: str
    flow_version: int
    node_id: str
    data: dict[str, DataValue] = field(repr=False)
    resume_status: Literal["waiting_button", "waiting_input", "waiting_effect"] | None = None
    revision: int | None = None
    trigger_release: int | None = None
    effect_revision: int | None = None


@dataclass(frozen=True, slots=True)
class DialogState:
    id: UUID
    user_id: int
    chat_id: int
    flow_id: str
    flow_version: int
    node_id: str
    status: SessionStatus
    revision: int
    data: dict[str, DataValue] = field(repr=False)
    trigger_release: int | None = None
    frames: tuple[CallFrame, ...] = field(default=(), repr=False)
    effect_revision: int | None = None

    @property
    def root_flow_id(self) -> str:
        return self.frames[0].flow_id if self.frames else self.flow_id


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: DialogState
    node: Node
    outcome: Literal["started", "advanced", "invalid_input", "resumed", "cancelled", "duplicate"]
    returned_from: DialogState | None = None
    replaced_from: DialogState | None = None
    notices: tuple[DialogState, ...] = field(default=(), repr=False)
