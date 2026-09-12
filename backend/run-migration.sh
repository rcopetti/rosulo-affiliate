#!/usr/bin/env sh
# Run the rosulo-affiliate backend database migration as a one-shot AWS Fargate task.
#
# Registers a new revision of the `affiliates-db-migration` task definition with
# the given image tag, runs it on Fargate, and waits for it to finish. The task
# definition wires DATABASE_URL from SSM Parameter Store
# (/rosulo/affiliate-backend/DATABASE_URL), so no secrets are passed on the
# command line. The container runs the image's `migrate` entrypoint, which
# executes `alembic upgrade head` and exits.
#
# Usage:
#   ./run-migration.sh <tag>            # e.g. ./run-migration.sh 0.1-3b8ab83
#   ./run-migration.sh <tag> --no-wait  # register + run, don't wait for completion
#   ./run-migration.sh --latest         # use the :latest tag
#
# Exit codes:
#   0 - task ran and the container exited 0
#   1 - usage error / AWS CLI failure
#   2 - task ran but the container exited non-zero (migration failed)
set -eu

# --- config (edit if your infra changes) ------------------------------------
CLUSTER="allbum-cluster-serverless"
TASK_DEF_FAMILY="affiliates-db-migration"
SUBNETS="subnet-091d7350c16609a01"
SECURITY_GROUPS="sg-034e1f956f9b3a4b9"
ECR_REGISTRY="239714841352.dkr.ecr.us-west-2.amazonaws.com"
IMAGE_NAME="rosulo/rosulo-affiliate-backend"
AWS_REGION="us-west-2"

# --- args -------------------------------------------------------------------
TAG=""
WAIT=1

show_usage() {
    cat <<'USAGE'
Usage: ./run-migration.sh <tag> [--no-wait]
       ./run-migration.sh --latest [--no-wait]

  <tag>       Image tag to run migrations with (e.g. 0.1-3b8ab83)
  --latest    Use the :latest tag
  --no-wait   Register + run the task, but don't block until it finishes
USAGE
}

for arg in "$@"; do
    case "$arg" in
        --no-wait) WAIT=0 ;;
        --latest) TAG="latest" ;;
        -h|--help) show_usage; exit 0 ;;
        -*) echo "unknown option: $arg" >&2; show_usage >&2; exit 1 ;;
        *) TAG="$arg" ;;
    esac
done

if [ -z "$TAG" ]; then
    echo "error: image tag is required" >&2
    show_usage >&2
    exit 1
fi

IMAGE="${ECR_REGISTRY}/${IMAGE_NAME}:${TAG}"

# --- prerequisites ----------------------------------------------------------
if ! command -v aws >/dev/null 2>&1; then
    echo "error: aws CLI is not installed" >&2
    exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "error: jq is not installed (brew install jq)" >&2
    exit 1
fi

export AWS_REGION="$AWS_REGION"

# --- fetch the current task definition --------------------------------------
echo "==> fetching current task definition: $TASK_DEF_FAMILY"
CURRENT=$(aws ecs describe-task-definition \
    --task-definition "$TASK_DEF_FAMILY" \
    --query 'taskDefinition' \
    --output json) || {
    echo "error: could not describe task definition '$TASK_DEF_FAMILY'" >&2
    exit 1
}

# --- register a new revision with the updated image -------------------------
# Strip read-only fields (revision, status, registeredAt, registeredBy,
# compatibilities) that register-task-definition rejects, then swap the image.
echo "==> registering new revision with image: $IMAGE"
NEW_DEF=$(printf '%s' "$CURRENT" | jq \
    --arg image "$IMAGE" \
    '{
        family: .family,
        taskRoleArn: .taskRoleArn,
        executionRoleArn: .executionRoleArn,
        networkMode: .networkMode,
        containerDefinitions: (.containerDefinitions | map(.image = $image)),
        volumes: .volumes,
        placementConstraints: .placementConstraints,
        requiresCompatibilities: .requiresCompatibilities,
        cpu: .cpu,
        memory: .memory,
        runtimePlatform: .runtimePlatform
    } | del(.[] | nulls)')

REGISTERED=$(aws ecs register-task-definition \
    --cli-input-json "$NEW_DEF" \
    --output json) || {
    echo "error: failed to register new task definition revision" >&2
    exit 1
}

NEW_REVISION=$(printf '%s' "$REGISTERED" | jq -r '.taskDefinition.revision')
NEW_TASK_DEF_ARN=$(printf '%s' "$REGISTERED" | jq -r '.taskDefinition.taskDefinitionArn')
echo "    new revision: $NEW_REVISION ($NEW_TASK_DEF_ARN)"

# --- run the task -----------------------------------------------------------
echo "==> running task on cluster: $CLUSTER"
RUN_RESULT=$(aws ecs run-task \
    --cluster "$CLUSTER" \
    --task-definition "$TASK_DEF_FAMILY:$NEW_REVISION" \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUPS],assignPublicIp=ENABLED}" \
    --output json) || {
    echo "error: failed to run task" >&2
    printf '%s' "$RUN_RESULT" | jq '.failures[]? // .' >&2 2>/dev/null || true
    exit 1
}

TASK_ARN=$(printf '%s' "$RUN_RESULT" | jq -r '.tasks[0].taskArn // empty')
if [ -z "$TASK_ARN" ]; then
    echo "error: no task was started" >&2
    printf '%s' "$RUN_RESULT" | jq '.failures' >&2 2>/dev/null || true
    exit 1
fi

TASK_ID=$(printf '%s' "$TASK_ARN" | sed 's|.*/||')
echo "    task arn:  $TASK_ARN"
echo "    task id:   $TASK_ID"
echo

# --- wait for completion (unless --no-wait) ---------------------------------
if [ "$WAIT" -eq 0 ]; then
    echo "==> task started (--no-wait). monitor with:"
    echo "    aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN"
    echo "    aws logs get-log-events --log-group-name /ecs/$TASK_DEF_FAMILY --log-stream-name ecs/affiliates-migration/$TASK_ID"
    exit 0
fi

echo "==> waiting for task to complete..."
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN" || {
    echo "error: wait command failed" >&2
    exit 1
}

# --- inspect the result -----------------------------------------------------
TASK_DETAIL=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" --output json)
STOP_CODE=$(printf '%s' "$TASK_DETAIL" | jq -r '.tasks[0].stopCode')
STOP_REASON=$(printf '%s' "$TASK_DETAIL" | jq -r '.tasks[0].stoppedReason')
EXIT_CODE=$(printf '%s' "$TASK_DETAIL" | jq -r '.tasks[0].containers[0].exitCode // "null"')

echo
echo "==> task stopped"
echo "    stop code:   $STOP_CODE"
echo "    stop reason: $STOP_REASON"
echo "    exit code:   $EXIT_CODE"

# --- fetch the last log lines for context -----------------------------------
echo
echo "--- cloudwatch logs (last 20 lines) ---"
LOG_STREAM="ecs/affiliates-migration/$TASK_ID"
aws logs get-log-events \
    --log-group-name "/ecs/$TASK_DEF_FAMILY" \
    --log-stream-name "$LOG_STREAM" \
    --limit 20 \
    --query 'events[*].message' \
    --output text 2>/dev/null | sed 's/\t/\n/g' || echo "    (could not fetch logs)"
echo "---"

# --- verdict ----------------------------------------------------------------
if [ "$EXIT_CODE" = "0" ]; then
    echo
    echo "==> migrations applied successfully."
    exit 0
else
    echo
    echo "error: migration task exited with code $EXIT_CODE" >&2
    exit 2
fi
