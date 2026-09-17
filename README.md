# Manashelper

Manashelper is a Telegram bot that helps students at Manas University keep track of everyday student life —
their class schedule, the cafeteria menu, and their grades — without having to dig through separate websites.
You just chat with it on Telegram like you would with a friend, tapping buttons instead of typing commands.

> Looking for how the code works instead? See [`CLAUDE.md`](CLAUDE.md) for the full architecture notes, or jump
> to [For developers](#for-developers) below.

## What the bot can do

- 📅 **Class schedule** — pick your faculty, department and course once, and the bot remembers it. From then on
  you can see your day-by-day timetable at any time, with the currently ongoing or next-up class highlighted.
- 🔔 **Schedule change alerts** — if a class gets moved, cancelled, or a new one is added, the bot notifies
  everyone tracking that course automatically (checked every hour).
- 🍉 **Cafeteria menu** — see today's, tomorrow's, or any other day's menu, complete with dish photos and
  calorie counts, and rate the food with a star rating. The bot can also ping you automatically shortly before
  lunch and dinner.
- 🎓 **Grades & attendance (OBIS)** — securely link your OBIS account once, then check your exam grades and
  lesson-attendance/skip budget straight from the chat. The bot can also notify you as soon as a new grade is
  posted or an absence is recorded, without you needing to check manually.
- ⚙️ **Notification settings** — turn any of the above notifications on or off individually, whenever you like.
- 🌐 **Multiple languages** — the bot speaks Kyrgyz, Russian, Turkish and English, and picks a language
  automatically based on your Telegram app's language (you can also switch manually at any time).

Everything happens directly in the Telegram chat — there's no separate app or website to install.

## For developers

Built with Python 3.13, [aiogram 3](https://docs.aiogram.dev/) for the Telegram bot layer, SQLAlchemy 2 (async)
+ Postgres for storage, and [Dishka](https://github.com/reagento/dishka) for dependency injection. There is no
REST API — all interaction happens through Telegram long-polling. See [`CLAUDE.md`](CLAUDE.md) for a deep dive
into the architecture, package layout, and design decisions.

### Requirements

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/)
- Docker (to run a local Postgres instance)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Quick start

1. Start Postgres:
   ```
   docker compose -f docker-compose.dev.yml up -d
   ```
2. Create a `.env` file at the repo root:
   ```
   TELEGRAM_BOT_TOKEN=<your bot token>
   DATASOURCE_HOST=localhost
   DATASOURCE_NAME=db123
   DATASOURCE_USERNAME=user123
   DATASOURCE_PASSWORD=pass123
   OBIS_ENCRYPTION_KEY=<see below>
   ```
   Generate a value for `OBIS_ENCRYPTION_KEY` (a base64-encoded 32-byte AES-256 key used to encrypt stored OBIS
   passwords at rest):
   ```
   python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
   ```
3. Install dependencies: `uv sync`
4. Compile the translation catalogs (required before the bot or the test suite can run):
   ```
   uv run pybabel compile -d src/manashelper/locales
   ```
5. Apply database migrations (this also runs automatically on every boot): `uv run alembic upgrade head`
6. Run the bot: `uv run python -m manashelper.main`

### Development

```
uv run pytest                  # tests (needs the dev Postgres running, and the translation catalogs compiled)
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy src/manashelper    # type check
```

A [`.pre-commit-config.yaml`](.pre-commit-config.yaml) is included to run all three checks automatically before
each commit — install the git hook once with `pre-commit install`.

Adding or changing a user-facing string? See the gettext catalog workflow in [`CLAUDE.md`](CLAUDE.md#commands).

### Deployment

`.github/workflows/ci-cd.yml` handles CI/CD:

- **Tests** (lint, type-check, and the test suite against a real Postgres service container) run on every push
  to every branch, on pull requests targeting `main`, and on `v*` tag pushes.
- **Build & deploy** only runs after tests pass, and only on a push to `main` or a `v*` tag: it builds and
  pushes the Docker image (`docker/Dockerfile`) to `usbtypec1/manashelper` on Docker Hub, then deploys it to the
  server over SSH via `docker compose`, pruning old, no-longer-used image versions afterwards to keep the
  server's disk usage in check.

## License

[MIT](LICENSE)
