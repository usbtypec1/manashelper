"""aiohttp administrative transport; the production lifecycle belongs to main."""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from aiohttp import web
from aiohttp.typedefs import Handler
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from manashelper.bootstrap import load_models
from manashelper.core.config import Settings, get_settings
from manashelper.core.provider import CoreProvider
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.ui_flows.presentation.admin_contracts import ApiError
from manashelper.modules.ui_flows.presentation.admin_provider import AdminUiFlowsProvider
from manashelper.modules.ui_flows.presentation.admin_router import router
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.provider import TextCatalogProvider
from manashelper.platform.telegram.provider import TelegramPlatformProvider
from manashelper.platform.web.auth import AuthenticationError, ForbiddenError, web_origin
from manashelper.platform.web.cursors import InvalidCursorError
from manashelper.platform.web.frontend import install_editor
from manashelper.platform.web.keys import CONTAINER_KEY, SETTINGS_KEY
from manashelper.platform.web.landing import login_page
from manashelper.platform.web.miniapp import InvalidInitDataError, TooManyExchangesError
from manashelper.platform.web.provider import WebPlatformProvider
from manashelper.platform.web.routing import RequestContractError, admin_scope
from ui_flows.errors import FlowConflictError, FlowExecutionError, FlowNotFoundError, InvalidFlowError

logger = logging.getLogger(__name__)


def error_response(error: Exception) -> web.Response:
    issues = error.issues if isinstance(error, (InvalidFlowError, RequestContractError)) else []
    if isinstance(error, (AuthenticationError, InvalidInitDataError)):
        status, code, message = 401, "authentication_required", "Administrative session or launch context is invalid"
    elif isinstance(error, ForbiddenError):
        status, code, message = 403, "forbidden", "Origin or CSRF validation failed"
    elif isinstance(error, FlowNotFoundError):
        status, code, message = 404, "not_found", "Scenario or version does not exist"
    elif isinstance(error, FlowConflictError):
        status, code, message = 409, "revision_conflict", "Reload the current revision before retrying"
    elif isinstance(error, TooManyExchangesError):
        status, code, message = 429, "exchange_limit", "Wait before opening another administrative session"
    elif isinstance(error, (InvalidFlowError, FlowExecutionError, InvalidCursorError, RequestContractError)):
        status, code, message = 422, "invalid_request", "Request does not match the scenario contract"
    elif isinstance(error, web.HTTPException):
        status, code, message = error.status, "http_error", error.reason
    else:
        # Do not log exception values, request bodies, initData or credentials.
        logger.error("HTTP request failed (%s)", type(error).__name__)
        status, code, message = 500, "internal_error", "Request could not be completed"
    result = web.json_response(
        ApiError(code=code, message=message, issues=issues).model_dump(mode="json"), status=status
    )
    if status == 429:
        result.headers["Retry-After"] = "60"
    return result


@web.middleware
async def http_boundary(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        result = await handler(request)
    except Exception as error:
        result = error_response(error)
    result.headers.update(
        {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}
    )
    return result


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_admin_app(
    settings: Settings | None = None,
    container: AsyncContainer | None = None,
    ui_directory: Path | None = None,
) -> web.Application:
    configured = settings or get_settings()
    load_models()
    preview_slots = asyncio.Semaphore(4)

    @web.middleware
    async def limit_preview(request: web.Request, handler: Handler) -> web.StreamResponse:
        if request.path.endswith("/preview") and (request.match_info.route.name or "").startswith("admin."):
            if preview_slots.locked():
                raise web.HTTPServiceUnavailable()
            async with preview_slots:
                return await handler(request)
        return await handler(request)

    app = web.Application(middlewares=[http_boundary, limit_preview, admin_scope], client_max_size=1024 * 1024)
    app[SETTINGS_KEY] = configured
    app.router.add_get("/health", health)
    if container is not None:
        app[CONTAINER_KEY] = container
    else:

        class WebSettings(Provider):
            @provide(scope=Scope.APP, override=True)
            def config(self) -> Settings:
                return configured

        async def owned_container(app: web.Application) -> AsyncIterator[None]:
            async with make_async_container(
                CoreProvider(),
                TextCatalogProvider(),
                TelegramPlatformProvider(),
                WebSettings(),
                StudentQuestionsProvider(),
                UsersProvider(),
                ScheduleProvider(),
                NotificationsProvider(),
                FoodMenuProvider(),
                UiFlowsProvider(),
                WebPlatformProvider(),
                AdminUiFlowsProvider(),
            ) as owned:
                app[CONTAINER_KEY] = owned
                yield

        app.cleanup_ctx.append(owned_container)
    if configured.admin_web_origin is not None or configured.admin_web_signing_key is not None:
        web_origin(configured)
        app.add_routes(router)
        if not install_editor(app, ui_directory or Path(__file__).resolve().parents[3] / "admin-ui/dist"):
            app.router.add_get("/admin/", login_page)
    return app
