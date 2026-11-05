# ----------- Stage 1: Build -----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first for layer caching, before copying the rest of the source.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY docs/commands ./docs/commands

RUN uv sync --frozen --no-dev

# Compile gettext catalogs (locales/**/LC_MESSAGES/*.po -> *.mo) — .mo files are gitignored
# build artifacts, so this must happen before the image can serve translated strings.
RUN uv run pybabel compile -d src/manashelper/locales
COPY frontend/scripts ./frontend/scripts
RUN uv run python frontend/scripts/export_messages.py

# The frontend is compiled once; Node does not run in the application container.
FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
COPY --from=build /app/frontend/src/messages.json ./src/messages.json
RUN npm run build

# ----------- Stage 2: Minimal Run -----------
FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=build --chown=appuser:appuser /app /app
COPY --from=frontend --chown=appuser:appuser /src/manashelper/platform/web/static /app/src/manashelper/platform/web/static

# Pre-create the log directory owned by appuser: it doesn't exist anywhere else in the image, so
# without this, mounting the `app_logs` volume over it (see docker-compose.prod.yaml) would make Docker
# create the mount point as root, and appuser (below) couldn't write into it.
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

ENV PATH="/app/.venv/bin:${PATH}"

USER appuser
EXPOSE 8080

ENTRYPOINT ["python", "-m", "manashelper.main"]
