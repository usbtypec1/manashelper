# Manashelper

Telegram bot for Manas University students — Python 3.13, aiogram 3, SQLAlchemy 2 (async), Dishka.

## Functionality overview

This is a from-scratch Python rewrite of a former Java/Spring Boot implementation. Currently implemented (see
[`CLAUDE.md`](CLAUDE.md) for architecture details and the full roadmap of what's not yet ported):

- **Timetable browsing**: browse faculties → departments → courses via inline keyboards.
- **Course tracking**: tap a course to toggle tracking it; tracked courses are marked with ✅.

There is no REST API — all interaction happens through Telegram long-polling.

## Quick start

Requires Python 3.13+, [`uv`](https://docs.astral.sh/uv/), and Docker (for the dev Postgres instance).

1. Start Postgres: `docker compose -f docker-compose.dev.yml up -d`
2. Create a `.env` file at the repo root:
   ```
   TELEGRAM_BOT_TOKEN=<your bot token>
   DATASOURCE_HOST=localhost
   DATASOURCE_NAME=db123
   DATASOURCE_USERNAME=user123
   DATASOURCE_PASSWORD=pass123
   ```
3. Install dependencies: `uv sync`
4. Apply migrations (this also runs automatically on every boot): `uv run alembic upgrade head`
5. Run the bot: `uv run python -m manashelper.main`

## Development

```
uv run pytest                  # tests (needs the dev Postgres running)
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy src/manashelper    # type check
```

## Deployment

Pushing a `v*` git tag runs `.github/workflows/ci-cd.yml`: lint + type-check + tests against a Postgres service
container, then — only if that passes — a Docker build/push to `usbtypec1/manashelper` on Docker Hub, followed by
a remote deploy over SSH via `docker compose`.
