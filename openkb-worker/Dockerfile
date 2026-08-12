# syntax=docker/dockerfile:1.9@sha256:fe40cf4e92cd0c467be2cfc30657a680ae2398318afd50b0c80585784c604f28

FROM python:3.12.7-slim@sha256:60d9996b6a8a3689d36db740b49f4327be3be09a21122bd02fb8895abb38b50d

ARG OPENKB_VERSION=0.4.5
ARG OPENKB_COMMIT=ac118407eacd995618256f121c21a2d275672f47

LABEL org.opencontainers.image.source="https://github.com/FlyAIBox/fly-wiki" \
      io.flywiki.openkb.version="${OPENKB_VERSION}" \
      io.flywiki.openkb.commit="${OPENKB_COMMIT}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    OPENKB_ROOT=/data/openkb \
    OPENKB_VERSION=${OPENKB_VERSION} \
    OPENKB_COMMIT=${OPENKB_COMMIT}

WORKDIR /srv/openkb-worker

COPY --from=ghcr.io/astral-sh/uv:0.5.11@sha256:0ac957607303916420297a4c9c213bb33fbd3c888f9cd7f4f7273596ebf42b85 /uv /usr/local/bin/uv
COPY openkb-worker/pyproject.toml openkb-worker/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY openkb-worker/app.py ./app.py

RUN useradd --create-home --uid 10002 openkb \
    && mkdir -p /data/openkb \
    && chown -R openkb:openkb /data/openkb /srv/openkb-worker
USER openkb

EXPOSE 8100
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
