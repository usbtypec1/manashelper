import hmac
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiohttp import web
from dishka import AsyncContainer
from pydantic import ValidationError

from manashelper.core.config import Settings
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.presentation.catalog import localize_profile, ui_strings
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.telegram.webhook_context import webhook_processing
from manashelper.platform.telegram.webhook_middleware import ConcurrentWebhookUpdateError, WebhookReceiptMiddleware
from manashelper.platform.web.auth import authenticate
from manashelper.platform.web.preferences import register_preferences_routes

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_web_app(bot: Bot, dispatcher: Dispatcher, container: AsyncContainer, settings: Settings) -> web.Application:
    # Registered after Dishka's update middleware, so receipt and handler share
    # one request scope and transaction. Polling does not install this middleware.
    dispatcher.update.outer_middleware(WebhookReceiptMiddleware())

    @web.middleware
    async def response_headers(
        request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
    ) -> web.StreamResponse:
        try:
            response = await handler(request)
        except web.HTTPException as error:
            if request.path.startswith("/api/"):
                error.headers["Cache-Control"] = "no-store"
            error.headers["X-Content-Type-Options"] = "nosniff"
            raise
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app = web.Application(client_max_size=1024 * 1024, middlewares=[response_headers])

    async def webhook(request: web.Request) -> web.Response:
        secret = settings.webhook_secret.get_secret_value() if settings.webhook_secret else ""
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secret or not hmac.compare_digest(supplied.encode(), secret.encode()):
            raise web.HTTPUnauthorized()
        try:
            update = Update.model_validate(await request.json(), context={"bot": bot})
        except (ValueError, ValidationError) as error:
            raise web.HTTPBadRequest() from error
        token = webhook_processing.set(True)
        try:
            # feed_update avoids feed_webhook_update's timed background handoff,
            # which would acknowledge before the request scope commits.
            await dispatcher.feed_update(bot, update)
        except ConcurrentWebhookUpdateError as error:
            raise web.HTTPServiceUnavailable() from error
        finally:
            webhook_processing.reset(token)
        return web.json_response({"ok": True})

    async def gamification(request: web.Request) -> web.Response:
        user_id = authenticate(request.headers.get("Authorization", ""), settings.telegram_bot_token)
        async with container() as scope:
            if not await (await scope.get(UsersQuery)).exists(user_id):
                raise web.HTTPForbidden()
            query = await scope.get(GamificationQuery)
            if not await query.is_enabled(user_id):
                raise web.HTTPForbidden()
            payload: dict[str, Any]
            if request.path.endswith("/leaderboard"):
                payload = {
                    "entries": [
                        {
                            "full_name": entry.full_name,
                            "score": entry.score,
                            "rank": entry.rank,
                            "is_self": entry.user_id == user_id,
                        }
                        for entry in await query.leaderboard()
                    ]
                }
            else:
                locale = await (await scope.get(LocaleQuery)).get_locale(user_id)
                payload = localize_profile(await query.profile(user_id), locale.value)
                payload["ui"] = ui_strings(locale.value)
        return web.json_response(payload)

    async def index(request: web.Request) -> web.FileResponse:
        if not (STATIC_DIR / "index.html").is_file():
            raise web.HTTPServiceUnavailable(text="Mini App assets have not been built")
        return web.FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app.router.add_post("/telegram/webhook", webhook)
    app.router.add_get("/api/gamification/me", gamification)
    app.router.add_get("/api/gamification/leaderboard", gamification)
    register_preferences_routes(app, container, settings)
    app.router.add_get("/app", index)
    app.router.add_get("/app/", index)
    if (STATIC_DIR / "assets").is_dir():
        app.router.add_static("/app/assets", STATIC_DIR / "assets")
    app.router.add_get("/health", health)
    return app
