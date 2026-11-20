#!/usr/bin/env bash
# Build with the classic builder (DOCKER_BUILDKIT=0; this host has no buildx)
# and wait until the site answers GET /healthz.
set -euo pipefail
cd "$(dirname "$0")/.."

export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

docker compose build
docker compose up -d

url=http://127.0.0.1:8100/healthz
for _ in $(seq 1 90); do
  if body=$(curl -fsS "$url" 2>/dev/null); then
    printf 'crocket-site is up: %s\n%s\n' "$url" "$body"
    exit 0
  fi
  sleep 1
done

echo "timed out waiting for $url" >&2
docker compose logs --tail=80 >&2 || true
exit 1
