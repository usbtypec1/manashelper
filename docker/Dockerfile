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
RUN uv run --frozen --no-dev pybabel compile -d src/manashelper/locales

COPY scripts/export_ui_flow_editor_copy.py ./scripts/export_ui_flow_editor_copy.py
RUN uv run --frozen --no-dev python scripts/export_ui_flow_editor_copy.py

# Build the editor using Bun for both package management and JavaScript execution.
FROM oven/bun:1.4.3 AS admin-build
WORKDIR /workspace/src/admin-ui
COPY src/admin-ui/package.json src/admin-ui/bun.lock ./
RUN bun install --frozen-lockfile
COPY src/admin-ui ./
COPY features/ui_flows/openapi.json /workspace/features/ui_flows/openapi.json
COPY --from=build /app/src/admin-ui/src/generated/messages.json ./src/generated/messages.json
RUN bun run build

# ----------- Stage 2: Minimal Run -----------
FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=build --chown=appuser:appuser /app /app
COPY --from=admin-build --chown=appuser:appuser /workspace/src/admin-ui/dist /app/src/admin-ui/dist

# Pre-create the log directory owned by appuser: it doesn't exist anywhere else in the image, so
# without this, mounting the `app_logs` volume over it (see docker-compose.prod.yaml) would make Docker
# create the mount point as root, and appuser (below) couldn't write into it.
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

ENV PATH="/app/.venv/bin:${PATH}"

USER appuser

ENTRYPOINT ["python", "-m", "manashelper.main"]
