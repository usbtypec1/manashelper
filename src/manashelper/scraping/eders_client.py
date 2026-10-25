import logging
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from manashelper.scraping.eders_parser import (
    parse_account_timezone,
    parse_activity_details,
    parse_course_activities,
    parse_enrolled_courses,
)
from manashelper.scraping.eders_urls import EDERS_BASE_URL, EdersUnsafeUrlError, safe_eders_url
from manashelper.scraping.obis_client import OBIS_BASE_URL, OBIS_LOGIN_PATH, _login, _new_http_client
from manashelper.services.eders_models import ActivityKind, EdersCourse, EdersSnapshot

COURSES_METHOD = "core_course_get_enrolled_courses_by_timeline_classification"


class EdersFetchError(Exception):
    pass


class EdersSessionExpiredError(EdersFetchError):
    pass


def _validate_request_url(url: str, phase: str) -> None:
    parsed = urlsplit(url)
    if parsed.fragment:
        raise EdersUnsafeUrlError("Unsupported eders URL")
    if phase == "sso":
        if url in {f"{OBIS_BASE_URL}/site/eders", f"{OBIS_BASE_URL}{OBIS_LOGIN_PATH}"}:
            return
        if parsed.scheme == "https" and parsed.netloc == "eders.manas.edu.kg":
            if parsed.path in {"/", "/my/", "/my/index.php"} and not parsed.query:
                return
            params = parse_qs(parsed.query, keep_blank_values=True)
            if (
                parsed.path == "/auth/userkey/login.php"
                and set(params) == {"key"}
                and len(params["key"]) == 1
                and params["key"][0]
            ):
                return
        raise EdersUnsafeUrlError("Unsupported authentication URL")
    if phase == "read":
        if url == f"{EDERS_BASE_URL}/user/profile.php":
            return
        if parsed.scheme == "https" and parsed.netloc == "eders.manas.edu.kg" and parsed.path == "/login/index.php":
            raise EdersSessionExpiredError("Eders session expired")
        safe_eders_url(url, {"/course/view.php", "/mod/assign/view.php", "/mod/quiz/view.php"})
        return
    raise EdersUnsafeUrlError("Unsupported request phase")


async def _request(
    client: httpx.AsyncClient,
    url: str,
    phase: str,
    data: dict[str, str] | None = None,
) -> httpx.Response:
    for _ in range(10):
        _validate_request_url(url, phase)
        if data is not None and url != f"{OBIS_BASE_URL}{OBIS_LOGIN_PATH}":
            raise EdersUnsafeUrlError("POST is restricted to OBIS login")
        try:
            # Force English display labels without writing the user's preferences.
            request_url = url
            if phase == "read":
                request_url = str(httpx.URL(url).copy_add_param("lang", "en"))
            response = await client.request(
                "POST" if data is not None else "GET", request_url, data=data, follow_redirects=False
            )
        except httpx.HTTPError:
            # httpx exceptions include the request URL, which can contain an SSO key.
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
    async def login(self, client: httpx.AsyncClient, student_number: str, plain_password: str) -> str:
        # Same cookie jar and OBIS login flow as the export script.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        try:
            await _login(client, student_number, plain_password)
            response = await _request(client, f"{OBIS_BASE_URL}/site/eders", "sso")
            # Some deployments render the SSO link rather than redirecting.
            if response.url.host == urlsplit(OBIS_BASE_URL).hostname:
                for link in BeautifulSoup(response.text, "lxml").select("a[href]"):
                    href = link.get("href")
                    if isinstance(href, str) and urlsplit(href).path == "/auth/userkey/login.php":
                        response = await _request(client, urljoin(str(response.url), href), "sso")
                        break
        except httpx.HTTPError:
            raise EdersFetchError("OBIS authentication request failed") from None
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

    async def fetch_snapshot(self, student_number: str, plain_password: str) -> EdersSnapshot:
        # One short-lived session per snapshot, one retry of the whole snapshot.
        # Partial results must not be treated as a successful observation.
        for attempt in range(2):
            try:
                async with _new_http_client() as client:
                    sesskey = await self.login(client, student_number, plain_password)
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
