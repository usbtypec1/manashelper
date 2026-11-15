# Automatic OBIS login

After a user enters their student number and password, the bot obtains a fresh OBIS login
form and recognizes its CAPTCHA using `yii-captcha-solver` 0.1.1. The existing Login button
does the same with saved credentials. Password messages retain masking/deletion behavior.
Credentials and authenticated session cookies are saved only after successful login.

The same cookie session and CSRF token bind recognition to its POST. A matching Yii hash
alone never establishes success: the response must be an authenticated same-origin page
with a logout control. HTTP 200 maintenance pages are not accepted as a successful login.

`AutoLoginObisUseCase` tries at most three challenges. It submits only a confident
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

The existing 15-minute poll still selects users with saved sessions and reads the same
stored snapshots. When a fetch detects an expired session, the poll automatically logs
in using saved credentials and retries the refresh once. A successful recovery sends
no expiry reminder. If manual input is needed or credentials fail, the existing single
reminder/login-button flow is used. Transport errors propagate to the job transaction,
preserving the previous session and data for a later scheduled poll. Cached user screens
do not perform login or remote data fetches.

Users without any saved session can enter through the Login button. The poll does not
repeatedly attempt accounts whose session has already been removed after credential
failure. Clear credentials retains its existing behavior.

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

No new database migration is required. The uncommitted labeling feature and its V34
migration were rolled back; the local development database was downgraded to V33 after
confirming that its labeling table contained zero rows. Production databases were not
accessed for that rollback.

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

The final local verification on 15 November 2026 passed 1338 tests (39 skipped),
Ruff lint/format, strict application mypy and the frozen dependency-lock check.
The Linux Docker build stage recognized the real fixture through the direct-source
adapter with networking disabled and no standalone solver package installed.
A real OBIS login also succeeded through the application use case; the temporary
database user/session were rolled back afterward, and no Telegram messages were sent.
