# syntax=docker/dockerfile:1.9

# Build context is the REPOSITORY ROOT (see docker-compose.yml).
FROM node:22.14.0-slim AS build

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
# Avoid corepack here: older Node images ship a keyring that rejects current
# pnpm signatures. Install the workspace-pinned pnpm via npm instead.
RUN npm install -g pnpm@11.13.1

WORKDIR /repo

# Workspace manifests first for cache-friendly dependency installs.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json web/package.json
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY web/ web/
RUN pnpm --dir web build

# --- runtime -------------------------------------------------------------
FROM nginx:1.27.3-alpine AS runtime

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/web/dist /usr/share/nginx/html

EXPOSE 80
