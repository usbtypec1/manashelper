import hmac
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute

from manashelper.platform.web.auth import COOKIE_NAME, AdminAuthService, ForbiddenError, web_origin


class AdminRoute(APIRoute):
    """Finish the application scope before returning the HTTP response to ASGI."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            async with request.app.state.container() as scope:
                request.state.container = scope
                auth = await scope.get(AdminAuthService)
                if request.method not in {"GET", "HEAD"} and request.headers.get("origin") != web_origin(
                    request.app.state.admin_settings
                ):
                    raise ForbiddenError("Same-origin requests are required")
                if request.url.path != "/admin/api/v1/auth/exchange":
                    cookie = request.cookies.get(COOKIE_NAME)
                    request.state.admin = await auth.authenticate(cookie)
                    if request.method not in {"GET", "HEAD"}:
                        expected = auth.csrf(cookie or "")
                        provided = request.headers.get("x-csrf-token", "")
                        if not hmac.compare_digest(expected.encode(), provided.encode()):
                            raise ForbiddenError("CSRF token is invalid")
                return await original(request)

        return handle
