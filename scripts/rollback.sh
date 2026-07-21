#!/usr/bin/env bash
# Rolls the running API container back to the previous commit-tagged image.
# Called by Jenkins when the post-deploy health_check.py smoke test fails.
#
# Usage: rollback.sh [image_name] [container_name] [port]
set -euo pipefail

IMAGE_NAME="${1:-ml-model-cicd-gate-api}"
CONTAINER_NAME="${2:-ml-model-api}"
PORT="${3:-8000}"
KEEP_LAST_N=5

# --- Find the image tag currently running, so we know what to roll back FROM.
current_tag=""
if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  current_image=$(docker inspect --format '{{.Config.Image}}' "$CONTAINER_NAME")
  current_tag="${current_image#${IMAGE_NAME}:}"
fi
echo "rollback: currently running tag = '${current_tag:-none}'"

# --- List locally available commit-tagged images, newest first, and pick the
# --- one right after the current tag -- that's the last known-good version.
# (Reads into the array line-by-line instead of `mapfile` for bash 3.2 portability.)
tags=()
while IFS= read -r tag; do
  tags+=("$tag")
done < <(
  docker images "$IMAGE_NAME" --format '{{.Tag}}\t{{.CreatedAt}}' \
    | grep -v '^latest\b' \
    | sort -k2 -r \
    | cut -f1
)

if [ "${#tags[@]}" -lt 2 ]; then
  echo "rollback: FAILED - fewer than 2 tagged images available for ${IMAGE_NAME}, cannot roll back" >&2
  exit 1
fi

previous_tag=""
for i in "${!tags[@]}"; do
  if [ "${tags[$i]}" = "$current_tag" ]; then
    previous_tag="${tags[$((i + 1))]:-}"
    break
  fi
done
# Fall back to the second-newest image if the running tag wasn't identifiable.
if [ -z "$previous_tag" ]; then
  previous_tag="${tags[1]}"
fi

echo "rollback: rolling back ${IMAGE_NAME} to tag '${previous_tag}'"

# --- Stop the failing container and start the previous image in its place.
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER_NAME" -p "${PORT}:8000" \
  -e "MODEL_VERSION=${previous_tag}" \
  "${IMAGE_NAME}:${previous_tag}"

# --- Confirm the rolled-back version is actually healthy before declaring success.
if ! python3 "$(dirname "$0")/health_check.py" --base-url "http://localhost:${PORT}" --retries 5 --delay 2; then
  echo "rollback: FAILED - previous version '${previous_tag}' is also unhealthy" >&2
  exit 1
fi

# --- Prune old commit-tagged images beyond the retention window.
old_tags=("${tags[@]:$KEEP_LAST_N}")
for tag in "${old_tags[@]:-}"; do
  [ -z "$tag" ] && continue
  echo "rollback: pruning old image ${IMAGE_NAME}:${tag}"
  docker rmi "${IMAGE_NAME}:${tag}" >/dev/null 2>&1 || true
done

echo "rollback: SUCCESS - traffic is now served by '${previous_tag}'"
