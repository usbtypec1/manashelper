import logging
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from manashelper.core.config import Settings
from manashelper.modules.eders.application.models import ActivityKind, EdersCourse, EdersSnapshot
from manashelper.modules.eders.errors import (
    EdersFetchError,
    EdersLoginError,
    EdersSessionExpiredError,
    EdersUnsafeUrlError,
)
from manashelper.modules.eders.infrastructure.parser import (
    parse_account_timezone,
    parse_activity_details,
    parse_course_activities,
    parse_enrolled_courses,
)
from manashelper.modules.eders.infrastructure.urls import EDERS_BASE_URL
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError
from manashelper.modules.obis.infrastructure.client import OBIS_BASE_URL
from manashelper.modules.obis.infrastructure.client import login as obis_login

COURSES_METHOD = "core_course_get_enrolled_courses_by_timeline_classification"
LOGIN_URL = f"{EDERS_BASE_URL}/login/index.php"
COURSES_URL = f"{EDERS_BASE_URL}/my/courses.php"


def new_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=OBIS_BASE_URL, follow_redirects=True, timeout=15.0)


async def _request(
    client: httpx.AsyncClient,
    url: str,
    phase: str,
    data: dict[str, str] | None = None,
) -> httpx.Response:
    for _ in range(10):
        if phase == "read" and urlsplit(url).path == "/login/index.php":
            raise EdersSessionExpiredError("Eders session expired")
        try:
            # Force English display labels without writing the user's preferences.
            request_url = url
            if phase == "read":
                request_url = str(httpx.URL(url).copy_add_param("lang", "en"))
            response = await client.request(
                "POST" if data is not None else "GET", request_url, data=data, follow_redirects=False
            )
        except httpx.HTTPError:
            # Keep request URLs and form secrets out of errors.
            raise EdersFetchError("Eders request failed") from None
        if response.is_redirect:
            location = response.headers.get("location")
            if not location or (data is not None and response.status_code in {307, 308}):
                raise EdersUnsafeUrlError("Unsupported redirect")
            url = urljoin(url, location)
            # Language may be preserved in a read-only redirect, never action params.
            if phase == "read":
                parsed = httpx.URL(url)
                if parsed.params.get_list("lang") == ["en"]:
                    url = str(parsed.copy_remove_param("lang"))
            data = None
            continue
        if not response.is_success:
            raise EdersFetchError(f"Eders returned HTTP {response.status_code}")
        if phase == "read" and BeautifulSoup(response.text, "lxml").select_one(
            "input[name=logintoken], input[name='LoginForm[username]']"
        ):
            raise EdersSessionExpiredError("Eders session expired")
        return response
    raise EdersFetchError("Too many authentication redirects")


def _sesskey(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one("input[name=logintoken], input[name='LoginForm[username]']"):
        raise EdersSessionExpiredError("Eders login failed")
    for link in soup.select("a[href]"):
        href = link.get("href")
        if isinstance(href, str) and urlsplit(urljoin(EDERS_BASE_URL, href)).netloc == "eders.manas.edu.kg":
            keys = parse_qs(urlsplit(href).query).get("sesskey", [])
            if len(keys) == 1 and re.fullmatch(r"[A-Za-z0-9]+", keys[0]):
                return keys[0]
    match = re.search(r'"sesskey"\s*:\s*"([A-Za-z0-9]+)"', html)
    if match:
        return match[1]
    raise EdersSessionExpiredError("Missing Eders session key")


class EdersClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def login(self, client: httpx.AsyncClient, student_number: str) -> str:
        password = self._settings.eders_password
        if not self._settings.eders_enabled or password is None:
            raise EdersFetchError("Eders is disabled")
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        try:
            page = await _request(client, LOGIN_URL, "login")
            form = BeautifulSoup(page.text, "lxml").select_one("form:has(input[name=username][type=text])")
            token = form.select_one("input[name=logintoken]") if form else None
            value = token.get("value") if token else None
            if not isinstance(value, str) or not value:
                raise EdersFetchError("Missing Eders login token")
            response = await _request(
                client,
                LOGIN_URL,
                "login",
                data={
                    "anchor": "",
                    "logintoken": value,
                    "username": student_number,
                    "password": password.get_secret_value(),
                },
            )
            return _sesskey(response.text)
        except (EdersFetchError, EdersUnsafeUrlError) as error:
            raise EdersLoginError(str(error)) from None

    async def login_via_obis(self, client: httpx.AsyncClient, student_number: str, plain_password: str) -> str:
        try:
            await obis_login(client, student_number, plain_password)
            response = await _request(client, f"{OBIS_BASE_URL}/site/eders", "sso")
            # Some deployments render the SSO link instead of redirecting.
            if response.url.host == urlsplit(OBIS_BASE_URL).hostname:
                for link in BeautifulSoup(response.text, "lxml").select("a[href]"):
                    href = link.get("href")
                    if isinstance(href, str) and urlsplit(href).path == "/auth/userkey/login.php":
                        response = await _request(client, urljoin(str(response.url), href), "sso")
                        break
        except (httpx.HTTPError, ObisLoginError, ObisParseError):
            raise EdersFetchError("OBIS authentication failed") from None
        return _sesskey(response.text)

    async def _courses(self, client: httpx.AsyncClient, sesskey: str) -> list[EdersCourse]:
        courses: dict[int, EdersCourse] = {}
        offset = 0
        while True:
            try:
                response = await client.post(
                    f"{EDERS_BASE_URL}/lib/ajax/service.php",
                    params={"sesskey": sesskey, "info": COURSES_METHOD},
                    json=[
                        {
                            "index": 0,
                            "methodname": COURSES_METHOD,
                            "args": {
                                "offset": offset,
                                "limit": 0,
                                "classification": "all",
                                "sort": "fullname",
                                "customfieldname": "",
                                "customfieldvalue": "",
                                "requiredfields": [
                                    "id",
                                    "fullname",
                                    "shortname",
                                    "showcoursecategory",
                                    "showshortname",
                                    "visible",
                                    "enddate",
                                ],
                            },
                        }
                    ],
                    follow_redirects=False,
                )
                if response.is_redirect:
                    raise EdersSessionExpiredError("Eders AJAX session expired")
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                raise EdersFetchError("Could not load enrolled Eders courses") from None
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                error = payload[0].get("exception", {})
                if isinstance(error, dict) and error.get("errorcode") in {"invalidsesskey", "requireloginerror"}:
                    raise EdersSessionExpiredError("Eders AJAX session expired")
            batch, next_offset = parse_enrolled_courses(payload)
            courses.update((course.id, course) for course in batch)
            if next_offset is None or next_offset < 0 or not batch:
                return list(courses.values())
            if next_offset <= offset:
                raise EdersFetchError("Invalid Eders course pagination")
            offset = next_offset

    async def fetch_snapshot(self, student_number: str, obis_password: str | None = None) -> EdersSnapshot:
        # One short-lived session per snapshot, one retry of the whole snapshot.
        # Partial results must not be treated as a successful observation.
        for attempt in range(2):
            try:
                async with new_http_client() as client:
                    if obis_password is None:
                        sesskey = await self.login(client, student_number)
                    else:
                        sesskey = await self.login_via_obis(client, student_number, obis_password)
                    profile = await _request(client, f"{EDERS_BASE_URL}/user/profile.php", "read")
                    timezone = parse_account_timezone(profile.text)
                    courses = await self._courses(client, sesskey)
                    activities = []
                    for course in courses:
                        page = await _request(client, f"{EDERS_BASE_URL}/course/view.php?id={course.id}", "read")
                        course_timezone = parse_account_timezone(page.text) or timezone
                        for activity in parse_course_activities(page.text, course, course_timezone):
                            if activity.kind in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
                                details = await _request(client, activity.url, "read")
                                activity = parse_activity_details(details.text, activity, course_timezone)
                            activities.append(activity)
                    return EdersSnapshot(tuple(activities), datetime.now(UTC), courses=tuple(courses))
            except EdersSessionExpiredError:
                if attempt:
                    raise
        raise EdersSessionExpiredError("Eders session expired")
