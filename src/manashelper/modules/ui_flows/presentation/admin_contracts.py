"""Administrative API payloads shared with the generated OpenAPI contract."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from ui_flows.domain.contracts import (
    ContractIssue,
    DelegateDefinition,
    DeliveryStatus,
    FlowEvent,
    SessionStatus,
)
from ui_flows.domain.rollout import RolloutMode
from ui_flows.domain.schema import (
    ContractModel,
    DataField,
    FlowDocument,
    Identifier,
    LocaleCode,
    Scalar,
)


class ExchangeTicket(ContractModel):
    ticket: Annotated[str, Field(min_length=32, max_length=256, repr=False)]


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


class FlowVersion(ContractModel):
    flow_id: Identifier
    version: Annotated[int, Field(ge=1)]
    draft_revision: Annotated[int, Field(ge=0)]
    published_at: datetime
    author_id: int


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


class VersionContent(DraftContent):
    version: int


class PreviewUser(ContractModel):
    id: int
    chat_id: int
    locale: LocaleCode
    theme: Literal["basic", "halloween"]


class PreviewDelegateResult(ContractModel):
    outcome: Identifier
    values: dict[Identifier, Scalar] = Field(default_factory=dict)


class PreviewRequest(DraftContent):
    node_id: Identifier | None = None
    data: dict[Identifier, Scalar] = Field(default_factory=dict)
    user: PreviewUser
    eders_enabled: bool
    event: FlowEvent | None = None
    delegate_results: dict[str, PreviewDelegateResult] = Field(default_factory=dict)


class PreviewButton(ContractModel):
    id: Identifier
    label: str
    url: str | None = None


class PreviewScreen(ContractModel):
    text: str
    keyboard: Literal["reply", "inline", "none", "main"]
    buttons: list[list[PreviewButton]]
    feature: str | None = None
    return_flow: str | None = None


class PreviewResult(ContractModel):
    node_id: Identifier
    data: dict[Identifier, Scalar]
    screen: PreviewScreen | None
    issues: list[ContractIssue]


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
