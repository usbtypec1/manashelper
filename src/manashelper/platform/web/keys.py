from aiohttp import web
from dishka import AsyncContainer

from manashelper.core.config import Settings
from manashelper.platform.web.auth_repository import AuthenticatedAdmin

SETTINGS_KEY = web.AppKey("settings", Settings)
CONTAINER_KEY = web.AppKey("container", AsyncContainer)
REQUEST_CONTAINER_KEY = web.RequestKey("container", AsyncContainer)
ADMIN_KEY = web.RequestKey("admin", AuthenticatedAdmin)
AUTH_TOKEN_KEY = web.RequestKey("auth_token", str)
BEARER_KEY = web.RequestKey("bearer", bool)
