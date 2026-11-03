"""Build the administrative contract without depending on a web framework."""

from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from manashelper.modules.ui_flows.presentation.admin_contracts import (
    ActivateTextCatalog,
    ActivateVersion,
    AdminSession,
    ApiError,
    DelegateCatalog,
    DraftContent,
    EditorCatalog,
    ExchangeTelegram,
    ExchangeTicket,
    FlowDraft,
    FlowPage,
    FlowSummary,
    FlowVersion,
    LocationPage,
    MiniAppSession,
    PreviewRequest,
    PreviewResult,
    PublishDraft,
    RolloutStatus,
    SaveDraft,
    SaveTextEntry,
    SaveTriggers,
    SetRollout,
    TextCatalogDraft,
    TextCatalogRelease,
    TextCatalogVersions,
    TransitionPage,
    TriggerDraftContent,
    TriggerReleaseContent,
    TriggerVersions,
    UserLocation,
    ValidationReport,
    VersionContent,
    VersionPage,
)
from ui_flows.domain.texts import TextDocument, TextEntry, TextVariant


def build_openapi() -> dict[str, Any]:
    models: list[type[BaseModel]] = [
        ActivateTextCatalog,
        ActivateVersion,
        AdminSession,
        ApiError,
        DelegateCatalog,
        DraftContent,
        EditorCatalog,
        ExchangeTicket,
        ExchangeTelegram,
        MiniAppSession,
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
        SaveTextEntry,
        SetRollout,
        TextCatalogDraft,
        TextCatalogRelease,
        TextCatalogVersions,
        TextDocument,
        TextEntry,
        TextVariant,
        TransitionPage,
        ValidationReport,
        VersionPage,
        VersionContent,
        SaveTriggers,
        TriggerDraftContent,
        TriggerReleaseContent,
        TriggerVersions,
    ]
    _, schemas = models_json_schema(
        [(model, "validation") for model in models], ref_template="#/components/schemas/{model}"
    )

    def content(model: type[BaseModel]) -> dict[str, Any]:
        return {"application/json": {"schema": {"$ref": f"#/components/schemas/{model.__name__}"}}}

    paths: dict[str, Any] = {}

    def add(
        path: str,
        method: str,
        operation_id: str,
        description: str,
        response: type[BaseModel] | None,
        request: type[BaseModel] | None = None,
        *,
        public: bool = False,
        paginated: bool = False,
        created: bool = False,
    ) -> None:
        status = "204" if response is None else ("201" if created else "200")
        responses: dict[str, Any] = {status: {"description": "Success"}}
        if response is not None:
            responses[status]["content"] = content(response)
        if operation_id in {"exchangeTicket", "logout"}:
            responses[status]["headers"] = {
                "Set-Cookie": {
                    "description": "Set or clear HttpOnly admin session cookie",
                    "schema": {"type": "string"},
                }
            }
        for code, meaning in {
            "401": "Authentication required",
            "403": "Forbidden or CSRF check failed",
            "404": "Resource not found",
            "409": "Revision conflict or already exists",
            "422": "Invalid request or scenario",
        }.items():
            responses[code] = {"description": meaning, "content": content(ApiError)}
        operation: dict[str, Any] = {
            "operationId": operation_id,
            "description": description,
            "responses": responses,
            "security": []
            if public
            else [
                {"AdminSession": [], **({"CsrfToken": []} if method != "get" else {})},
                {"MiniAppBearer": []},
            ],
        }
        parameters: list[dict[str, Any]] = []
        for name in ("id", "user_id", "version", "key"):
            if "{" + name + "}" in path:
                parameters.append(
                    {
                        "name": name,
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "integer" if name in {"user_id", "version"} else "string",
                            **({"minLength": 1, "maxLength": 120} if name == "key" else {}),
                        },
                    }
                )
        if paginated:
            parameters.extend(
                [
                    {"name": "cursor", "in": "query", "schema": {"type": "string", "maxLength": 256}},
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                    },
                ]
            )
        if parameters:
            operation["parameters"] = parameters
        if request is not None:
            operation["requestBody"] = {"required": True, "content": content(request)}
        paths.setdefault(path, {})[method] = operation

    add(
        "/auth/exchange",
        "post",
        "exchangeTicket",
        "Consume an admin-issued, single-use login ticket; "
        "tickets expire in 5 minutes. Require same-origin requests. Return a session expiring in 8 hours; "
        "the cookie is HttpOnly, Secure, SameSite=Strict. Reusing an expired/consumed ticket returns 401.",
        AdminSession,
        ExchangeTicket,
        public=True,
    )
    add("/auth/logout", "post", "logout", "Revoke the current session and clear its cookie.", None)
    add(
        "/auth/telegram",
        "post",
        "exchangeTelegram",
        "Validate signed Telegram initData (configured administrator, age <= 5 minutes, no future timestamp). "
        "Require same Origin. Return an 8-hour bearer token; store it only in memory. "
        "At most 5 valid exchanges per minute per running host; later exchanges return 429. No cookie is issued.",
        MiniAppSession,
        ExchangeTelegram,
        public=True,
    )
    paths["/auth/telegram"]["post"]["responses"]["429"] = {
        "description": "Exchange limit",
        "content": content(ApiError),
    }
    add(
        "/auth/session",
        "get",
        "getAdminSession",
        "Read the current session and recover its CSRF token after a page reload.",
        AdminSession,
    )
    add(
        "/rollout",
        "get",
        "getRollout",
        "Read launch mode, revision and active-dialog count. Missing state defaults to admin-only.",
        RolloutStatus,
    )
    add(
        "/rollout",
        "put",
        "setRollout",
        "Set admin/all/off with expected_revision. All requires valid published menus and survey. "
        "Off stops new launches while existing sessions continue; no schema rollback is needed.",
        RolloutStatus,
        SetRollout,
    )
    add("/flows", "get", "listFlows", "List scenarios ordered by stable ID.", FlowPage, paginated=True)
    add(
        "/flows/{id}/versions/{version}",
        "get",
        "getVersion",
        "Read an immutable version for monitoring; editing uses the draft.",
        VersionContent,
    )
    add(
        "/users/{user_id}/location",
        "get",
        "getLocation",
        "Read the current or last observed user position without form data.",
        UserLocation,
    )
    add(
        "/catalog",
        "get",
        "getEditorCatalog",
        "Read allowed user-text templates from the current immutable catalog release and capability definitions.",
        EditorCatalog,
    )
    add(
        "/texts",
        "get",
        "getTextCatalog",
        "Read the editable user-text document, its optimistic-concurrency revision and current published release.",
        TextCatalogDraft,
    )
    add(
        "/texts/{key}",
        "put",
        "saveTextEntry",
        "Replace one draft text entry if expected_revision matches. The entry key must match the path. "
        "Editing the draft does not change published releases or active sessions.",
        TextCatalogDraft,
        SaveTextEntry,
    )
    add(
        "/texts/publish",
        "post",
        "publishTextCatalog",
        "Validate all locales, themes, plural forms, placeholders and display limits, then publish an immutable "
        "catalog release at expected_revision. Existing scenario versions retain their pinned text release.",
        TextCatalogRelease,
        PublishDraft,
    )
    add(
        "/texts/releases",
        "get",
        "listTextCatalogReleases",
        "List immutable user-text release metadata without changing the draft or publication pointer.",
        TextCatalogVersions,
    )
    add(
        "/texts/activate",
        "post",
        "activateTextCatalog",
        "Activate an existing text release if expected_current_release matches. Does not alter the draft, "
        "immutable scenario versions, active sessions or already rendered delivery intents.",
        TextCatalogDraft,
        ActivateTextCatalog,
    )
    add(
        "/flows",
        "post",
        "createFlow",
        "Create an unpublished scenario at draft revision 0; duplicate ID returns 409.",
        FlowDraft,
        DraftContent,
        created=True,
    )
    add("/flows/{id}", "get", "getFlow", "Read draft and publication pointers.", FlowSummary)
    add("/flows/{id}/draft", "get", "getDraft", "Read the editable document and its current revision.", FlowDraft)
    add(
        "/flows/{id}/draft",
        "put",
        "saveDraft",
        "Replace a draft if expected_revision matches; increment its revision. "
        "document.id must match the path. Semantic errors may be saved for subsequent editing; structurally "
        "invalid documents return 422. Retrying with an old revision returns 409.",
        FlowDraft,
        SaveDraft,
    )
    add(
        "/flows/{id}/validate",
        "post",
        "validateFlow",
        "Validate an unsaved document against registered contracts. "
        "Semantic issues return 200 with an issues list; malformed input returns 422.",
        ValidationReport,
        DraftContent,
    )
    add(
        "/flows/{id}/preview",
        "post",
        "previewFlow",
        "Simulate an unsaved scenario with supplied test data and "
        "delegate results. Never call live delegates or create user sessions. Missing stub results are reported "
        "as issues; no real data is fetched. An optional text_catalog_release selects a historical immutable "
        "text snapshot; omitted selects the current release. Rendered text uses the same resolver as Telegram.",
        PreviewResult,
        PreviewRequest,
    )
    add(
        "/flows/{id}/publish",
        "post",
        "publishFlow",
        "Validate and atomically publish the stored expected_revision. "
        "Repeating publication of that revision returns its original version without creating another. "
        "It does not reactivate an older version after rollback; use activate explicitly. Active sessions stay pinned. "
        "The new scenario version pins the catalog release used to validate it.",
        FlowVersion,
        PublishDraft,
    )
    add(
        "/flows/{id}/versions",
        "get",
        "listVersions",
        "List immutable version metadata newest first.",
        VersionPage,
        paginated=True,
    )
    add(
        "/flows/{id}/activate",
        "post",
        "activateVersion",
        "Move the publication pointer to an existing version "
        "if expected_published_version matches. Does not migrate active sessions; incompatible delegate versions "
        "cannot be activated. A null expectation means the scenario has never been published.",
        FlowSummary,
        ActivateVersion,
    )
    add(
        "/triggers",
        "get",
        "getTriggers",
        "Read the trigger draft, revision and current immutable release.",
        TriggerDraftContent,
    )
    add(
        "/triggers",
        "put",
        "saveTriggers",
        "Save a typed trigger draft with optimistic concurrency. Publication validates matchers and targets.",
        TriggerDraftContent,
        SaveTriggers,
    )
    add(
        "/triggers/publish",
        "post",
        "publishTriggers",
        "Reject ambiguous/unsafe bindings and publish a manifest pinning scenario, delegate and text versions. "
        "Retries return the original release without reactivation.",
        TriggerReleaseContent,
        PublishDraft,
    )
    add(
        "/triggers/releases",
        "get",
        "listTriggerReleases",
        "Read immutable trigger manifests newest first.",
        TriggerVersions,
    )
    add(
        "/triggers/activate",
        "post",
        "activateTriggers",
        "Activate an immutable manifest with expected_current_release. "
        "Active sessions and displayed actions retain their pins.",
        TriggerDraftContent,
        ActivateTextCatalog,
    )
    add(
        "/delegates",
        "get",
        "listDelegates",
        "List available delegate contracts, not Python import paths or secrets.",
        DelegateCatalog,
    )
    add(
        "/users/locations",
        "get",
        "listLocations",
        "List registered users with runtime or last observed legacy positions ordered by user ID. "
        "Never return form answers or credentials. Unknown/lost legacy FSM states are marked explicitly. "
        "A sent screen does not imply it was read.",
        LocationPage,
        paginated=True,
    )
    add(
        "/users/{user_id}/transitions",
        "get",
        "listTransitions",
        "List transition metadata newest first, without message text or field values.",
        TransitionPage,
        paginated=True,
    )

    paths["/catalog"]["get"]["parameters"] = [
        {
            "name": "text_catalog_release",
            "in": "query",
            "schema": {"type": "integer", "minimum": 1},
            "description": "Read the pinned text release for historical monitoring; default is the current release.",
        }
    ]
    schemas["$defs"]["ApiError"]["examples"] = [
        {"code": "revision_conflict", "message": "The draft was changed; reload before saving.", "issues": []},
        {
            "code": "invalid_flow",
            "message": "The scenario cannot be published.",
            "issues": [
                {
                    "code": "missing_target",
                    "path": "/nodes/0/buttons/0/0/target",
                    "message": "Target does not exist",
                    "node_id": "main",
                    "button_id": "study",
                }
            ],
        },
    ]
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Manashelper interface editor",
            "version": "1.0.0",
            "description": "Administrative interface for scenario management. "
            "All operations except ticket/Telegram exchange require an authorized administrator session. "
            "Cookie mutations require X-CSRF-Token; bearer tokens have a separate digest namespace. "
            "All mutations require same-origin validation, including bearer mutations. "
            "Cursor pages use stable ordering; cursors are opaque and bound to the operation. "
            "No endpoint promises exactly-once Telegram delivery.",
        },
        "servers": [{"url": "/admin/api/v1"}],
        "paths": paths,
        "components": {
            "schemas": schemas["$defs"],
            "securitySchemes": {
                "AdminSession": {"type": "apiKey", "in": "cookie", "name": "manashelper_admin"},
                "CsrfToken": {"type": "apiKey", "in": "header", "name": "X-CSRF-Token"},
                "MiniAppBearer": {"type": "http", "scheme": "bearer"},
            },
        },
    }
