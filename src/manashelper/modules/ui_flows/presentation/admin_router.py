from dataclasses import asdict
from typing import Annotated, cast

from dishka import AsyncContainer
from fastapi import APIRouter, Query, Request, Response

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.ui_flows.application.admin_queries import AdminQueries
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.catalog import get_catalog_texts
from manashelper.modules.ui_flows.menus import EDERS_FEATURES, FEATURES
from manashelper.modules.ui_flows.presentation.admin_contracts import (
    ActivateVersion,
    AdminSession,
    CatalogTemplate,
    DelegateCatalog,
    DraftContent,
    EditorCatalog,
    ExchangeTicket,
    FeatureOption,
    FlowDraft,
    FlowPage,
    FlowSummary,
    FlowVersion,
    LocationPage,
    PreviewRequest,
    PreviewResult,
    PublishDraft,
    RolloutStatus,
    SaveDraft,
    SetRollout,
    TransitionPage,
    UserLocation,
    UserTransition,
    ValidationReport,
    VersionContent,
    VersionPage,
)
from manashelper.modules.ui_flows.presentation.preview import preview
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, InvalidScreenError
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.web.auth import COOKIE_NAME, AdminAuthService
from manashelper.platform.web.routing import AdminRoute
from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.flows import FlowService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.state import Draft, PublishedFlow
from ui_flows.errors import FlowConflictError, InvalidFlowError

router = APIRouter(prefix="/admin/api/v1", route_class=AdminRoute)
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=256)]


def scope(request: Request) -> AsyncContainer:
    return cast(AsyncContainer, request.state.container)


def summary(draft: Draft) -> FlowSummary:
    return FlowSummary(id=draft.document.id, draft_revision=draft.revision, published_version=draft.published_version)


def version_info(version: PublishedFlow) -> FlowVersion:
    return FlowVersion(
        flow_id=version.document.id,
        version=version.version,
        draft_revision=version.draft_revision,
        published_at=version.published_at,
        author_id=version.author_id,
    )


def check_id(flow_id: str, body: DraftContent) -> None:
    if flow_id != body.document.id:
        raise InvalidFlowError(
            [ContractIssue(code="id_mismatch", path="/document/id", message="Document ID must match the path")]
        )


@router.post("/auth/exchange", response_model=AdminSession, operation_id="exchangeTicket")
async def exchange(body: ExchangeTicket, request: Request, response: Response) -> AdminSession:
    login = await (await scope(request).get(AdminAuthService)).exchange(body.ticket)
    response.set_cookie(
        COOKIE_NAME, login.cookie, max_age=8 * 60 * 60, path="/admin", secure=True, httponly=True, samesite="strict"
    )
    return AdminSession(user_id=login.admin.user_id, expires_at=login.admin.expires_at, csrf_token=login.csrf)


@router.get("/auth/session", response_model=AdminSession, operation_id="getAdminSession")
async def current_session(request: Request) -> AdminSession:
    auth = await scope(request).get(AdminAuthService)
    return AdminSession(
        user_id=request.state.admin.user_id,
        expires_at=request.state.admin.expires_at,
        csrf_token=auth.csrf(request.cookies[COOKIE_NAME]),
    )


@router.post("/auth/logout", status_code=204, operation_id="logout")
async def logout(request: Request) -> Response:
    await (await scope(request).get(AdminAuthService)).logout(request.cookies[COOKIE_NAME])
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/admin", secure=True, httponly=True, samesite="strict")
    return response


async def rollout_status(request: Request) -> RolloutStatus:
    service = await scope(request).get(RolloutService)
    state = await service.get()
    return RolloutStatus(**asdict(state), active_dialogs=await service.active_count())


@router.get("/rollout", response_model=RolloutStatus, operation_id="getRollout")
async def get_rollout(request: Request) -> RolloutStatus:
    return await rollout_status(request)


@router.put("/rollout", response_model=RolloutStatus, operation_id="setRollout")
async def set_rollout(body: SetRollout, request: Request) -> RolloutStatus:
    await (await scope(request).get(RolloutService)).set(body.mode, body.expected_revision, request.state.admin.user_id)
    if body.mode == "all":
        flows = await scope(request).get(FlowService)
        for id in ("main_menu", "student_questions"):
            draft = await flows.get(id)
            if draft.published_version is not None:
                document = (await flows.version(id, draft.published_version)).document
                await validate_texts(request, DraftContent(document=document))
    return await rollout_status(request)


@router.get("/flows", response_model=FlowPage, operation_id="listFlows")
async def flows(request: Request, cursor: Cursor = None, limit: Limit = 50) -> FlowPage:
    rows, next_cursor = await (await scope(request).get(AdminQueries)).flows(cursor, limit)
    return FlowPage(items=[FlowSummary(**asdict(row)) for row in rows], next_cursor=next_cursor)


@router.post("/flows", response_model=FlowDraft, status_code=201, operation_id="createFlow")
async def create(body: DraftContent, request: Request) -> FlowDraft:
    draft = await (await scope(request).get(FlowService)).create(body.document)
    return FlowDraft(document=draft.document, revision=draft.revision)


@router.get("/flows/{id}", response_model=FlowSummary, operation_id="getFlow")
async def flow(id: str, request: Request) -> FlowSummary:
    return summary(await (await scope(request).get(FlowService)).get(id))


@router.get("/flows/{id}/draft", response_model=FlowDraft, operation_id="getDraft")
async def draft(id: str, request: Request) -> FlowDraft:
    value = await (await scope(request).get(FlowService)).get(id)
    return FlowDraft(document=value.document, revision=value.revision)


@router.put("/flows/{id}/draft", response_model=FlowDraft, operation_id="saveDraft")
async def save(id: str, body: SaveDraft, request: Request) -> FlowDraft:
    check_id(id, body)
    value = await (await scope(request).get(FlowService)).save(body.document, body.expected_revision)
    return FlowDraft(document=value.document, revision=value.revision)


async def validate_texts(request: Request, body: DraftContent) -> None:
    policy = await scope(request).get(FlowPolicy)
    try:
        FlowRenderer().validate_document(body.document, dict(policy.capabilities))
    except InvalidScreenError as error:
        raise InvalidFlowError(
            [
                ContractIssue(
                    code="invalid_screen",
                    path=error.path,
                    node_id=error.node_id,
                    message="Check HTML, placeholders, label ambiguity and display limits in all locales and themes",
                )
            ]
        ) from error


@router.post("/flows/{id}/validate", response_model=ValidationReport, operation_id="validateFlow")
async def validate(id: str, body: DraftContent, request: Request) -> ValidationReport:
    check_id(id, body)
    try:
        await (await scope(request).get(FlowService)).validate(body.document)
        await validate_texts(request, body)
    except InvalidFlowError as error:
        return ValidationReport(issues=error.issues)
    return ValidationReport(issues=[])


@router.post("/flows/{id}/publish", response_model=FlowVersion, operation_id="publishFlow")
async def publish(id: str, body: PublishDraft, request: Request) -> FlowVersion:
    service = await scope(request).get(FlowService)
    value = await service.get(id)
    if value.revision != body.expected_revision:
        raise FlowConflictError("Draft revision has changed")
    await validate_texts(request, DraftContent(document=value.document))
    return version_info(await service.publish(id, body.expected_revision, request.state.admin.user_id))


@router.get("/flows/{id}/versions", response_model=VersionPage, operation_id="listVersions")
async def versions(id: str, request: Request, cursor: Cursor = None, limit: Limit = 50) -> VersionPage:
    await (await scope(request).get(FlowService)).get(id)
    rows, next_cursor = await (await scope(request).get(AdminQueries)).versions(id, cursor, limit)
    return VersionPage(items=[FlowVersion(**asdict(row)) for row in rows], next_cursor=next_cursor)


@router.get("/flows/{id}/versions/{version}", response_model=VersionContent, operation_id="getVersion")
async def version_document(id: str, version: int, request: Request) -> VersionContent:
    value = await (await scope(request).get(FlowService)).version(id, version)
    return VersionContent(document=value.document, version=value.version)


@router.post("/flows/{id}/activate", response_model=FlowSummary, operation_id="activateVersion")
async def activate(id: str, body: ActivateVersion, request: Request) -> FlowSummary:
    service = await scope(request).get(FlowService)
    value = await service.version(id, body.version)
    await validate_texts(request, DraftContent(document=value.document))
    return summary(await service.activate(id, body.version, body.expected_published_version))


@router.get("/delegates", response_model=DelegateCatalog, operation_id="listDelegates")
async def delegates(request: Request) -> DelegateCatalog:
    return DelegateCatalog(items=(await scope(request).get(DelegateRegistry)).definitions())


@router.get("/catalog", response_model=EditorCatalog, operation_id="getEditorCatalog")
async def catalog(request: Request) -> EditorCatalog:
    policy = await scope(request).get(FlowPolicy)
    templates: dict[str, CatalogTemplate] = {}
    for locale in Locale:
        for theme in Theme:
            with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
                for key, text in get_catalog_texts().items():
                    item = templates.setdefault(
                        key, CatalogTemplate(key=key, translations={}, themes={"halloween": {}})
                    )
                    destination = item.translations if theme == Theme.BASIC else item.themes["halloween"]
                    destination[locale.value] = text
    return EditorCatalog(
        texts=list(templates.values()),
        capability_fields=dict(policy.capability_fields),
        capabilities=dict(policy.capabilities),
        features=[
            FeatureOption(
                id=feature, enabled=feature not in EDERS_FEATURES or bool(policy.capabilities["eders_enabled"])
            )
            for feature in sorted(FEATURES)
        ],
    )


@router.post("/flows/{id}/preview", response_model=PreviewResult, operation_id="previewFlow")
async def preview_flow(id: str, body: PreviewRequest, request: Request) -> PreviewResult:
    check_id(id, body)
    return await preview(body, await scope(request).get(DelegateRegistry), await scope(request).get(FlowPolicy))


@router.get("/users/locations", response_model=LocationPage, operation_id="listLocations")
async def locations(request: Request, cursor: Cursor = None, limit: Limit = 50) -> LocationPage:
    rows, next_cursor = await (await scope(request).get(AdminQueries)).locations(cursor, limit)
    return LocationPage(
        items=[
            UserLocation(
                user_id=row.user_id,
                chat_id=row.chat_id,
                owner=row.owner,
                flow_id=row.flow_id,
                flow_version=row.version,
                node_id=row.node_id,
                legacy_state=row.legacy_state,
                handler=row.handler,
                status=row.status,
                delivery_status=row.delivery_status,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        next_cursor=next_cursor,
    )


@router.get("/users/{user_id}/transitions", response_model=TransitionPage, operation_id="listTransitions")
async def transitions(user_id: int, request: Request, cursor: Cursor = None, limit: Limit = 50) -> TransitionPage:
    rows, next_cursor = await (await scope(request).get(AdminQueries)).transitions(user_id, cursor, limit)
    return TransitionPage(items=[UserTransition(**asdict(row)) for row in rows], next_cursor=next_cursor)


@router.get("/users/{user_id}/location", response_model=UserLocation, operation_id="getLocation")
async def user_location(user_id: int, request: Request) -> UserLocation:
    row = await (await scope(request).get(AdminQueries)).location(user_id)
    return UserLocation(
        user_id=row.user_id,
        chat_id=row.chat_id,
        owner=row.owner,
        flow_id=row.flow_id,
        flow_version=row.version,
        node_id=row.node_id,
        legacy_state=row.legacy_state,
        handler=row.handler,
        status=row.status,
        delivery_status=row.delivery_status,
        updated_at=row.updated_at,
    )
