import httpx

from manashelper.scraping.obis_parser import parse_login_page_csrf_token

OBIS_BASE_URL = "https://obistest.manas.edu.kg"
OBIS_LOGIN_PATH = "/site/login"
OBIS_ATTENDANCE_PATH = "/vs-ders/taken-lessons"
OBIS_EXAM_GRADES_PATH = "/vs-ders/taken-grades"


class ObisLoginError(Exception):
    pass


def _new_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=OBIS_BASE_URL, follow_redirects=True, timeout=15.0)


async def _login(client: httpx.AsyncClient, student_number: str, plain_password: str) -> None:
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


class ObisClient:
    async def verify_credentials(self, student_number: str, plain_password: str) -> None:
        async with _new_http_client() as client:
            await _login(client, student_number, plain_password)

    async def fetch_attendance_html(self, student_number: str, plain_password: str) -> str:
        async with _new_http_client() as client:
            await _login(client, student_number, plain_password)
            response = await client.get(OBIS_ATTENDANCE_PATH)
            response.raise_for_status()
            return response.text

    async def fetch_exam_grades_html(self, student_number: str, plain_password: str) -> str:
        async with _new_http_client() as client:
            await _login(client, student_number, plain_password)
            response = await client.get(OBIS_EXAM_GRADES_PATH)
            response.raise_for_status()
            return response.text
