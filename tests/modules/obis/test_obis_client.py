import httpx
import pytest

from manashelper.modules.obis.application.models import ObisLoginAttempt
from manashelper.modules.obis.errors import ObisCaptchaError, ObisLoginError, ObisParseError, ObisSessionExpiredError
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.parser import parse_login_page_captcha_url
from tests.paths import FIXTURES_DIR

LOGIN_PAGE = (FIXTURES_DIR / "obis/login.html").read_text(encoding="utf-8")
ATTEMPT = ObisLoginAttempt({"PHPSESSID": "form-session", "_csrf": "csrf-cookie"}, "fixture-csrf-token")


def _login_page(captcha_error: str = "") -> str:
    return LOGIN_PAGE.replace("{captcha_error}", captcha_error)


@pytest.fixture
def obis(monkeypatch):
    requests: list[httpx.Request] = []
    routes: dict[tuple[str, str], httpx.Response] = {}
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = routes[(request.method, request.url.path)]
        return httpx.Response(response.status_code, headers=response.headers, content=response.content)

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)
    )
    return routes, requests


async def test_start_login_keeps_captcha_bound_to_login_form_cookies(obis):
    routes, requests = obis
    routes[("GET", "/site/login")] = httpx.Response(
        200, headers={"set-cookie": "PHPSESSID=form-session; path=/; secure; HttpOnly"}, text=_login_page()
    )
    routes[("GET", "/site/captcha")] = httpx.Response(200, headers={"content-type": "image/png"}, content=b"png")

    challenge = await ObisClient().start_login()

    assert challenge.captcha_image == b"png"
    assert challenge.attempt == ObisLoginAttempt({"PHPSESSID": "form-session"}, "fixture-csrf-token")
    assert requests[1].url.params["v"] == "6af55f2dc10ce9.56575628"
    assert requests[1].headers["cookie"] == "PHPSESSID=form-session"


async def test_start_login_rejects_non_image_captcha(obis):
    routes, _ = obis
    routes[("GET", "/site/login")] = httpx.Response(200, text=_login_page())
    routes[("GET", "/site/captcha")] = httpx.Response(200, headers={"content-type": "text/html"}, text="<html>")
    with pytest.raises(ObisParseError):
        await ObisClient().start_login()


@pytest.mark.parametrize("source", ["https://evil.example/site/captcha", "//evil.example/x", ""])
def test_captcha_url_must_stay_on_obis(source):
    page = _login_page().replace("/site/captcha?v=6af55f2dc10ce9.56575628", source)
    with pytest.raises(ObisParseError):
        parse_login_page_captcha_url(page)


async def test_complete_login_submits_captcha_and_returns_rotated_session_cookies(obis):
    routes, requests = obis
    routes[("POST", "/site/login")] = httpx.Response(
        302, headers={"location": "/", "set-cookie": "PHPSESSID=authenticated; path=/; secure; HttpOnly"}
    )
    routes[("GET", "/")] = httpx.Response(200, text="<html>home</html>")

    cookies = await ObisClient().complete_login(ATTEMPT, "student", "password", "Ab3x9")

    assert cookies == {"PHPSESSID": "authenticated", "_csrf": "csrf-cookie"}
    form = dict(httpx.QueryParams(requests[0].content.decode()))
    assert form == {
        "LoginForm[username]": "student",
        "LoginForm[password_hash]": "password",
        "LoginForm[verifyCode]": "Ab3x9",
        "_csrf": "fixture-csrf-token",
    }
    assert "PHPSESSID=form-session" in requests[0].headers["cookie"]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(200, text=_login_page("The verification code is incorrect.")), ObisCaptchaError),
        (httpx.Response(200, text=_login_page()), ObisLoginError),
        (httpx.Response(400, text="Unable to verify your data submission."), ObisCaptchaError),
    ],
)
async def test_complete_login_distinguishes_captcha_and_credential_failures(obis, response, error):
    routes, _ = obis
    routes[("POST", "/site/login")] = response
    with pytest.raises(error):
        await ObisClient().complete_login(ATTEMPT, "student", "password", "wrong")


async def test_fetch_uses_saved_session_and_detects_expiry(obis):
    routes, requests = obis
    routes[("GET", "/vs-ders/taken-grades")] = httpx.Response(200, text="<table>grades</table>")
    assert await ObisClient().fetch_exam_grades_html({"PHPSESSID": "saved"}) == "<table>grades</table>"
    assert requests[0].headers["cookie"] == "PHPSESSID=saved"

    routes[("GET", "/vs-ders/taken-grades")] = httpx.Response(302, headers={"location": "/site/login"})
    routes[("GET", "/site/login")] = httpx.Response(200, text=_login_page())
    with pytest.raises(ObisSessionExpiredError):
        await ObisClient().fetch_exam_grades_html({"PHPSESSID": "expired"})
