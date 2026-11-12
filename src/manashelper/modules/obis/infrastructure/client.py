import httpx

from manashelper.modules.obis.application.models import ObisLoginAttempt, ObisLoginChallenge
from manashelper.modules.obis.errors import ObisCaptchaError, ObisLoginError, ObisParseError, ObisSessionExpiredError
from manashelper.modules.obis.infrastructure.parser import (
    has_captcha_error,
    is_login_page,
    parse_login_page_captcha_url,
    parse_login_page_csrf_token,
)

OBIS_BASE_URL = "https://obistest.manas.edu.kg"
OBIS_HOST = httpx.URL(OBIS_BASE_URL).host
OBIS_LOGIN_PATH = "/site/login"
OBIS_ATTENDANCE_PATH = "/vs-ders/taken-lessons"
OBIS_EXAM_GRADES_PATH = "/vs-ders/taken-grades"
OBIS_TRANSCRIPT_PATH = "/vs-ders/transkript-detailed"


def new_http_client(cookies: dict[str, str] | None = None) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=OBIS_BASE_URL, follow_redirects=True, timeout=15.0)
    for name, value in (cookies or {}).items():
        # Bind restored cookies to OBIS so server updates replace them instead of adding duplicates.
        client.cookies.set(name, value, domain=OBIS_HOST)
    return client


def session_cookies(client: httpx.AsyncClient) -> dict[str, str]:
    return {cookie.name: cookie.value for cookie in client.cookies.jar if cookie.value is not None}


async def login(client: httpx.AsyncClient, student_number: str, plain_password: str) -> None:
    """Legacy captcha-less login kept for the Eders SSO fallback; OBIS now rejects it."""
    login_page = await client.get(OBIS_LOGIN_PATH)
    login_page.raise_for_status()
    csrf_token = parse_login_page_csrf_token(login_page.text)

    response = await client.post(
        OBIS_LOGIN_PATH,
        data={
            "LoginForm[username]": student_number,
            "LoginForm[password_hash]": plain_password,
            "_csrf": csrf_token,
        },
    )
    response.raise_for_status()
    if response.url.path.rstrip("/") == OBIS_LOGIN_PATH:
        raise ObisLoginError("Invalid OBIS credentials")


def _is_login_response(response: httpx.Response) -> bool:
    return response.url.path.rstrip("/") == OBIS_LOGIN_PATH or is_login_page(response.text)


class ObisClient:
    async def start_login(self) -> ObisLoginChallenge:
        async with new_http_client() as client:
            page = await client.get(OBIS_LOGIN_PATH)
            page.raise_for_status()
            csrf_token = parse_login_page_csrf_token(page.text)
            image = await client.get(parse_login_page_captcha_url(page.text))
            image.raise_for_status()
            if not image.headers.get("content-type", "").startswith("image/"):
                raise ObisParseError("OBIS captcha is not an image.")
            return ObisLoginChallenge(ObisLoginAttempt(session_cookies(client), csrf_token), image.content)

    async def complete_login(
        self, attempt: ObisLoginAttempt, student_number: str, plain_password: str, captcha_code: str
    ) -> dict[str, str]:
        async with new_http_client(attempt.cookies) as client:
            response = await client.post(
                OBIS_LOGIN_PATH,
                data={
                    "LoginForm[username]": student_number,
                    "LoginForm[password_hash]": plain_password,
                    "LoginForm[verifyCode]": captcha_code,
                    "_csrf": attempt.csrf_token,
                },
            )
            if response.status_code == httpx.codes.BAD_REQUEST:
                # Yii rejects an expired CSRF token before checking the captcha or credentials.
                raise ObisCaptchaError("OBIS login form expired")
            response.raise_for_status()
            if _is_login_response(response):
                if has_captcha_error(response.text):
                    raise ObisCaptchaError("Invalid OBIS captcha")
                raise ObisLoginError("Invalid OBIS credentials")
            return session_cookies(client)

    async def fetch_transcript_html(self, cookies: dict[str, str]) -> str:
        return await self._fetch(cookies, OBIS_TRANSCRIPT_PATH)

    async def fetch_attendance_html(self, cookies: dict[str, str]) -> str:
        return await self._fetch(cookies, OBIS_ATTENDANCE_PATH)

    async def fetch_exam_grades_html(self, cookies: dict[str, str]) -> str:
        return await self._fetch(cookies, OBIS_EXAM_GRADES_PATH)

    async def _fetch(self, cookies: dict[str, str], path: str) -> str:
        async with new_http_client(cookies) as client:
            response = await client.get(path)
            response.raise_for_status()
            if _is_login_response(response):
                raise ObisSessionExpiredError
            return response.text
