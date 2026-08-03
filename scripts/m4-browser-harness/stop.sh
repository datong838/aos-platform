#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${AOS_M4_STATE_DIR:-${TMPDIR:-/tmp}/aos-m4-browser-harness}"
CONTAINER="${AOS_M4_PG_CONTAINER:-aos-m4-browser-pg}"

for service in web proxy api; do
  pid_file="$STATE_DIR/${service}.pid"
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
done

if command -v docker >/dev/null && docker inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
fi

for file in \
  postgres.container seed.json access-token token-response.json \
  api.pid proxy.pid web.pid api.log proxy.log web.log \
  me.json current.json reference.json; do
  rm -f "$STATE_DIR/$file"
done
rmdir "$STATE_DIR" 2>/dev/null || true
echo "M4 browser harness stopped and isolated state removed"
