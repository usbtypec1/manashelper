"""Durable external work; payloads contain typed values or encrypted secret handles."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from ui_flows.domain.contracts import DelegateResult
from ui_flows.domain.schema import DataValue
from ui_flows.domain.state import DialogState

EffectStatus = Literal["pending", "unknown", "succeeded", "failed", "applied"]


@dataclass(frozen=True, slots=True)
class ExternalOperation:
    id: UUID
    session_id: UUID
    user_id: int
    chat_id: int
    revision: int
    flow_id: str
    flow_version: int
    node_id: str
    delegate_id: str
    contract_version: int
    arguments: dict[str, DataValue] = field(repr=False)
    status: EffectStatus = "pending"
    result: DelegateResult | None = field(default=None, repr=False)
    error_code: str | None = None
    created_at: datetime | None = None

    def matches_position(self, state: DialogState, *, suspended: bool = False) -> bool:
        if (state.id, state.user_id, state.chat_id) != (self.session_id, self.user_id, self.chat_id):
            return False
        source = (self.flow_id, self.flow_version, self.node_id, self.revision, "waiting_effect")
        if (
            state.flow_id,
            state.flow_version,
            state.node_id,
            state.effect_revision if state.effect_revision is not None else state.revision,
            state.status,
        ) == source:
            return True
        return suspended and any(
            (
                frame.flow_id,
                frame.flow_version,
                frame.node_id,
                frame.effect_revision if frame.effect_revision is not None else frame.revision,
                frame.resume_status,
            )
            == source
            for frame in state.frames
        )
