# Automatic OBIS login

After a user enters their student number and password, the bot obtains a fresh OBIS login
form and recognizes its CAPTCHA using `yii-captcha-solver` 0.1.1. The existing Login button
does the same with saved credentials. Password messages retain masking/deletion behavior.
Credentials and authenticated session cookies are saved only after successful login.

The same cookie session and CSRF token bind recognition to its POST. A matching Yii hash
alone never establishes success: the response must be an authenticated same-origin page
with a logout control. HTTP 200 maintenance pages are not accepted as a successful login.

`AutoLoginObisUseCase` tries at most five challenges. It submits only a confident
answer returned by the recognizer; an uncertain candidate is never posted. An uncertain result
gets a fresh challenge. A definitive CAPTCHA rejection or expired form permits another
attempt with a fresh form/session. Credential errors, transport errors and unconfirmed
responses stop the scenario without repeating the POST. After CAPTCHA exhaustion the
bot shows a fresh, unsubmitted image for the existing manual flow. A missing client hash
also falls back to that flow.

CPU recognition runs through `asyncio.to_thread`, with at most two active solver calls
per application instance. The bot's asyncio loop remains available. Images and user
answers are not collected for training, and there are no labeling routes or tables.

## Session recovery

The 15-minute poll selects users with nonempty saved credentials, including existing
users who have never opened a session. The first poll creates their session automatically.
User screens continue to read persisted snapshots without logging in or fetching remotely.

`ObisAccessService` acquires the user-row lock before inspecting auth state, obtaining
cookies or starting login. It reuses saved cookies and recovers an expired session once,
retrying only the failed operation. Earlier successful refreshes and notifications are
not repeated. Concurrent requests reread the state after acquiring the same database lock.
Updated authenticated cookies are saved encrypted without changing the session creation time.

`obis_auth_states` distinguishes first login from paused automatic access. CAPTCHA
exhaustion or invalid credentials require manual login; the OBIS poll queues one localized
notice and marks it claimed in the same transaction. An enqueue failure rolls back the
claim, allowing the next poll to deliver it. Unclaimed notices remain eligible even when
Eders was the caller that encountered the auth failure.

Temporary login/transport failures preserve the saved session and set a durable retry
deadline: 15 minutes, doubling on consecutive failed refresh cycles up to six hours. Individual
successful reads or Eders SSO do not erase this history; a complete successful OBIS poll clears it.
No uncertain POST
is repeated in the same attempt series. Successful login or clearing credentials resets
the auth state. Expected manual/deferred outcomes are caught inside the request scope so
these state changes commit; unexpected errors still roll back.

Eders keeps direct Moodle login as its first choice. Its SSO fallback obtains cookies
through the same access service and requests `/site/eders`; it never submits a separate
OBIS password. An OBIS login redirect during SSO triggers the shared recovery path before
any completion mutation. Live SSO availability remains an upstream compatibility check.

## Dependency and deployment

The recognition engine and glyph bank from version 0.1.1 live directly in
`src/manashelper/modules/obis/infrastructure/yii_captcha/`. The internal library exposes
`solver.solve(image_bytes, expected_hash) -> str | None`; the asynchronous adapter in
`infrastructure/captcha.py` handles thread execution and limits concurrency. Invalid
challenges and uncertain recognition allow manual fallback. The library contains no
CLI, HTTP client, report writer or standalone package metadata. `ObisClient` owns
challenge acquisition and authenticated sessions. The search algorithm and confidence
thresholds are preserved. See the bundled `SOURCE.md` for provenance and local changes.

There is no wheel, separate package installation, workspace member, or library build
step. NumPy and Pillow are normal application dependencies in
`pyproject.toml` and `uv.lock`. The existing Docker `COPY src` includes code and model
data, and `.dockerignore` explicitly preserves the bundled Yii license. The image does
not depend on a sibling checkout or a private package index. Run `uv sync --frozen`
locally, or rebuild the normal application image. PHP, Tesseract and a GPU are not needed.

Deploy migration `V34_add_obis_auth_state.py` with the application. It adds only
`obis_auth_states`: existing encrypted credentials, sessions and snapshots are unchanged.
The migration makes no network requests; initial logins run through normal polling.
Its downgrade removes only auth state, preserving those credentials, sessions and snapshots.

## Verification

Tests in `tests/modules/obis/test_auto_login.py` exercise recognition, bounded retry,
session binding, transport/credential failure boundaries, session recovery and a real
solver → mocked HTTP form → encrypted PostgreSQL integration. Telegram tests verify
automatic success without a CAPTCHA photo and preserve the manual fallback.

Run the relevant tests with local PostgreSQL and compiled catalogs, using the environment
overrides documented in `AGENTS.md`:

```text
pytest tests/modules/obis tests/modules/users tests/modules/feedback/test_feedback_composition.py
```

The earlier local verification on 15 November 2026 passed 1338 tests (39 skipped),
Ruff lint/format, strict application mypy and the frozen dependency-lock check.
The Linux Docker build stage recognized the real fixture through the direct-source
adapter with networking disabled and no standalone solver package installed.
A real OBIS login also succeeded through the application use case; the temporary
database user/session were rolled back afterward, and no Telegram messages were sent.

After adding shared access and durable auth state on the same date, the final suite passed
1405 tests (8 skipped), including the local OBIS/Eders HTTP simulation. Ruff lint/format,
strict application mypy, the dependency-lock check and Alembic schema comparison passed.
Additional tests cover initial session creation, cross-worker locking, persisted retry
deadlines, partial-cycle backoff, cookie rotation, a one-time manual-login notice with
transactional rollback, and upgrade/downgrade preservation. The HTTP tests exercise fifth
challenge success, five-challenge exhaustion and saved-cookie SSO. No live university
account was used for these new checks; current production SSO compatibility remains unverified.
