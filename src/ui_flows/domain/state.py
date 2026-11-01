"""Plain application snapshots. No SQLAlchemy instances cross repository boundaries."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from ui_flows.domain.contracts import SessionStatus
from ui_flows.domain.schema import FlowDocument, LocaleCode, Node, Scalar

ACTIVE_STATUSES = ("running", "waiting_button", "waiting_input")


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
    data: dict[str, Scalar] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: DialogState
    node: Node
    outcome: Literal["started", "advanced", "invalid_input", "resumed", "cancelled", "duplicate"]
    returned_from: DialogState | None = None
