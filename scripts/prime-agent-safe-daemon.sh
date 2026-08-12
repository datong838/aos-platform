#!/bin/zsh

set -eu

readonly PRIME_AGENT_BIN="/Users/ddt/.workbuddy/binaries/node/versions/22.22.2/bin/prime-agent"
readonly PRIME_AGENT_NODE_DIR="/Users/ddt/.workbuddy/binaries/node/versions/22.22.2/bin"
readonly PRIME_AGENT_AUTH="/Users/ddt/.prime/agent/auth.json"
readonly PRIME_AGENT_CWD="/Users/ddt/work/projects/ai_agent"

validate_auth() {
  /usr/bin/python3 - "${PRIME_AGENT_AUTH}" <<'PY'
import json
import os
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"Prime Agent auth file is missing: {path}")

metadata = path.stat()
if metadata.st_uid != os.getuid():
    raise SystemExit("Prime Agent auth file is not owned by the current user")

mode = stat.S_IMODE(metadata.st_mode)
if mode != 0o600:
    raise SystemExit(f"Prime Agent auth file mode must be 0600, got {mode:04o}")

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"Prime Agent auth file is invalid: {type(error).__name__}") from error

credential = payload.get("agnes")
if not isinstance(credential, dict):
    raise SystemExit("Prime Agent auth file has no AGNES credential")
if credential.get("type") != "api_key":
    raise SystemExit("Prime Agent AGNES credential must use api_key auth")
if not isinstance(credential.get("key"), str) or not credential["key"].strip():
    raise SystemExit("Prime Agent AGNES credential is empty")
PY
}

validate_auth

if [[ "${1:-}" == "--check" ]]; then
  if (( $# != 1 )); then
    print -u2 "usage: ${0:t} [--check]"
    exit 64
  fi
  print "Prime Agent safe-start preflight: OK"
  exit 0
fi

if (( $# != 0 )); then
  print -u2 "usage: ${0:t} [--check]"
  exit 64
fi

if [[ ! -x "${PRIME_AGENT_BIN}" ]]; then
  print -u2 "Prime Agent executable is unavailable: ${PRIME_AGENT_BIN}"
  exit 69
fi

cd "${PRIME_AGENT_CWD}"
export PATH="${PRIME_AGENT_NODE_DIR}:/usr/bin:/bin:/usr/sbin:/sbin"
unset AGNES_API_KEY

exec "${PRIME_AGENT_BIN}" \
  --provider agnes \
  --model agnes-2.5-flash \
  --mode daemon
