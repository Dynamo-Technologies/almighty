#!/bin/bash
# Launcher for the almighty FastAPI shim on spark-763d.
#
# Repurposes the existing crewai:stig-hardened-boto3 container as our
# worker — bind-mounts the almighty repo, sets PYTHONPATH to include
# every package's src/ dir, installs the few extra deps the shim needs
# (fastapi, uvicorn, pyrapide, etc), and runs uvicorn against
# almighty_agent_runtime.shim:app.
#
# Usage (run on spark-763d):
#   ./run-worker.sh [REPO_ROOT]      # default REPO_ROOT = $HOME/almighty
#
# Idempotent: stops and recreates the container if it's already running.
set -euxo pipefail

REPO_ROOT="${1:-$HOME/almighty}"
PORT="${PORT:-7000}"
IMAGE="${IMAGE:-crewai:stig-hardened-boto3}"
CONTAINER="${CONTAINER:-almighty-worker}"

# Pre-flight: repo must exist and be on the right branch.
test -d "$REPO_ROOT/agents/runtime" || {
  echo "ERROR: $REPO_ROOT/agents/runtime not found. Clone first:" >&2
  echo "  git clone https://github.com/Dynamo-Technologies/almighty $REPO_ROOT" >&2
  exit 1
}
( cd "$REPO_ROOT" && git pull --ff-only )

# Stop any prior worker.
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

# Start fresh. Notes:
#   --entrypoint bash    — the crewai:stig-hardened-boto3 image has
#                          ENTRYPOINT = ["python","-m","crewai.cli.cli"]
#                          baked in. Without overriding, our bash -c …
#                          would be passed as args to the crewai CLI and
#                          fail with "No such command 'bash'". Override
#                          to bash and pass the script via -c.
#   --network host       — share the Spark's network namespace so the
#                          shim can reach localhost:8001 (vllm-agent) and
#                          the EC2 can reach us at 100.106.123.5:$PORT.
#   PYTHONPATH           — all src/ dirs of the almighty packages so
#                          imports resolve without `pip install -e`.
#   pip install --quiet  — adds the few extras the stig-hardened image
#                          doesn't have. ~30s on first start, cached
#                          afterward in the container's writable layer.
docker run -d --name "$CONTAINER" \
  --entrypoint bash \
  --network host \
  --restart unless-stopped \
  -v "$REPO_ROOT:/app/almighty:ro" \
  -e PYTHONPATH="/app/almighty/kernel:/app/almighty/agents/tools/src:/app/almighty/agents/blue/src:/app/almighty/agents/red/src:/app/almighty/agents/white-cell/src:/app/almighty/agents/runtime/src:/app/almighty/services/czml-validator/src" \
  -e BLUE_LLM_BASE_URL="http://127.0.0.1:8001/v1" \
  -e RED_LLM_BASE_URL="http://100.112.216.53:8000/v1" \
  -e BLUE_LLM_API_KEY="EMPTY" \
  -e RED_LLM_API_KEY="EMPTY" \
  "$IMAGE" \
  -c "
    set -e
    # crewai:stig-hardened-boto3 is on registry.access.redhat.com/ubi9/
    # python-312, an s2i-style image whose real Python 3.12 + pip live in
    # /opt/app-root. \`--entrypoint bash\` bypasses the s2i shim that
    # normally activates that env, so /usr/bin/python3 (UBI9 system 3.9,
    # no pip) is what we'd hit by default. Prepend the app-root bin dir
    # so python3 resolves to 3.12 with pip baked in.
    export PATH=/opt/app-root/bin:\$PATH
    python3 -m pip install --no-cache-dir --quiet \
      fastapi 'uvicorn[standard]' httpx pyrapide pydantic
    cd /app/almighty
    exec python3 -m uvicorn almighty_agent_runtime.shim:app --host 0.0.0.0 --port $PORT --log-level info
  "

# Wait up to 90s for /healthz.
echo "waiting for healthz on :$PORT..."
for i in $(seq 1 45); do
  if curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then
    echo "almighty-worker healthy on :$PORT"
    exit 0
  fi
  sleep 2
done

echo "ERROR: worker did not become healthy in 90s" >&2
echo "--- container logs (last 50) ---" >&2
docker logs --tail 50 "$CONTAINER" >&2
exit 1
