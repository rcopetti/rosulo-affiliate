# syntax=docker/dockerfile:1.7

# ---- Builder ---------------------------------------------------------------
# Install dependencies into a virtualenv we can copy into the runtime image.
FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# uv needs ca-certificates for any index fetches; curl is used to install uv.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /usr/local/bin/uv

WORKDIR /app

# Install the dependency group used at runtime. The lockfile is the source of
# truth, so we resolve against it rather than re-solving the project.
# --frozen keeps the build reproducible; --no-dev excludes test/lint tooling.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# ---- Runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

# libpq5 is required by asyncpg at runtime. No build tools, no compilers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtualenv from the builder.
COPY --from=builder /app/.venv /app/.venv

# Copy the application source. .dockerignore (in backend/, the build context
# root) strips out .venv, tests, caches, and .env files so they never enter
# the image.
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Non-root user for the running process.
RUN groupadd --system --gid 1001 rosulo \
    && useradd --system --uid 1001 --gid rosulo --create-home --home-dir /home/rosulo rosulo \
    && chown -R rosulo:rosulo /app
USER rosulo

EXPOSE 8000

# Healthcheck hits the unversioned /healthz endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

# Entrypoint dispatches on the first arg: `migrate` runs alembic and exits
# (one-shot init job); anything else is exec'd as the app process. The default
# CMD below starts uvicorn WITHOUT running migrations, so multiple replicas can
# start without racing on the schema. Run `migrate` once as a separate job /
# init container before scaling — see docker/docker-compose.yml.
COPY --chmod=0755 docker/entrypoint.sh /app/docker/entrypoint.sh
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
