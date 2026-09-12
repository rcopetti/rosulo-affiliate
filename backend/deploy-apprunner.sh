#!/usr/bin/env sh
# Deploy a new image version to the Rosulo Affiliates App Runner service.
#
# Updates the Rosulo-Affiliates App Runner service to point at the given image
# tag, preserving all existing environment variables, secrets, port, and the
# ECR access role. App Runner pulls the new image and rolls out a new
# deployment.
#
# Usage:
#   ./deploy-apprunner.sh <tag>             # deploy + wait for completion
#   ./deploy-apprunner.sh <tag> --no-wait   # deploy, don't wait
#   ./deploy-apprunner.sh --latest          # deploy the :latest tag
#
# Exit codes:
#   0 - deployment completed successfully (service is RUNNING)
#   1 - usage error / AWS CLI failure
#   2 - deployment completed but service is not RUNNING (check logs)
set -eu

# --- config -----------------------------------------------------------------
SERVICE_ARN="arn:aws:apprunner:us-west-2:239714841352:service/Rosulo-Affiliates/23b44d7fb7fd4c1c981e2e334ab1f2c1"
ECR_REGISTRY="239714841352.dkr.ecr.us-west-2.amazonaws.com"
IMAGE_NAME="rosulo/rosulo-affiliate-backend"
ACCESS_ROLE_ARN="arn:aws:iam::239714841352:role/service-role/AffiliatesECRAccessRole"
AWS_REGION="us-west-2"

# --- args -------------------------------------------------------------------
TAG=""
WAIT=1

show_usage() {
    cat <<'USAGE'
Usage: ./deploy-apprunner.sh <tag> [--no-wait]
       ./deploy-apprunner.sh --latest [--no-wait]

  <tag>       Image tag to deploy (e.g. 0.1-3b8ab83)
  --latest    Use the :latest tag
  --no-wait   Start the deployment but don't block until it finishes
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

# --- fetch current service config (preserve env vars + secrets) -------------
echo "==> fetching current service config: Rosulo-Affiliates"
CURRENT=$(aws apprunner describe-service \
    --service-arn "$SERVICE_ARN" \
    --query 'Service.SourceConfiguration' \
    --output json) || {
    echo "error: could not describe App Runner service" >&2
    exit 1
}

# --- build the update payload with the new image, preserving everything else -
UPDATE_CONFIG=$(printf '%s' "$CURRENT" | jq \
    --arg image "$IMAGE" \
    --arg role "$ACCESS_ROLE_ARN" \
    '{
        ImageRepository: {
            ImageIdentifier: $image,
            ImageRepositoryType: .ImageRepository.ImageRepositoryType,
            ImageConfiguration: .ImageRepository.ImageConfiguration
        },
        AuthenticationConfiguration: .AuthenticationConfiguration
    }')

# --- trigger the deployment -------------------------------------------------
echo "==> updating App Runner service to image: $IMAGE"
UPDATE_RESULT=$(aws apprunner update-service \
    --service-arn "$SERVICE_ARN" \
    --source-configuration "$UPDATE_CONFIG" \
    --output json) || {
    echo "error: failed to update App Runner service" >&2
    exit 1
}

OPERATION_ID=$(printf '%s' "$UPDATE_RESULT" | jq -r '.OperationId')
PREV_STATUS=$(printf '%s' "$UPDATE_RESULT" | jq -r '.Service.Status')
echo "    operation id: $OPERATION_ID"
echo "    prev status:  $PREV_STATUS"
echo

if [ "$WAIT" -eq 0 ]; then
    echo "==> deployment started (--no-wait). monitor with:"
    echo "    aws apprunner describe-service --service-arn $SERVICE_ARN --query 'Service.Status'"
    exit 0
fi

# --- wait for the deployment to complete ------------------------------------
# App Runner goes through: RUNNING → PENDING (deploying) → RUNNING (done)
# or → FAILED. We poll until it's back to RUNNING or FAILED.
echo "==> waiting for deployment to complete..."
echo "    (this can take 2-5 minutes — App Runner pulls the image and rolls out)"

sleep 10
while true; do
    STATUS=$(aws apprunner describe-service \
        --service-arn "$SERVICE_ARN" \
        --query 'Service.Status' \
        --output text 2>/dev/null || echo "ERROR")

    case "$STATUS" in
        RUNNING)
            echo "    status: RUNNING — deployment complete"
            break
            ;;
        FAILED)
            echo "error: deployment FAILED" >&2
            echo "    check the App Runner console for deployment logs" >&2
            exit 2
            ;;
        PENDING|OPERATION_IN_PROGRESS)
            printf '.'
            sleep 15
            ;;
        *)
            echo "    status: $STATUS (unexpected — continuing to wait)"
            sleep 15
            ;;
    esac
done

echo
echo "==> deployed successfully"
echo "    image: $IMAGE"
echo
echo "    service URL:"
aws apprunner describe-service \
    --service-arn "$SERVICE_ARN" \
    --query 'Service.ServiceUrl' \
    --output text 2>/dev/null | sed 's/^/    /'
