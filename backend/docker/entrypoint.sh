#!/usr/bin/env sh
# Entrypoint dispatcher for the rosulo-affiliate backend container.
#
# Subcommands:
#   migrate  - run `alembic upgrade head` and exit (one-shot init job)
#   <cmd>    - exec the given command verbatim (the image default runs uvicorn)
#
# Migrations are intentionally NOT run before the app starts so that multiple
# app replicas can come up without racing on the schema. Run `migrate` once as
# a separate one-shot job / init container before scaling the app. See
# docker/docker-compose.yml for the init-container pattern.
#
# The DATABASE_URL is read by app.core.config, which alembic/env.py imports,
# so no separate alembic.ini sqlalchemy.url is needed.
set -eu

if [ "${1:-}" = "migrate" ]; then
    echo "[entrypoint] applying alembic migrations..."
    alembic upgrade head
    echo "[entrypoint] migrations complete."
    exit 0
fi

# Default: exec the provided command (image CMD runs uvicorn).
exec "$@"
