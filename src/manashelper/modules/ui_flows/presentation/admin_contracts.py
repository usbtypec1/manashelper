"""Administrative API payloads shared with the generated OpenAPI contract."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from ui_flows.domain.contracts import (
    ActionSnapshot,
    ContractIssue,
    DelegateDefinition,
    DeliveryStatus,
    FlowEvent,
    SessionStatus,
)
from ui_flows.domain.delivery import ScreenMedia
from ui_flows.domain.ingress import TriggerDocument, TriggerManifest
from ui_flows.domain.rollout import RolloutMode
from ui_flows.domain.schema import (
    ContractModel,
    DataField,
    DataValue,
    FlowDocument,
    Identifier,
    LocaleCode,
    Scalar,
)
from ui_flows.domain.texts import TextDocument, TextEntry


class ExchangeTicket(ContractModel):
    ticket: Annotated[str, Field(min_length=32, max_length=256, repr=False)]


class ExchangeTelegram(ContractModel):
    init_data: Annotated[str, Field(min_length=1, max_length=16384, repr=False)]


class MiniAppSession(ContractModel):
    user_id: int
    expires_at: datetime
    access_token: Annotated[str, Field(repr=False)]


class AdminSession(ContractModel):
    user_id: int
    expires_at: datetime
    csrf_token: Annotated[str, Field(repr=False)]


class ApiError(ContractModel):
    code: str
    message: str
    issues: list[ContractIssue] = Field(default_factory=list)


class RolloutStatus(ContractModel):
    mode: RolloutMode
    revision: Annotated[int, Field(ge=0)]
    active_dialogs: Annotated[int, Field(ge=0)]
    updated_at: datetime | None
    updated_by: int | None


class SetRollout(ContractModel):
    mode: RolloutMode
    expected_revision: Annotated[int, Field(ge=0)]


class FlowSummary(ContractModel):
    id: Identifier
    draft_revision: Annotated[int, Field(ge=0)]
    published_version: Annotated[int, Field(ge=1)] | None


class FlowPage(ContractModel):
    items: list[FlowSummary]
    next_cursor: str | None


class DraftContent(ContractModel):
    document: FlowDocument


class SaveDraft(DraftContent):
    expected_revision: Annotated[int, Field(ge=0)]


class FlowDraft(DraftContent):
    revision: Annotated[int, Field(ge=0)]


class ValidationReport(ContractModel):
    issues: list[ContractIssue]


class PublishDraft(ContractModel):
    expected_revision: Annotated[int, Field(ge=0)]


class TextCatalogDraft(ContractModel):
    document: TextDocument
    revision: Annotated[int, Field(ge=0)]
    current_release: Annotated[int, Field(ge=1)]


class SaveTextEntry(ContractModel):
    entry: TextEntry
    expected_revision: Annotated[int, Field(ge=0)]


class TextCatalogRelease(ContractModel):
    id: Annotated[int, Field(ge=1)]
    draft_revision: Annotated[int, Field(ge=0)]
    author_id: int | None = None
    published_at: datetime


class TextCatalogVersions(ContractModel):
    items: list[TextCatalogRelease]


class ActivateTextCatalog(ContractModel):
    release_id: Annotated[int, Field(ge=1)]
    expected_current_release: Annotated[int, Field(ge=1)]


class TriggerDraftContent(ContractModel):
    document: TriggerDocument
    revision: Annotated[int, Field(ge=0)]
    current_release: int | None


class SaveTriggers(ContractModel):
    document: TriggerDocument
    expected_revision: Annotated[int, Field(ge=0)]


class TriggerReleaseContent(ContractModel):
    id: Annotated[int, Field(ge=1)]
    draft_revision: Annotated[int, Field(ge=0)]
    author_id: int
    published_at: datetime
    manifest: TriggerManifest


class TriggerVersions(ContractModel):
    items: list[TriggerReleaseContent]


class FlowVersion(ContractModel):
    flow_id: Identifier
    version: Annotated[int, Field(ge=1)]
    draft_revision: Annotated[int, Field(ge=0)]
    published_at: datetime
    author_id: int
    text_catalog_release: Annotated[int, Field(ge=1)] | None = None
    dependencies: dict[Identifier, Annotated[int, Field(ge=1)]] = Field(default_factory=dict)


class VersionPage(ContractModel):
    items: list[FlowVersion]
    next_cursor: str | None


class ActivateVersion(ContractModel):
    version: Annotated[int, Field(ge=1)]
    expected_published_version: Annotated[int, Field(ge=1)] | None


class DelegateCatalog(ContractModel):
    items: list[DelegateDefinition]


class CatalogTemplate(ContractModel):
    key: str
    translations: dict[LocaleCode, str]
    themes: dict[Literal["halloween"], dict[LocaleCode, str]]


class FeatureOption(ContractModel):
    id: Identifier
    enabled: bool


class EditorCatalog(ContractModel):
    texts: list[CatalogTemplate]
    capability_fields: dict[str, DataField]
    capabilities: dict[str, Scalar]
    features: list[FeatureOption] = Field(default_factory=list)
    text_catalog_release: Annotated[int, Field(ge=1)] | None = None


class VersionContent(DraftContent):
    version: int
    text_catalog_release: Annotated[int, Field(ge=1)] | None = None
    dependencies: dict[Identifier, Annotated[int, Field(ge=1)]] = Field(default_factory=dict)


class PreviewUser(ContractModel):
    id: int
    chat_id: int
    locale: LocaleCode
    theme: Literal["basic", "halloween"]


class PreviewDelegateResult(ContractModel):
    outcome: Identifier
    values: dict[Identifier, DataValue] = Field(default_factory=dict)


class PreviewFrame(ContractModel):
    flow_id: Identifier
    flow_version: Annotated[int, Field(ge=0)]
    node_id: Identifier
    data: dict[Identifier, DataValue] = Field(default_factory=dict)
    resume_status: Literal["waiting_button", "waiting_input", "waiting_effect"] | None = None
    revision: Annotated[int, Field(ge=0)] | None = None
    trigger_release: Annotated[int, Field(ge=1)] | None = None
    effect_revision: Annotated[int, Field(ge=0)] | None = None


class PreviewPosition(PreviewFrame):
    frames: Annotated[list[PreviewFrame], Field(max_length=15)] = Field(default_factory=list)
    dependencies: dict[Identifier, Annotated[int, Field(ge=1)]] = Field(default_factory=dict)


class PreviewRequest(DraftContent):
    node_id: Identifier | None = None
    data: dict[Identifier, DataValue] = Field(default_factory=dict)
    user: PreviewUser
    eders_enabled: bool
    event: FlowEvent | None = None
    delegate_results: dict[str, PreviewDelegateResult] = Field(default_factory=dict)
    text_catalog_release: Annotated[int, Field(ge=1)] | None = None
    position: PreviewPosition | None = None


class PreviewButton(ContractModel):
    id: Identifier
    label: str
    url: str | None = None
    snapshot: ActionSnapshot | None = None


class PreviewScreen(ContractModel):
    text: str
    keyboard: Literal["reply", "inline", "none", "main"]
    buttons: list[list[PreviewButton]]
    feature: str | None = None
    return_flow: str | None = None
    messages: list[str] = Field(default_factory=list)
    media: list[ScreenMedia] = Field(default_factory=list)
    contact_request: str | None = None
    input_type: Literal["text", "integer", "choice", "contact", "media", "secret"] | None = None


class PreviewResult(ContractModel):
    node_id: Identifier
    data: dict[Identifier, DataValue]
    screen: PreviewScreen | None
    issues: list[ContractIssue]
    position: PreviewPosition | None = None
    node_kind: Literal["menu", "input", "end", "return"] | None = None


class UserLocation(ContractModel):
    user_id: int
    chat_id: int
    owner: Literal["runtime", "legacy", "unknown"]
    flow_id: Identifier | None
    flow_version: int | None
    node_id: Identifier | None
    legacy_state: str | None
    status: SessionStatus | None
    delivery_status: DeliveryStatus | None
    updated_at: datetime | None
    handler: str | None = None


class LocationPage(ContractModel):
    items: list[UserLocation]
    next_cursor: str | None


class UserTransition(ContractModel):
    id: int
    flow_id: Identifier | None
    from_step: str | None
    to_step: str | None
    outcome: str
    occurred_at: datetime
    owner: Literal["runtime", "legacy", "unknown"] = "unknown"
    flow_version: int | None = None


class TransitionPage(ContractModel):
    items: list[UserTransition]
    next_cursor: str | None
