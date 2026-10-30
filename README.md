# Manashelper

Manashelper is a Telegram bot that helps students at Manas University keep track of everyday student life —
their class schedule, the cafeteria menu, and their grades — without having to dig through separate websites.
You just chat with it on Telegram like you would with a friend, tapping buttons instead of typing commands.

> Looking for how the code works instead? See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the current architecture, or jump
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
- 📚 **Eders** — main-menu buttons open deadlines, course materials and the study week. Notification settings
  configure reminders one day and two hours before a deadline, activity openings and deadline changes. The study week combines
  the next seven days of classes, activity dates and newly discovered materials. Eders is checked every 15 minutes
  using the saved student number and a shared password from `MANASHELPER_EDERS_PASSWORD`. `/materials text` searches course names,
  sections and titles. New and renamed materials or changed text blocks are grouped by course in notifications.
  Folders, links, files, forums and text blocks are supported. Initial syncs are silent for materials.
  Unverified timezones and conflicting dates are shown explicitly. Without `MANASHELPER_EDERS_PASSWORD`, Eders buttons,
  handlers, notification settings and polling are disabled, including the study week.
- 🌐 **Multiple languages** — the bot speaks Kyrgyz, Russian, Turkish, English and simplified Chinese, and picks a language
  automatically based on your Telegram app's language (you can also switch manually at any time).

Everything happens directly in the Telegram chat — there's no separate app or website to install.

## For developers

Built with Python 3.13, [aiogram 3](https://docs.aiogram.dev/) for the Telegram bot layer, SQLAlchemy 2 (async)
+ Postgres for storage, and [Dishka](https://github.com/reagento/dishka) for dependency injection. There is no
REST API — all interaction happens through Telegram long-polling. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
for the current package layout, [`docs/MIGRATION.md`](docs/MIGRATION.md) for the completed refactor and
[`docs/BACKLOG.md`](docs/BACKLOG.md) for deferred fixes and verification.

### Requirements

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/)
- Docker with the Compose plugin (to run a local PostgreSQL 18 instance)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Quick start

Existing PostgreSQL 17 installations must follow [the upgrade procedure](docs/postgres-18-upgrade.md)
before starting the new Compose configuration. The old volume is preserved.

Run these commands from the repository root.

All project environment variables use the `MANASHELPER_` prefix, including GitHub Actions secrets and variables.
When upgrading, rename keys in local/production `.env` files and GitHub settings in the same release; old
unprefixed names are ignored. For rollback, restore the previous configuration with the previous application
version. PostgreSQL container variables such as `POSTGRES_USER` and platform variables such as `GITHUB_SHA`
keep their standard names.

1. Copy [`.env.example`](.env.example) to `.env`:
   ```sh
   cp .env.example .env
   ```
   Set `MANASHELPER_TELEGRAM_BOT_TOKEN`, `MANASHELPER_OBIS_ENCRYPTION_KEY`, `MANASHELPER_ADVERTISEMENT_CHANNEL_ID`, `MANASHELPER_ADVERTISEMENT_CHANNEL_LINK`,
   `MANASHELPER_MODERATION_CHAT_ID` and `MANASHELPER_ADMIN_CHAT_ID`. The bot must have permission to post to the advertisement channel
   and send messages to the moderation/admin chats. Keep `MANASHELPER_DATASOURCE_HOST=localhost` for a local Python process.
   The example database credentials match the development Compose defaults; change them together if needed.
   Generate a value for `MANASHELPER_OBIS_ENCRYPTION_KEY` (a base64-encoded 32-byte AES-256 key used to encrypt stored OBIS
   passwords at rest):
   ```
   uv run python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
   ```
   Omit `MANASHELPER_EDERS_PASSWORD` or leave it empty to disable Eders. To enable it, set the shared password and restart
   the bot. Eders obtains a fresh `logintoken` from Moodle's login form, posts the saved student number and
   shared password, and accepts login only after reaching `/my/courses.php`. It does not use the OBIS password.
   Student numbers are still saved through the existing OBIS account-linking flow.
   The first sync after switching authentication establishes a silent baseline for the student number;
   changing the OBIS password no longer resets that baseline. Existing notification preferences are preserved.
2. Start Postgres:
   ```sh
   docker compose --project-directory . --env-file .env -f docker/docker-compose.dev.yaml up -d --wait db
   ```
3. Install dependencies: `uv sync`
4. Compile the translation catalogs (required before the bot or the test suite can run):
   ```
   uv run pybabel compile -d src/manashelper/locales
   ```
5. Apply database migrations (this also runs automatically on every boot): `uv run alembic upgrade head`
6. Run the bot: `uv run python -m manashelper.main`

`--project-directory .` keeps the Compose project name based on the repository directory after moving
the Compose files into `docker/`. `--env-file .env` explicitly loads the root configuration.

### Development

```
uv run pytest                  # tests (needs the dev Postgres running, and the translation catalogs compiled)
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy src/manashelper    # type check
```

A [`.pre-commit-config.yaml`](.pre-commit-config.yaml) is included to run all three checks automatically before
each commit — install the git hook once with `pre-commit install`.

Adding or changing a user-facing string? See the gettext catalog workflow in
[`AGENTS.md`](AGENTS.md#localization-and-telegram-text).

### Deployment

Compose files live in [`docker/`](docker/):

- [`docker-compose.dev.yaml`](docker/docker-compose.dev.yaml) starts only the local PostgreSQL 18 database,
  exposed on port `5432`.
- [`docker-compose.prod.yaml`](docker/docker-compose.prod.yaml) starts PostgreSQL 18 and the published
  `usbtypec1/manashelper:${MANASHELPER_VERSION}` image. The database is exposed only on the server's loopback interface.
  `MANASHELPER_DB_HOST_PORT` sets the published port (default `5432`); PostgreSQL uses port `5432` inside Docker.
  The app waits for the database healthcheck. Database data and logs use persistent volumes.

For a manual production launch from the repository root, create `.env` from `.env.example`, fill in the real
values, set `MANASHELPER_DATASOURCE_HOST=db`, and set `MANASHELPER_VERSION` to the desired image tag (for example, `1.2.3` for release
`v1.2.3`). Existing PostgreSQL 17 installations must first complete the
[upgrade procedure](docs/postgres-18-upgrade.md).

```sh
docker compose --project-directory . --env-file .env -f docker/docker-compose.prod.yaml config --quiet
docker compose --project-directory . --env-file .env -f docker/docker-compose.prod.yaml pull
docker compose --project-directory . --env-file .env -f docker/docker-compose.prod.yaml up -d --wait --remove-orphans
```

[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) handles CI/CD:

- **Tests** (lint, format, type checks, migrations and tests against a real Postgres service) run on pull requests
  targeting `main`, pushes to `main` (including merges), and `v*` tag pushes.
- **Build & deploy** runs after tests pass on a push to `main` or a `v*` tag. It builds `docker/Dockerfile` and
  pushes the versioned image and `latest` to Docker Hub. Images from `main` use a `sha-<commit>` tag;
  release tags use the version without the `v` prefix. Pushes to other branches do not trigger this workflow.
- **Deployment files**: the runner copies `docker/docker-compose.prod.yaml` as `docker-compose.yaml` and writes
  the `MANASHELPER_ENV_FILE` secret to `.env`. Both files are copied to `/opt/manashelper/` on the server. The secret must
  contain the production configuration with `MANASHELPER_DATASOURCE_HOST=db`; CI exports `MANASHELPER_VERSION` from the build job.
- **Server update** validates `docker-compose.yaml`, pulls the image, checks for an unmigrated PostgreSQL 17
  installation, starts containers with `docker compose -f docker-compose.yaml up -d --wait --remove-orphans`,
  and removes dangling images.

Configure GitHub Actions secrets `MANASHELPER_DOCKERHUB_TOKEN`, `MANASHELPER_ENV_FILE`, `MANASHELPER_EC2_HOST`, `MANASHELPER_EC2_USER`, `MANASHELPER_EC2_SSH_KEY` and
`MANASHELPER_EC2_PORT`. The SSH user needs Docker access and write permission to `/opt/manashelper`; the server needs
Docker with the Compose plugin. The deployed `.env` has permissions `600`.

The final `notify` job waits for Test, Build and Deploy, including failed or skipped jobs, then sends one
Telegram message with their results: 🟢 success, 🔴 failure, ⚪ skipped, 🟡 cancelled. Set the bot token in the
GitHub Actions secret `MANASHELPER_TELEGRAM_BOT_TOKEN` and the destination chat ID in the Actions variable `MANASHELPER_TELEGRAM_CHAT_ID`.
The bot must be able to send messages to that chat. If either setting is unavailable (for example, secrets on
a fork pull request), the notification is skipped with a workflow warning. Delivery errors fail the notification
job. The message uses Telegram's [`sendMessage`](https://core.telegram.org/bots/api#sendmessage) method.

## License

[MIT](LICENSE)
