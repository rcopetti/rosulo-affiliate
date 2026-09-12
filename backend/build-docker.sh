#!/usr/bin/env sh
# Build the rosulo-affiliate backend Docker image with a versioned tag.
#
# Tag format: <major.minor>-<git_short_hash>  (e.g. 0.1-618f0fb)
#   - <major.minor> comes from `version` in backend/pyproject.toml
#   - <git_short_hash> is `git rev-parse --short HEAD`
#
# The image is also tagged `latest` locally for convenience. This script does
# NOT push — run `docker push` manually once the image is verified.
#
# Builds for linux/amd64 explicitly so the image runs on AWS Fargate and App
# Runner (both default to amd64). Building on Apple Silicon without --platform
# produces an arm64 image that fails with "exec format error" on Fargate.
#
# Refuses to build if the working tree is dirty, so every image traces back to
# a specific, reproducible commit.
#
# Usage:
#   ./build-docker.sh                  # build with current version + hash
#   ./build-docker.sh --force          # bypass the dirty-tree check (dangerous)
set -eu

# --- locate the backend directory (script lives in it) ----------------------
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# --- args -------------------------------------------------------------------
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
        -h|--help)
            cat <<'HELP'
Usage: ./build-docker.sh [--force]

Builds the backend Docker image tagged <major.minor>-<short_hash> and latest.
--force bypasses the dirty-working-tree guard. Do not use on shared branches.
HELP
            exit 0 ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

# --- must be inside a git repo ----------------------------------------------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "error: $SCRIPT_DIR is not inside a git repository" >&2
    exit 1
fi

# --- dirty-tree guard -------------------------------------------------------
# `git status --porcelain` lists tracked modifications, staged changes, AND
# untracked files — any of which would make the image non-reproducible from
# the commit hash baked into the tag. --force bypasses this guard.
if [ "$FORCE" -eq 0 ] && [ -n "$(git status --porcelain)" ]; then
    echo "error: working tree has uncommitted or untracked changes." >&2
    echo "       commit or stash first, or re-run with --force to build anyway." >&2
    git status --short >&2
    exit 1
fi

# --- version from pyproject.toml (major.minor) ------------------------------
VERSION_LINE=$(grep -m1 '^version' pyproject.toml)
if [ -z "$VERSION_LINE" ]; then
    echo "error: could not find 'version' in pyproject.toml" >&2
    exit 1
fi
# Extract the quoted value, e.g. version = "0.1.0" -> 0.1.0
FULL_VERSION=$(printf '%s\n' "$VERSION_LINE" | sed -n 's/.*"\([^"]*\)".*/\1/p')
if [ -z "$FULL_VERSION" ]; then
    echo "error: could not parse version from: $VERSION_LINE" >&2
    exit 1
fi
# major.minor only (drop patch and any pre-release suffix)
VERSION_MINOR=$(printf '%s\n' "$FULL_VERSION" | cut -d. -f1,2)

# --- git short hash ---------------------------------------------------------
GIT_HASH=$(git rev-parse --short HEAD)

# --- assemble tag -----------------------------------------------------------
ECR_REGISTRY="239714841352.dkr.ecr.us-west-2.amazonaws.com"
IMAGE_NAME="rosulo/rosulo-affiliate-backend"
TAG="${VERSION_MINOR}-${GIT_HASH}"
IMAGE="${ECR_REGISTRY}/${IMAGE_NAME}:${TAG}"
IMAGE_LATEST="${ECR_REGISTRY}/${IMAGE_NAME}:latest"

echo "==> building"
echo "    version (full):   $FULL_VERSION"
echo "    version (minor):  $VERSION_MINOR"
echo "    git hash:         $GIT_HASH"
echo "    image:            $IMAGE"
echo "    latest alias:     $IMAGE_LATEST"
echo

# --- build + tag ------------------------------------------------------------
# Build for linux/amd64 so the image runs on AWS Fargate and App Runner (both
# default to amd64). On Apple Silicon this cross-compiles via QEMU (buildx).
# Build the versioned tag directly, then re-tag as latest from the same image
# (no second build).
docker buildx build --platform linux/amd64 -f docker/Dockerfile -t "$IMAGE" --load .
docker tag "$IMAGE" "$IMAGE_LATEST"

echo
echo "==> done"
echo "    $IMAGE"
echo "    $IMAGE_LATEST"
echo
echo "    verify, then push with:"
echo "      docker push $IMAGE"
echo "      docker push $IMAGE_LATEST"
