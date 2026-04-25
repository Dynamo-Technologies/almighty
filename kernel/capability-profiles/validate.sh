#!/usr/bin/env bash
# Validate every JSON profile in this directory against
# docs/schema/capability-profile.schema.json (WS-106).
#
# Uses python3 + jsonschema. If jsonschema is not importable, a local
# .venv is created in this directory and jsonschema is installed there.
# The .venv is gitignored.

set -euo pipefail

cd "$(dirname "$0")"

SCHEMA="../../docs/schema/capability-profile.schema.json"
PROFILES=(us-bct.json peer.json near-peer.json hybrid-irregular.json)

if [[ ! -f "$SCHEMA" ]]; then
  echo "ERROR: schema not found at $SCHEMA" >&2
  exit 2
fi

PY=${PY:-python3}
if ! "$PY" -c 'import jsonschema' >/dev/null 2>&1; then
  echo "jsonschema not importable for $PY — provisioning local venv..."
  if [[ ! -d .venv ]]; then
    "$PY" -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --quiet jsonschema
  PY=python
fi

"$PY" - "$SCHEMA" "${PROFILES[@]}" <<'PY_EOF'
import json
import sys
from jsonschema import Draft202012Validator, FormatChecker

schema_path, *profile_paths = sys.argv[1:]
with open(schema_path) as f:
    schema = json.load(f)

validator = Draft202012Validator(schema, format_checker=FormatChecker())

failed = 0
for path in profile_paths:
    with open(path) as f:
        profile = json.load(f)
    errors = list(validator.iter_errors(profile))
    if not errors:
        print(f"  OK   {path}")
        continue
    failed += 1
    print(f"  FAIL {path} ({len(errors)} error(s))")
    for err in errors:
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        print(f"      {loc}: {err.message}")

sys.exit(1 if failed else 0)
PY_EOF

echo "All profiles valid."
