"""Transport-independent input and publication contracts. Input payloads are never receipts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from ui_flows.domain.schema import ContractModel, Identifier
from ui_flows.domain.state import DialogState

BindingId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


@dataclass(frozen=True, slots=True)
class IncomingEvent:
    bot_id: int
    update_id: int
    actor_id: int
    chat_id: int
    chat_type: str
    kind: Literal["command", "deep_link", "callback", "text", "contact", "media", "reply", "unsupported"]
    message_id: int | None = None
    thread_id: int | None = None
    key: str = ""
    arguments: str = field(default="", repr=False)
    text: str = field(default="", repr=False)
    callback: str = field(default="", repr=False)
    codec: str | None = None
    action: str | None = None
    valid: bool = True
    contact_owner: int | None = None
    phone: str | None = field(default=None, repr=False)
    media_type: str | None = None
    file_ids: tuple[str, ...] = field(default=(), repr=False)
    caption: str | None = field(default=None, repr=False)
    media_group_id: str | None = None
    reply_to_message_id: int | None = None


class TriggerMatcher(ContractModel):
    kind: Literal["command", "deep_link", "prefix", "callback", "reply_label", "native_reply"]
    key: Annotated[str, Field(min_length=1, max_length=120)]
    arguments: Literal["none", "text", "uuid", "flow_id"] = "none"
    action: Annotated[str, Field(max_length=64)] | None = None


class ScenarioTarget(ContractModel):
    kind: Literal["scenario"] = "scenario"
    flow_id: Identifier
    entry: Identifier | None = None
    navigation: Literal["study"] | None = None
    arguments: dict[Identifier, Literal["argument", "actor_id", "chat_id"]] = Field(default_factory=dict)


class LegacyTarget(ContractModel):
    kind: Literal["legacy"] = "legacy"
    adapter: Identifier


class TriggerBinding(ContractModel):
    id: BindingId
    matcher: TriggerMatcher
    target: Annotated[ScenarioTarget | LegacyTarget, Field(discriminator="kind")]
    scope: Literal["private", "group", "any"] = "private"
    access: Literal["public", "admin", "moderation"] = "public"
    capabilities: list[Identifier] = Field(default_factory=list)
    policy: Literal["reject_if_busy", "resume", "replace", "preserve", "call"] = "reject_if_busy"
    fallback_adapter: Identifier | None = None


class TriggerDocument(ContractModel):
    schema_version: Literal[1] = 1
    bindings: Annotated[list[TriggerBinding], Field(max_length=256)]


class ScenarioPin(ContractModel):
    flow_id: Identifier
    version: Annotated[int, Field(ge=1)]
    text_catalog_release: Annotated[int, Field(ge=1)]


class TriggerManifest(ContractModel):
    document: TriggerDocument
    scenarios: list[ScenarioPin]
    text_catalog_release: Annotated[int, Field(ge=1)] = 1


@dataclass(frozen=True, slots=True)
class TriggerDraft:
    document: TriggerDocument
    revision: int
    current_release: int | None


@dataclass(frozen=True, slots=True)
class TriggerRelease:
    id: int
    draft_revision: int
    author_id: int
    published_at: datetime
    manifest: TriggerManifest


class ExpectedPosition(ContractModel):
    session_id: Annotated[str, Field(max_length=64)] | None = None
    revision: Annotated[int, Field(ge=0)] | None = None

    def matches(self, state: DialogState | None) -> bool:
        if state is None:
            return self.session_id is None and self.revision is None
        return self.session_id == str(state.id) and self.revision == state.revision


class RouteDecision(ContractModel):
    kind: Literal["legacy", "launch", "runtime_text", "runtime_callback", "reject", "ignore"]
    release_id: int
    binding_id: BindingId | None = None
    adapter: Identifier | None = None
    flow_id: Identifier | None = None
    flow_version: int | None = None
    entry: Identifier | None = None
    navigation: Literal["study"] | None = None
    policy: Literal["reject_if_busy", "resume", "replace", "preserve", "call"] = "reject_if_busy"
    position: ExpectedPosition | None = None


@dataclass(frozen=True, slots=True)
class IngressContext:
    admin_id: int
    moderation_chat_id: int
    runtime_flow: str | None = None
    legacy_owner: str | None = None
    saved_reply: bool = False
    rollout: bool = False
    capabilities: frozenset[str] = frozenset()
    labels: dict[str, frozenset[str]] = field(default_factory=dict)
    runtime_busy: bool = True
    runtime_input: Literal["text", "integer", "choice", "contact", "media", "secret"] | None = None
