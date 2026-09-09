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
RUN uv sync --frozen --no-dev

# ----------- Stage 2: Minimal Run -----------
FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=build --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:${PATH}"

USER appuser

ENTRYPOINT ["python", "-m", "manashelper.main"]
