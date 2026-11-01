from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ui_flows.domain.contracts import DeliveryStatus, SessionStatus


@dataclass(frozen=True, slots=True)
class FlowInfo:
    id: str
    draft_revision: int
    published_version: int | None


@dataclass(frozen=True, slots=True)
class VersionInfo:
    flow_id: str
    version: int
    draft_revision: int
    published_at: datetime
    author_id: int


@dataclass(frozen=True, slots=True)
class LocationInfo:
    user_id: int
    chat_id: int
    flow_id: str | None
    version: int | None
    node_id: str | None
    status: SessionStatus | None
    delivery_status: DeliveryStatus | None
    updated_at: datetime | None
    owner: Literal["runtime", "legacy", "unknown"] = "unknown"
    legacy_state: str | None = None
    handler: str | None = None


@dataclass(frozen=True, slots=True)
class TransitionInfo:
    id: int
    flow_id: str | None
    from_step: str | None
    to_step: str | None
    outcome: str
    occurred_at: datetime
    owner: Literal["runtime", "legacy", "unknown"] = "unknown"
    flow_version: int | None = None
