import logging
from datetime import UTC, datetime
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from manashelper.scraping.eders_parser import (
    EdersGradesUnavailableError,
    parse_account_timezone,
    parse_activity_details,
    parse_course_activities,
    parse_course_grades,
    parse_courses,
)
from manashelper.scraping.eders_urls import EDERS_BASE_URL, EdersUnsafeUrlError, safe_eders_url
from manashelper.scraping.obis_client import OBIS_ATTENDANCE_PATH, OBIS_BASE_URL, OBIS_LOGIN_PATH, ObisLoginError
from manashelper.scraping.obis_parser import parse_login_page_csrf_token
from manashelper.services.eders_models import ActivityKind, EdersSnapshot

OVERVIEW_URL = f"{EDERS_BASE_URL}/grade/report/overview/index.php"


class EdersFetchError(Exception):
    pass


class EdersSessionExpiredError(EdersFetchError):
    pass


class EdersPermissionError(EdersFetchError):
    pass


def _new_http_client() -> httpx.AsyncClient:
    # Redirects are checked before following; the SSO key lives only in this client.
    # httpx logs full URLs at INFO, and httpcore can log request headers at DEBUG.
    # Neither library may log the temporary authentication session.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return httpx.AsyncClient(follow_redirects=False, timeout=15.0)


def _validate_url(url: str, phase: str) -> None:
    parts = urlsplit(url)
    params = parse_qs(parts.query, keep_blank_values=True)
    if parts.scheme != "https" or parts.fragment:
        raise EdersUnsafeUrlError("Unsupported authentication URL")
    if parts.netloc == urlsplit(OBIS_BASE_URL).netloc:
        if phase == "read" and parts.path == OBIS_LOGIN_PATH:
            raise EdersSessionExpiredError("OBIS session expired")
        if phase != "read" and parts.path in {"/", "/site/index", "/site/login", "/site/eders"} and not params:
            return
        # OBIS can finish a successful login on the student's current courses page.
        if phase == "login" and parts.path == OBIS_ATTENDANCE_PATH and not params:
            return
    elif parts.netloc == urlsplit(EDERS_BASE_URL).netloc:
        if parts.path in {"/login/index.php", "/auth/userkey/login.php"} and phase == "read":
            raise EdersSessionExpiredError("Eders session expired")
        if phase == "sso":
            if (
                parts.path == "/auth/userkey/login.php"
                and set(params) == {"key"}
                and len(params["key"]) == 1
                and params["key"][0]
            ):
                return
            if parts.path in {"", "/", "/my/", "/my/index.php", "/my/courses.php"} and not params:
                return
        if parts.path == "/grade/report/overview/index.php" and not params:
            return
        if phase == "read" and parts.path == "/user/profile.php" and not params:
            return
        if phase == "read":
            safe_eders_url(
                url,
                {
                    "/course/view.php",
                    "/mod/assign/view.php",
                    "/mod/quiz/view.php",
                    "/grade/report/user/index.php",
                    "/course/user.php",
                },
            )
            return
    raise EdersUnsafeUrlError("Unsupported authentication or read-only URL")


async def _request(
    client: httpx.AsyncClient,
    url: str,
    phase: str,
    data: dict[str, str] | None = None,
) -> httpx.Response:
    for _ in range(10):
        _validate_url(url, phase)
        if data is not None and url != f"{OBIS_BASE_URL}{OBIS_LOGIN_PATH}":
            raise EdersUnsafeUrlError("POST is restricted to OBIS login")
        try:
            # Force English display labels without writing the user's preferences.
            request_url = url
            if phase == "read":
                request_url = str(httpx.URL(url).copy_add_param("lang", "en"))
            response = await client.request("POST" if data is not None else "GET", request_url, data=data)
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
            if response.status_code == 403:
                raise EdersPermissionError("Eders access denied")
            raise EdersFetchError(f"Eders returned HTTP {response.status_code}")
        if phase == "read" and BeautifulSoup(response.text, "lxml").select_one(
            "input[name=logintoken], input[name='LoginForm[username]']"
        ):
            raise EdersSessionExpiredError("Eders session expired")
        return response
    raise EdersFetchError("Too many authentication redirects")


async def _authenticate(client: httpx.AsyncClient, student_number: str, plain_password: str) -> None:
    login_url = f"{OBIS_BASE_URL}{OBIS_LOGIN_PATH}"
    page = await _request(client, login_url, "login")
    token = parse_login_page_csrf_token(page.text)
    response = await _request(
        client,
        login_url,
        "login",
        {"LoginForm[username]": student_number, "LoginForm[password_hash]": plain_password, "_csrf": token},
    )
    if response.url.path.rstrip("/") == OBIS_LOGIN_PATH:
        raise ObisLoginError("Invalid OBIS credentials")
    response = await _request(client, f"{OBIS_BASE_URL}/site/eders", "sso")
    if response.url.host == urlsplit(OBIS_BASE_URL).hostname:
        # Some OBIS deployments render the SSO link instead of redirecting to it.
        for link in BeautifulSoup(response.text, "lxml").select("a[href]"):
            href = link.get("href")
            if not isinstance(href, str):
                continue
            url = urljoin(str(response.url), href)
            if urlsplit(url).path == "/auth/userkey/login.php":
                await _request(client, url, "sso")
                return
        raise EdersFetchError("Missing OBIS to eders transition")


class EdersClient:
    async def fetch_snapshot(self, student_number: str, plain_password: str) -> EdersSnapshot:
        # One short-lived session per snapshot, one retry of the whole snapshot.
        # Partial results must not be treated as a successful observation.
        for attempt in range(2):
            try:
                async with _new_http_client() as client:
                    await _authenticate(client, student_number, plain_password)
                    profile = await _request(client, f"{EDERS_BASE_URL}/user/profile.php", "read")
                    timezone = parse_account_timezone(profile.text)
                    overview = await _request(client, OVERVIEW_URL, "read")
                    courses = parse_courses(overview.text)
                    activities = []
                    grades = []
                    unavailable_grade_courses = []
                    for course in courses:
                        page = await _request(client, f"{EDERS_BASE_URL}/course/view.php?id={course.id}", "read")
                        for activity in parse_course_activities(page.text, course, timezone):
                            if activity.kind in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
                                details = await _request(client, activity.url, "read")
                                activity = parse_activity_details(details.text, activity, timezone)
                            activities.append(activity)
                        try:
                            report = await _request(
                                client, f"{EDERS_BASE_URL}/grade/report/user/index.php?id={course.id}", "read"
                            )
                            grades.extend(parse_course_grades(report.text, course))
                        except (EdersGradesUnavailableError, EdersPermissionError):
                            unavailable_grade_courses.append(course.id)
                    return EdersSnapshot(
                        tuple(activities),
                        datetime.now(UTC),
                        tuple(grades),
                        grades_observed=True,
                        catalog_observed=True,
                        courses=tuple(courses),
                        unavailable_grade_courses=tuple(unavailable_grade_courses),
                    )
            except EdersSessionExpiredError:
                if attempt:
                    raise
        raise EdersSessionExpiredError("Eders session expired")
