import secrets

from aiogram.utils.i18n import gettext as _
from aiohttp import web
from dishka import AsyncContainer
from yarl import URL

from manashelper.core.config import Settings
from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.use_cases.redeem_eders_login_link import RedeemEdersLoginLinkUseCase
from manashelper.modules.eders.errors import EdersFetchError, EdersUnsafeUrlError, InvalidEdersLoginLinkError
from manashelper.modules.obis.errors import (
    ObisManualLoginRequiredError,
    ObisRetryLaterError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html

# A fragment never reaches the HTTP access log. Remove it from browser history
# before an explicit POST; GET/HEAD previews cannot consume the grant.
LOGIN_SCRIPT = """
const token = location.hash.slice(1);
history.replaceState(null, '', location.pathname + location.search);
if (token) {
  const form = document.createElement('form');
  form.method = 'post';
  form.action = location.pathname + location.search;
  const input = document.createElement('input');
  input.type = 'hidden'; input.name = 'token'; input.value = token;
  form.append(input); document.body.append(form); form.submit();
} else {
  document.getElementById('message').textContent = document.getElementById('invalid').textContent;
}
"""


def login_page(request: web.Request, *, status: int = 200, launch: bool = False) -> web.Response:
    locale = request.query.get("lang", "ru")
    if locale not in {value.value for value in Locale}:
        locale = "ru"
    nonce = secrets.token_urlsafe(24)
    with i18n.context(), i18n.use_locale(locale):
        message = {
            200: _("eders.login_opening"),
            410: _("eders.login_expired"),
            409: _("eders.login_obis_required"),
            503: _("eders.login_failed"),
        }[status]
        expired = _("eders.login_expired")
        javascript = _("eders.login_javascript")
    body = (
        f'<!doctype html><html lang="{locale}"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Eders</title><body><p id="message">{escape_html(message)}</p>'
    )
    if launch:
        body += (
            f'<p id="invalid" hidden>{escape_html(expired)}</p>'
            f"<noscript>{escape_html(javascript)}</noscript>"
            f'<script nonce="{nonce}">{LOGIN_SCRIPT}</script>'
        )
    body += "</body></html>"
    return web.Response(
        text=body,
        content_type="text/html",
        status=status,
        headers={
            "Cache-Control": "no-store",
            # no-referrer makes browsers submit forms with Origin: null. The
            # fragment is already removed; only this origin may receive a referrer.
            "Referrer-Policy": "same-origin" if launch else "no-referrer",
            "Content-Security-Policy": (
                f"default-src 'none'; script-src 'nonce-{nonce}'; form-action 'self' https://eders.manas.edu.kg; "
                "base-uri 'none'; frame-ancestors 'none'"
            ),
        },
    )


def register_browser_login_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    if not settings.eders_enabled or not settings.public_url:
        return
    expected_origin = str(URL(settings.public_url).origin())

    async def landing(request: web.Request) -> web.Response:
        return login_page(request, launch=True)

    async def redeem(request: web.Request) -> web.Response:
        if request.headers.get("Origin") != expected_origin:
            raise web.HTTPForbidden()
        if request.content_length is None or request.content_length > 256:
            raise web.HTTPBadRequest()
        form = await request.post()
        tokens = form.getall("token", [])
        if len(tokens) != 1 or not isinstance(tokens[0], str):
            raise web.HTTPBadRequest()
        async with container() as scope:
            try:
                url = await (await scope.get(RedeemEdersLoginLinkUseCase)).execute(tokens[0])
            except InvalidEdersLoginLinkError:
                return login_page(request, status=410)
            except (UserNotFoundError, UserHasNoCredentialsError, ObisManualLoginRequiredError):
                # Catch inside the scope so OBIS manual-login/backoff state commits.
                return login_page(request, status=409)
            except (ObisRetryLaterError, EdersFetchError, EdersUnsafeUrlError):
                return login_page(request, status=503)
        raise web.HTTPSeeOther(location=url, headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})

    app.router.add_get("/api/eders/browser-login", landing)
    app.router.add_post("/api/eders/browser-login", redeem)
