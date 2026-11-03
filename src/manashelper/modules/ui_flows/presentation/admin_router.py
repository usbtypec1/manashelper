from dataclasses import asdict

from aiohttp import web
from dishka import AsyncContainer

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.ui_flows.application.admin_queries import AdminQueries
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.catalog import get_catalog_texts
from manashelper.modules.ui_flows.menus import EDERS_FEATURES, FEATURES
from manashelper.modules.ui_flows.presentation.admin_contracts import (
    ActivateTextCatalog,
    ActivateVersion,
    AdminSession,
    CatalogTemplate,
    DelegateCatalog,
    DraftContent,
    EditorCatalog,
    ExchangeTelegram,
    ExchangeTicket,
    FeatureOption,
    FlowDraft,
    FlowPage,
    FlowSummary,
    FlowVersion,
    LocationPage,
    MiniAppSession,
    PreviewRequest,
    PublishDraft,
    RolloutStatus,
    SaveDraft,
    SaveTextEntry,
    SetRollout,
    TextCatalogDraft,
    TextCatalogRelease,
    TextCatalogVersions,
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
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.web.auth import COOKIE_NAME, AdminAuthService
from manashelper.platform.web.auth_repository import AuthenticatedAdmin
from manashelper.platform.web.keys import ADMIN_KEY, AUTH_TOKEN_KEY, BEARER_KEY, REQUEST_CONTAINER_KEY
from manashelper.platform.web.routing import body as parse_body
from manashelper.platform.web.routing import pagination, path_integer
from manashelper.platform.web.routing import response as respond
from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.flows import FlowService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.state import Draft, PublishedFlow
from ui_flows.errors import FlowConflictError, InvalidFlowError

router = web.RouteTableDef()


@router.get("/admin/api/v1/triggers", name="admin.getTriggers")
async def get_triggers(request: web.Request) -> web.Response:
    from manashelper.modules.ui_flows.presentation.admin_contracts import TriggerDraftContent

    return respond(TriggerDraftContent(**asdict(await (await scope(request).get(TriggerService)).draft())))


@router.put("/admin/api/v1/triggers", name="admin.saveTriggers")
async def save_triggers(request: web.Request) -> web.Response:
    from manashelper.modules.ui_flows.presentation.admin_contracts import SaveTriggers, TriggerDraftContent

    body = await parse_body(request, SaveTriggers)
    draft = await (await scope(request).get(TriggerService)).save(body.document, body.expected_revision)
    return respond(TriggerDraftContent(**asdict(draft)))


@router.post("/admin/api/v1/triggers/publish", name="admin.publishTriggers")
async def publish_triggers(request: web.Request) -> web.Response:
    from manashelper.modules.ui_flows.presentation.admin_contracts import TriggerReleaseContent

    body = await parse_body(request, PublishDraft)
    release = await (await scope(request).get(TriggerService)).publish(body.expected_revision, admin(request).user_id)
    return respond(TriggerReleaseContent(**asdict(release)))


@router.get("/admin/api/v1/triggers/releases", name="admin.listTriggerReleases")
async def trigger_releases(request: web.Request) -> web.Response:
    from manashelper.modules.ui_flows.presentation.admin_contracts import TriggerReleaseContent, TriggerVersions

    versions = await (await scope(request).get(TriggerService)).versions()
    return respond(TriggerVersions(items=[TriggerReleaseContent(**asdict(item)) for item in versions]))


@router.post("/admin/api/v1/triggers/activate", name="admin.activateTriggers")
async def activate_triggers(request: web.Request) -> web.Response:
    from manashelper.modules.ui_flows.presentation.admin_contracts import TriggerDraftContent

    body = await parse_body(request, ActivateTextCatalog)
    draft = await (await scope(request).get(TriggerService)).activate(body.release_id, body.expected_current_release)
    return respond(TriggerDraftContent(**asdict(draft)))


def admin(request: web.Request) -> AuthenticatedAdmin:
    return request[ADMIN_KEY]


def scope(request: web.Request) -> AsyncContainer:
    return request[REQUEST_CONTAINER_KEY]


def summary(draft: Draft) -> FlowSummary:
    return FlowSummary(id=draft.document.id, draft_revision=draft.revision, published_version=draft.published_version)


def version_info(version: PublishedFlow) -> FlowVersion:
    return FlowVersion(
        flow_id=version.document.id,
        version=version.version,
        draft_revision=version.draft_revision,
        published_at=version.published_at,
        author_id=version.author_id,
        text_catalog_release=version.text_catalog_release,
        dependencies=version.dependencies,
    )


def check_id(flow_id: str, body: DraftContent) -> None:
    if flow_id != body.document.id:
        raise InvalidFlowError(
            [ContractIssue(code="id_mismatch", path="/document/id", message="Document ID must match the path")]
        )


@router.post("/admin/api/v1/auth/exchange", name="admin.exchangeTicket")
async def exchange(request: web.Request) -> web.Response:
    body = await parse_body(request, ExchangeTicket)
    login = await (await scope(request).get(AdminAuthService)).exchange(body.ticket)
    result = respond(
        AdminSession(user_id=login.admin.user_id, expires_at=login.admin.expires_at, csrf_token=login.csrf)
    )
    result.set_cookie(
        COOKIE_NAME, login.cookie, max_age=8 * 60 * 60, path="/admin", secure=True, httponly=True, samesite="strict"
    )
    return result


@router.get("/admin/api/v1/auth/session", name="admin.getAdminSession")
async def current_session(request: web.Request) -> web.Response:
    auth = await scope(request).get(AdminAuthService)
    csrf = "" if request[BEARER_KEY] else auth.csrf(request[AUTH_TOKEN_KEY])
    return respond(AdminSession(user_id=admin(request).user_id, expires_at=admin(request).expires_at, csrf_token=csrf))


@router.post("/admin/api/v1/auth/logout", name="admin.logout")
async def logout(request: web.Request) -> web.Response:
    await (await scope(request).get(AdminAuthService)).logout(request[AUTH_TOKEN_KEY], bearer=request[BEARER_KEY])
    result = web.Response(status=204)
    if not request[BEARER_KEY]:
        result.del_cookie(COOKIE_NAME, path="/admin", secure=True, httponly=True, samesite="strict")
    return result


async def rollout_status(request: web.Request) -> RolloutStatus:
    service = await scope(request).get(RolloutService)
    state = await service.get()
    return RolloutStatus(**asdict(state), active_dialogs=await service.active_count())


@router.get("/admin/api/v1/rollout", name="admin.getRollout")
async def get_rollout(request: web.Request) -> web.Response:
    return respond(await rollout_status(request), 200)


@router.put("/admin/api/v1/rollout", name="admin.setRollout")
async def set_rollout(request: web.Request) -> web.Response:
    body = await parse_body(request, SetRollout)
    await (await scope(request).get(RolloutService)).set(body.mode, body.expected_revision, admin(request).user_id)
    if body.mode == "all":
        flows = await scope(request).get(FlowService)
        for id in ("main_menu", "student_questions"):
            draft = await flows.get(id)
            if draft.published_version is not None:
                document = (await flows.version(id, draft.published_version)).document
                await validate_texts(request, DraftContent(document=document))
    return respond(await rollout_status(request), 200)


@router.get("/admin/api/v1/flows", name="admin.listFlows")
async def flows(request: web.Request) -> web.Response:
    page = pagination(request)
    cursor, limit = (page.cursor, page.limit)
    rows, next_cursor = await (await scope(request).get(AdminQueries)).flows(cursor, limit)
    return respond(FlowPage(items=[FlowSummary(**asdict(row)) for row in rows], next_cursor=next_cursor), 200)


@router.post("/admin/api/v1/flows", name="admin.createFlow")
async def create(request: web.Request) -> web.Response:
    body = await parse_body(request, DraftContent)
    draft = await (await scope(request).get(FlowService)).create(body.document)
    return respond(FlowDraft(document=draft.document, revision=draft.revision), 201)


@router.get("/admin/api/v1/flows/{id}", name="admin.getFlow")
async def flow(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    return respond(summary(await (await scope(request).get(FlowService)).get(id)), 200)


@router.get("/admin/api/v1/flows/{id}/draft", name="admin.getDraft")
async def draft(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    value = await (await scope(request).get(FlowService)).get(id)
    return respond(FlowDraft(document=value.document, revision=value.revision), 200)


@router.put("/admin/api/v1/flows/{id}/draft", name="admin.saveDraft")
async def save(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    body = await parse_body(request, SaveDraft)
    check_id(id, body)
    value = await (await scope(request).get(FlowService)).save(body.document, body.expected_revision)
    return respond(FlowDraft(document=value.document, revision=value.revision), 200)


async def validate_texts(request: web.Request, body: DraftContent) -> None:
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


@router.post("/admin/api/v1/flows/{id}/validate", name="admin.validateFlow")
async def validate(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    body = await parse_body(request, DraftContent)
    check_id(id, body)
    try:
        await (await scope(request).get(FlowService)).validate(body.document)
        await validate_texts(request, body)
    except InvalidFlowError as error:
        return respond(ValidationReport(issues=error.issues), 200)
    return respond(ValidationReport(issues=[]), 200)


@router.post("/admin/api/v1/flows/{id}/publish", name="admin.publishFlow")
async def publish(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    body = await parse_body(request, PublishDraft)
    service = await scope(request).get(FlowService)
    value = await service.get(id)
    if value.revision != body.expected_revision:
        raise FlowConflictError("Draft revision has changed")
    await validate_texts(request, DraftContent(document=value.document))
    return respond(version_info(await service.publish(id, body.expected_revision, admin(request).user_id)), 200)


@router.get("/admin/api/v1/flows/{id}/versions", name="admin.listVersions")
async def versions(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    page = pagination(request)
    cursor, limit = (page.cursor, page.limit)
    await (await scope(request).get(FlowService)).get(id)
    rows, next_cursor = await (await scope(request).get(AdminQueries)).versions(id, cursor, limit)
    return respond(VersionPage(items=[FlowVersion(**asdict(row)) for row in rows], next_cursor=next_cursor), 200)


@router.get("/admin/api/v1/flows/{id}/versions/{version}", name="admin.getVersion")
async def version_document(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    version = path_integer(request, "version")
    value = await (await scope(request).get(FlowService)).version(id, version)
    return respond(
        VersionContent(
            document=value.document,
            version=value.version,
            text_catalog_release=value.text_catalog_release,
            dependencies=value.dependencies,
        ),
        200,
    )


@router.post("/admin/api/v1/flows/{id}/activate", name="admin.activateVersion")
async def activate(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    body = await parse_body(request, ActivateVersion)
    service = await scope(request).get(FlowService)
    value = await service.version(id, body.version)
    with i18n.use_catalog(
        await (await scope(request).get(TextCatalogService)).version(value.text_catalog_release or 1)
    ):
        await validate_texts(request, DraftContent(document=value.document))
    return respond(summary(await service.activate(id, body.version, body.expected_published_version)), 200)


@router.get("/admin/api/v1/delegates", name="admin.listDelegates")
async def delegates(request: web.Request) -> web.Response:
    return respond(DelegateCatalog(items=(await scope(request).get(DelegateRegistry)).definitions()), 200)


async def catalog_content(request: web.Request) -> web.Response:
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
    return respond(
        EditorCatalog(
            text_catalog_release=i18n.current_catalog.release_id,
            texts=list(templates.values()),
            capability_fields=dict(policy.capability_fields),
            capabilities=dict(policy.capabilities),
            features=[
                FeatureOption(
                    id=feature, enabled=feature not in EDERS_FEATURES or bool(policy.capabilities["eders_enabled"])
                )
                for feature in sorted(FEATURES)
            ],
        ),
        200,
    )


@router.post("/admin/api/v1/flows/{id}/preview", name="admin.previewFlow")
async def preview_flow(request: web.Request) -> web.Response:
    id = request.match_info["id"]
    body = await parse_body(request, PreviewRequest)
    check_id(id, body)
    texts = await scope(request).get(TextCatalogService)
    snapshot = (
        await texts.current() if body.text_catalog_release is None else await texts.version(body.text_catalog_release)
    )
    with i18n.use_catalog(snapshot):
        return respond(
            await preview(
                body,
                await scope(request).get(DelegateRegistry),
                await scope(request).get(FlowPolicy),
                flows=await scope(request).get(FlowService),
                texts=texts,
            ),
            200,
        )


@router.get("/admin/api/v1/users/locations", name="admin.listLocations")
async def locations(request: web.Request) -> web.Response:
    page = pagination(request)
    cursor, limit = (page.cursor, page.limit)
    rows, next_cursor = await (await scope(request).get(AdminQueries)).locations(cursor, limit)
    return respond(
        LocationPage(
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
        ),
        200,
    )


@router.get("/admin/api/v1/users/{user_id}/transitions", name="admin.listTransitions")
async def transitions(request: web.Request) -> web.Response:
    user_id = path_integer(request, "user_id")
    page = pagination(request)
    cursor, limit = (page.cursor, page.limit)
    rows, next_cursor = await (await scope(request).get(AdminQueries)).transitions(user_id, cursor, limit)
    return respond(TransitionPage(items=[UserTransition(**asdict(row)) for row in rows], next_cursor=next_cursor), 200)


@router.get("/admin/api/v1/users/{user_id}/location", name="admin.getLocation")
async def user_location(request: web.Request) -> web.Response:
    user_id = path_integer(request, "user_id")
    row = await (await scope(request).get(AdminQueries)).location(user_id)
    return respond(
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
        ),
        200,
    )


@router.post("/admin/api/v1/auth/telegram", name="admin.exchangeTelegram")
async def exchange_telegram(request: web.Request) -> web.Response:
    body = await parse_body(request, ExchangeTelegram)
    login = await (await scope(request).get(AdminAuthService)).exchange_telegram(body.init_data)
    return respond(
        MiniAppSession(user_id=login.admin.user_id, expires_at=login.admin.expires_at, access_token=login.access_token)
    )


@router.get("/admin/api/v1/texts", name="admin.getTextCatalog")
async def text_catalog(request: web.Request) -> web.Response:
    draft = await (await scope(request).get(TextCatalogService)).draft()
    return respond(TextCatalogDraft(**asdict(draft)))


@router.put("/admin/api/v1/texts/{key}", name="admin.saveTextEntry")
async def save_text(request: web.Request) -> web.Response:
    body = await parse_body(request, SaveTextEntry)
    draft = await (await scope(request).get(TextCatalogService)).save_entry(
        request.match_info["key"],
        body.entry,
        body.expected_revision,
    )
    return respond(TextCatalogDraft(**asdict(draft)))


@router.post("/admin/api/v1/texts/publish", name="admin.publishTextCatalog")
async def publish_texts(request: web.Request) -> web.Response:
    body = await parse_body(request, PublishDraft)
    release = await (await scope(request).get(TextCatalogService)).publish(
        body.expected_revision, admin(request).user_id
    )
    return respond(TextCatalogRelease(**asdict(release)))


@router.get("/admin/api/v1/texts/releases", name="admin.listTextCatalogReleases")
async def text_releases(request: web.Request) -> web.Response:
    releases = await (await scope(request).get(TextCatalogService)).versions()
    return respond(TextCatalogVersions(items=[TextCatalogRelease(**asdict(release)) for release in releases]))


@router.post("/admin/api/v1/texts/activate", name="admin.activateTextCatalog")
async def activate_texts(request: web.Request) -> web.Response:
    body = await parse_body(request, ActivateTextCatalog)
    draft = await (await scope(request).get(TextCatalogService)).activate(
        body.release_id, body.expected_current_release
    )
    return respond(TextCatalogDraft(**asdict(draft)))


@router.get("/admin/api/v1/catalog", name="admin.getEditorCatalog")
async def catalog(request: web.Request) -> web.Response:
    from manashelper.platform.web.routing import IntegerPath, validate

    release = request.query.get("text_catalog_release")
    if release is None:
        return await catalog_content(request)
    selected = validate(IntegerPath, {"value": release}, "query/text_catalog_release").value
    snapshot = await (await scope(request).get(TextCatalogService)).version(selected)
    with i18n.use_catalog(snapshot):
        return await catalog_content(request)
