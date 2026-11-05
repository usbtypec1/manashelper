from datetime import UTC, datetime
from urllib.parse import parse_qsl

from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web


def authenticate(authorization: str, bot_token: str) -> int:
    scheme, _, raw = authorization.partition(" ")
    if scheme != "tma" or not raw or len(raw) > 16384:
        raise web.HTTPUnauthorized()
    try:
        pairs = parse_qsl(raw, strict_parsing=True)
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("Duplicate initData fields")
        data = safe_parse_webapp_init_data(bot_token, raw)
        age = datetime.now(UTC).timestamp() - data.auth_date.timestamp()
        if not -30 <= age <= 3600 or data.user is None or data.user.is_bot:
            raise ValueError("Expired or missing user")
        return data.user.id
    except (ValueError, TypeError, KeyError) as error:
        raise web.HTTPUnauthorized() from error
