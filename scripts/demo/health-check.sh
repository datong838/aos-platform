#!/usr/bin/env bash
# TB.0 · macOS/Linux 健康检查（对齐 health-check.ps1）
set -uo pipefail

INFRA_ONLY=0
REQUIRE_WEB=0
for arg in "$@"; do
  case "$arg" in
    --infra-only) INFRA_ONLY=1 ;;
    --require-web) REQUIRE_WEB=1 ;;
  esac
done

if [ -x "$HOME/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
  export PATH="$HOME/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi

fail=0
http_test() {
  local name="$1" url="$2" required="${3:-0}"
  local code
  code="$(curl -sf -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || true)"
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    printf 'OK   %-22s HTTP %s  %s\n' "$name" "$code" "$url"
    return 0
  fi
  if [ "$required" = 1 ]; then
    printf 'FAIL %-22s unreachable  %s\n' "$name" "$url"
    fail=$((fail + 1))
  else
    printf 'WARN %-22s unreachable  %s\n' "$name" "$url"
  fi
  return 1
}

echo "=== TB.0 health-check ==="

# PG: docker container OR native host
if command -v docker >/dev/null 2>&1 && docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta >/dev/null 2>&1; then
  printf 'OK   %-22s accepting (docker)\n' "PostgreSQL :5433"
elif command -v pg_isready >/dev/null 2>&1 && pg_isready -h 127.0.0.1 -p 5433 -U aos_app >/dev/null 2>&1; then
  printf 'OK   %-22s accepting (native)\n' "PostgreSQL :5433"
else
  printf 'FAIL %-22s not ready\n' "PostgreSQL :5433"
  fail=$((fail + 1))
fi

http_test "MinIO :9000" "http://127.0.0.1:9000/minio/health/live" 1 || true

if [ "$INFRA_ONLY" = 0 ]; then
  http_test "aos-api /v1/health" "http://127.0.0.1:8080/v1/health" 1 || true
  http_test "LiteLLM :4001" "http://127.0.0.1:4001/health/liveliness" 0 || true
  http_test "OCR :8082" "http://127.0.0.1:8082/health" 0 || true
  if [ "$REQUIRE_WEB" = 1 ]; then
    http_test "web :5173" "http://127.0.0.1:5173/" 1 || true
  else
    http_test "web :5173" "http://127.0.0.1:5173/" 0 || true
  fi
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "RESULT: DEMO HEALTH OK"
  exit 0
fi
echo "RESULT: DEMO HEALTH FAIL ($fail)"
if [ "$INFRA_ONLY" = 0 ]; then
  echo "TIP  aos-api 掉线时可执行: bash scripts/demo/ensure-api.sh"
fi
exit 1
