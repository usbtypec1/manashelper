from urllib.parse import parse_qs

import httpx
import pytest

from manashelper.modules.eders.errors import EdersFetchError, EdersUnsafeUrlError
from manashelper.modules.eders.infrastructure.client import COURSES_URL, LOGIN_URL
from tests.modules.eders.factories import make_eders_client

LOGIN_FORM = '<form><input name="username" type="text"><input name="logintoken" value="fresh-token"></form>'
COURSES_PAGE = '<script>M.cfg = {"sesskey":"sessionkey"};</script>'


async def test_form_login_uses_fresh_token_shared_password_and_cookies():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "eders.manas.edu.kg"
        if len(requests) == 1:
            return httpx.Response(200, text=LOGIN_FORM, headers={"set-cookie": "MoodleSession=first; Path=/"})
        assert "MoodleSession=" in request.headers["cookie"]
        if len(requests) == 2:
            assert request.method == "POST"
            assert request.headers["content-type"] == "application/x-www-form-urlencoded"
            assert parse_qs(request.content.decode(), keep_blank_values=True) == {
                "anchor": [""],
                "logintoken": ["fresh-token"],
                "username": ["2204.01001"],
                "password": ["shared&token=+ пароль"],
            }
            return httpx.Response(303, headers={"location": "/login/index.php?loginredirect=1"})
        assert request.method == "GET" and not request.content
        if len(requests) == 3:
            return httpx.Response(303, headers={"location": "/login/index.php?testsession=123"})
        if len(requests) == 4:
            return httpx.Response(
                303, headers={"location": "/my/courses.php", "set-cookie": "MoodleSession=second; Path=/"}
            )
        assert str(request.url) == COURSES_URL
        assert request.headers["cookie"] == "MoodleSession=second"
        return httpx.Response(200, text=COURSES_PAGE)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await make_eders_client("shared&token=+ пароль").login(client, "2204.01001") == "sessionkey"
    assert len(requests) == 5


@pytest.mark.parametrize("page", ["<form></form>", LOGIN_FORM.replace('value="fresh-token"', 'value=""')])
async def test_missing_form_token_does_not_submit_credentials(page):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=page)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EdersFetchError, match="login token"):
            await make_eders_client().login(client, "fake-student")
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.parametrize("destination", ["/login/index.php?loginredirect=1", "/my/", "/my/courses.php"])
async def test_failed_login_is_not_a_success_even_with_sesskey(destination):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(303, headers={"location": destination})
        if str(request.url) == LOGIN_URL:
            return httpx.Response(200, text=LOGIN_FORM)
        return httpx.Response(200, text=LOGIN_FORM + COURSES_PAGE)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EdersFetchError, match="login failed"):
            await make_eders_client().login(client, "fake-student")


@pytest.mark.parametrize(
    "destination",
    [
        "https://evil.example/my/courses.php",
        "http://eders.manas.edu.kg/my/courses.php",
        "/login/logout.php?sesskey=secret",
        "/auth/userkey/login.php?key=secret",
        "/login/index.php?loginredirect=1&action=delete",
        "/my/courses.php?action=delete",
    ],
)
async def test_login_rejects_unsafe_redirect_before_following(destination):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, text=LOGIN_FORM)
        return httpx.Response(303, headers={"location": destination})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EdersUnsafeUrlError):
            await make_eders_client().login(client, "fake-student")
    assert len(requests) == 2


@pytest.mark.parametrize("status", [307, 308])
async def test_login_never_replays_password_on_preserving_redirect(status):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, text=LOGIN_FORM)
        return httpx.Response(status, headers={"location": "/my/courses.php"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EdersUnsafeUrlError):
            await make_eders_client().login(client, "fake-student")
    assert len(requests) == 2


@pytest.mark.parametrize("password", [None, ""])
async def test_disabled_eders_never_requests_login(password):
    def handler(request):
        pytest.fail("Disabled Eders made an HTTP request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EdersFetchError, match="disabled"):
            await make_eders_client(password).login(client, "fake-student")
