#!/usr/bin/env sh
# Build the rosulo-affiliate frontend (Vite SPA) into dist/ for static hosting.
#
# Produces a static bundle in dist/ that can be synced to an S3 bucket and
# served via CloudFront (or any static host / CDN). The app uses same-origin
# relative API paths (VITE_API_BASE_URL stays /api/v1), so the CDN should
# route:
#   /api/*     → App Runner (backend)
#   /*         → S3 (static files, SPA fallback to /index.html)
#
# VITE_* vars are build-time — they are baked into the static bundle.
# The env file is sourced before building so Vite picks them up.
#
# Usage:
#   ./build-web.sh                          # production build (loads .env.prod)
#   ./build-web.sh --env .env               # local/sandbox build with .env
#   ./build-web.sh --dev                    # non-minified, for staging inspection
#   ./build-web.sh --clean                  # clear the Vite cache before building
#   ./build-web.sh --api-url URL            # override: talk directly to a backend URL
#                                            # (cross-origin; backend CORS must allow it)
set -eu

# --- locate the frontend directory (script lives in it) ---------------------
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# --- args -------------------------------------------------------------------
DEV=0
CLEAN=0
API_URL=""
ENV_FILE=".env.prod"
for arg in "$@"; do
    case "$arg" in
        --dev) DEV=1 ;;
        --clean|-c) CLEAN=1 ;;
        --api-url) shift_next=1 ;;
        --env) shift_next=2 ;;
        -h|--help)
            cat <<'HELP'
Usage: ./build-web.sh [--env <file>] [--dev] [--clean] [--api-url <url>]

Builds the frontend static bundle into dist/.
  --env <file>     Environment file to load (default: .env.prod)
                   Use .env.prod for production, .env for sandbox/dev.
                   The file must exist and contain VITE_API_BASE_URL.
  --dev            Non-minified build (for staging inspection)
  --clean          Clear the Vite cache before building
  --api-url <url>  Talk directly to a backend URL instead of same-origin
                   (requires CORS on the backend; otherwise leave unset and
                   use CloudFront to proxy /api/* to App Runner)

VITE_* vars are build-time — they are baked into the static bundle.
The env file is sourced before building so Vite picks them up.

Optional env vars in the file:
  VITE_API_BASE_URL   Backend API base URL (default: /api/v1, same-origin)
HELP
            exit 0 ;;
        *)
            if [ "${shift_next:-0}" = "1" ]; then
                API_URL="$arg"
                shift_next=0
            elif [ "${shift_next:-0}" = "2" ]; then
                ENV_FILE="$arg"
                shift_next=0
            else
                echo "unknown arg: $arg" >&2; exit 2
            fi ;;
    esac
done

# --- prerequisites ----------------------------------------------------------
if [ ! -d "node_modules" ]; then
    echo "==> installing dependencies (npm install)"
    npm install
fi

# --- load env file ----------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: env file '$ENV_FILE' not found." >&2
    echo "       Create it from .env.example:" >&2
    echo "         cp .env.example $ENV_FILE" >&2
    exit 1
fi

echo "==> loading env from $ENV_FILE"
# shellcheck disable=SC1090
set -a
. "$ENV_FILE"
set +a

# --- validate required vars -------------------------------------------------
# No secrets are required — the only build-time var is the API base URL, and
# the code falls back to the same-origin default when it is unset.
if [ -z "${VITE_API_BASE_URL:-}" ]; then
    echo "    VITE_API_BASE_URL not set in $ENV_FILE, defaulting to /api/v1 (same-origin)."
    export VITE_API_BASE_URL="/api/v1"
fi

# --- build flags ------------------------------------------------------------
BUILD_FLAGS=""
if [ "$DEV" -eq 1 ]; then
    BUILD_FLAGS="$BUILD_FLAGS --minify false"
fi

# --- API mode ----------------------------------------------------------------
# By default the app uses same-origin relative paths (/api/v1). The static
# host's CDN proxies /api/* to the backend. Use --api-url to talk directly to
# the backend (cross-origin, needs CORS).
if [ -n "$API_URL" ]; then
    export VITE_API_BASE_URL="$API_URL"
    echo "==> API mode: direct to $API_URL (cross-origin)"
else
    echo "==> API mode: same-origin $VITE_API_BASE_URL (CDN proxies /api/* to backend)"
fi

# --- build ------------------------------------------------------------------
echo "==> building frontend bundle"
echo "    dir:    dist/"
if [ "$DEV" -eq 1 ]; then
    echo "    mode:   development (non-minified)"
else
    echo "    mode:   production (minified)"
fi
echo "    flags:  ${BUILD_FLAGS:- none}"
echo

if [ "$CLEAN" -eq 1 ]; then
    echo "==> clearing Vite cache"
    rm -rf node_modules/.vite
fi

rm -rf dist/
npm run build -- $BUILD_FLAGS

# --- summary ----------------------------------------------------------------
echo
echo "==> done"
echo "    output: $(pwd)/dist/"
echo
echo "    deploy to S3:"
echo "      aws s3 sync dist/ s3://affiliate.rosulo.com/ --delete"
echo
echo "    CloudFront (after S3 sync):"
echo "      create an invalidation for '/*'"
echo
echo "    CloudFront origins:"
echo "      /api/*  → App Runner backend (bhdwp9gmgt.us-west-2.awsapprunner.com)"
echo "      /*      → S3 bucket, with SPA fallback to /index.html"
