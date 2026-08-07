# syntax=docker/dockerfile:1.9

# Build context is the REPOSITORY ROOT (see docker-compose.yml build.context),
# because backend/pyproject.toml declares readme = "../README.md" and hatchling
# reads it while building the project wheel.

# Pinned base. Project requires Python >=3.11,<3.13; 3.12 is the runtime target.
# Pin to digest in production hardening (M0 discipline: no floating `latest`).
FROM python:3.12.7-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# uv is copied from its own pinned image rather than curl|sh.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

# README.md lives one level above the project dir to satisfy the pyproject
# `readme = "../README.md"` reference at wheel-build time.
WORKDIR /srv
COPY README.md ./README.md

WORKDIR /srv/backend

# No apt packages: healthchecks use Python stdlib (see docker-compose.yml).
# Keeps the image smaller and avoids flaky deb.debian.org during build.

# Resolve dependencies from the lockfile first for cache-friendly rebuilds.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Application source.
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN cp docker/entrypoint.sh /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

# Non-root runtime.
RUN useradd --create-home --uid 10001 flywiki \
    && chown -R flywiki:flywiki /srv
USER flywiki

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["api"]
