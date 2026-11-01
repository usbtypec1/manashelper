"""Build the administrative contract without depending on a web framework."""

from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from manashelper.modules.ui_flows.presentation.admin_contracts import (
    ActivateVersion,
    AdminSession,
    ApiError,
    DelegateCatalog,
    DraftContent,
    EditorCatalog,
    ExchangeTicket,
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
    ValidationReport,
    VersionContent,
    VersionPage,
)


def build_openapi() -> dict[str, Any]:
    models: list[type[BaseModel]] = [
        ActivateVersion,
        AdminSession,
        ApiError,
        DelegateCatalog,
        DraftContent,
        EditorCatalog,
        ExchangeTicket,
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
        ValidationReport,
        VersionPage,
        VersionContent,
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
            "security": [] if public else [{"AdminSession": [], **({"CsrfToken": []} if method != "get" else {})}],
        }
        parameters: list[dict[str, Any]] = []
        for name in ("id", "user_id", "version"):
            if "{" + name + "}" in path:
                parameters.append(
                    {
                        "name": name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer" if name in {"user_id", "version"} else "string"},
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
        "Read allowed gettext templates and capability definitions.",
        EditorCatalog,
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
        "as issues; no real data is fetched. Rendered text uses the same safe formatting rules as Telegram.",
        PreviewResult,
        PreviewRequest,
    )
    add(
        "/flows/{id}/publish",
        "post",
        "publishFlow",
        "Validate and atomically publish the stored expected_revision. "
        "Repeating publication of that revision returns its original version without creating another. "
        "It does not reactivate an older version after rollback; use activate explicitly. Active sessions stay pinned.",
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
            "All operations except ticket exchange require an authorized administrator session. "
            "Mutations additionally require X-CSRF-Token and same-origin validation. "
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
            },
        },
    }
