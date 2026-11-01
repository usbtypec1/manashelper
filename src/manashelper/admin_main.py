"""Separate administrative HTTP process; never starts polling or scheduled jobs."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from manashelper.bootstrap import load_models
from manashelper.core.config import Settings, get_settings
from manashelper.core.logging import configure_logging
from manashelper.core.provider import CoreProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.ui_flows.presentation.admin_contracts import ApiError
from manashelper.modules.ui_flows.presentation.admin_provider import AdminUiFlowsProvider
from manashelper.modules.ui_flows.presentation.admin_router import router
from manashelper.modules.ui_flows.presentation.openapi import build_openapi
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.web.auth import AuthenticationError, ForbiddenError, web_origin
from manashelper.platform.web.cursors import InvalidCursorError
from manashelper.platform.web.frontend import install_editor
from manashelper.platform.web.landing import login_page
from manashelper.platform.web.provider import WebPlatformProvider
from ui_flows.domain.contracts import ContractIssue
from ui_flows.errors import (
    FlowConflictError,
    FlowExecutionError,
    FlowNotFoundError,
    InvalidFlowError,
)

logger = logging.getLogger(__name__)


class AdminFastAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        return build_openapi()


def create_app(
    settings: Settings | None = None,
    container: AsyncContainer | None = None,
    ui_directory: Path | None = None,
) -> FastAPI:
    configured_settings = settings or get_settings()
    web_origin(configured_settings)
    load_models()

    class WebSettings(Provider):
        @provide(scope=Scope.APP, override=True)
        def config(self) -> Settings:
            return configured_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if container is not None:
            app.state.container = container
            yield
        else:
            async with make_async_container(
                CoreProvider(),
                WebSettings(),
                StudentQuestionsProvider(),
                UsersProvider(),
                UiFlowsProvider(),
                WebPlatformProvider(),
                AdminUiFlowsProvider(),
            ) as owned:
                app.state.container = owned
                yield

    app = AdminFastAPI(
        title="Manashelper interface editor",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    app.state.admin_settings = configured_settings
    if container is not None:
        app.state.container = container
    app.include_router(router)
    if not install_editor(app, ui_directory or Path(__file__).resolve().parents[1] / "admin-ui/dist"):
        app.add_api_route("/admin/", login_page, methods=["GET"], include_in_schema=False)

    @app.middleware("http")
    async def response_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    async def domain_error(request: Request, error: Exception) -> JSONResponse:
        issues = error.issues if isinstance(error, InvalidFlowError) else []
        if isinstance(error, RequestValidationError):
            issues = [
                ContractIssue(
                    code="schema_" + item["type"],
                    path="/" + "/".join(str(part) for part in item["loc"]),
                    message="Value does not match the contract: " + item["type"],
                )
                for item in error.errors()
            ]
        if isinstance(error, AuthenticationError):
            status, code, message = 401, "authentication_required", "Administrative session or ticket is invalid"
        elif isinstance(error, ForbiddenError):
            status, code, message = 403, "forbidden", "Origin or CSRF validation failed"
        elif isinstance(error, FlowNotFoundError):
            status, code, message = 404, "not_found", "Scenario or version does not exist"
        elif isinstance(error, FlowConflictError):
            status, code, message = 409, "revision_conflict", "Reload the current revision before retrying"
        else:
            status, code, message = 422, "invalid_request", "Request does not match the scenario contract"
        return JSONResponse(
            ApiError(code=code, message=message, issues=issues).model_dump(mode="json"), status_code=status
        )

    for error_type in (
        AuthenticationError,
        ForbiddenError,
        FlowNotFoundError,
        FlowConflictError,
        InvalidFlowError,
        FlowExecutionError,
        InvalidCursorError,
        RequestValidationError,
    ):
        app.add_exception_handler(error_type, domain_error)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception) -> JSONResponse:
        logger.error("Administrative request failed (%s)", type(error).__name__)
        return JSONResponse(
            ApiError(code="internal_error", message="Request could not be completed").model_dump(),
            status_code=500,
            headers={"Cache-Control": "no-store"},
        )

    return app


def main() -> None:
    configure_logging()
    uvicorn.run(create_app(), host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()
