#!/usr/bin/env python3
"""Standalone Agnes .env smoke. Not AIP Health and not an AgentRun.

Reads AGNES_API_KEY / AGNES_BASE_URL / AGNES_TEXT_MODEL from a local .env
or the process environment. Prints only metadata: never the key, prompt,
answer, or response body.

Supports the international (.com) and domestic (.cn) Agnes hubs.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ALLOWED_KEYS = ("AGNES_API_KEY", "AGNES_BASE_URL", "AGNES_TEXT_MODEL")
DEFAULT_ENV = Path("/Users/ddt/work/projects/ai_agent/aos-platform/.env")
DEFAULT_MODEL = "agnes-2.5-flash"
DEFAULT_TIMEOUT_MS = 60_000
PROBE_COUNT = 3
PINNED_HOSTS = frozenset({"apihub.agnes-ai.com", "apihub.agnes-ai.cn", "api.agnes-ai.cn"})
SAFE_PROBES = (
    "请仅回复一个简短的服务可用状态词。",
    "请用一句不含个人信息的中文说明当前服务可用。",
    "请仅回复：健康检查通过。",
)


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in ALLOWED_KEYS:
            continue
        values[key] = value.strip().strip("'").strip('"')
    return values


def resolve_settings(env_file: Path) -> dict[str, str]:
    merged = load_env_file(env_file)
    for key in ALLOWED_KEYS:
        if os.environ.get(key):
            merged[key] = os.environ[key]
    return merged


def chat_url(base_url: str) -> tuple[str, str]:
    parsed = urlsplit(base_url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or host not in PINNED_HOSTS:
        raise SystemExit("blocked: AGNES_BASE_URL host is not a pinned Agnes hub")
    path = parsed.path.rstrip("/") or "/v1"
    if path != "/v1":
        raise SystemExit("blocked: AGNES_BASE_URL path must be /v1")
    return f"https://{host}/v1/chat/completions", host


def one_probe(
    *,
    client: httpx.Client,
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_ms: int,
) -> dict[str, object]:
    started = time.perf_counter()
    try:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 32,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "latencyMs": int((time.perf_counter() - started) * 1000),
            "timeoutMs": timeout_ms,
        }
    except httpx.HTTPError as exc:
        return {
            "status": "transport_error",
            "errorType": type(exc).__name__,
            "latencyMs": int((time.perf_counter() - started) * 1000),
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
        parsed = response.json()
        body = parsed if isinstance(parsed, dict) else None
    except ValueError:
        body = None
    message = None
    finish_reason = None
    content_type = "missing"
    if isinstance(body, dict):
        choices = body.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        if isinstance(first, dict):
            finish_reason = (
                first.get("finish_reason")
                if isinstance(first.get("finish_reason"), str)
                else None
            )
            maybe_message = first.get("message")
            if isinstance(maybe_message, dict):
                message = maybe_message.get("content")
                content_type = type(message).__name__
    return {
        "status": "ok" if 200 <= response.status_code < 300 else "http_error",
        "httpStatus": response.status_code,
        "latencyMs": latency_ms,
        "answerPresent": isinstance(message, str) and bool(message.strip()),
        "contentType": content_type,
        "finishReason": finish_reason,
        "responseIdPresent": isinstance(body, dict) and isinstance(body.get("id"), str),
    }


def smoke(*, env_file: Path, timeout_ms: int) -> dict[str, object]:
    settings = resolve_settings(env_file)
    api_key = settings.get("AGNES_API_KEY") or ""
    base_url = settings.get("AGNES_BASE_URL") or ""
    model = settings.get("AGNES_TEXT_MODEL") or DEFAULT_MODEL
    if not api_key:
        return {
            "status": "blocked",
            "blocker": "missing_agnes_api_key",
            "envFileExists": env_file.is_file(),
        }
    if not base_url:
        return {"status": "blocked", "blocker": "missing_agnes_base_url"}

    url, host = chat_url(base_url)
    probes: list[dict[str, object]] = []
    with httpx.Client(
        trust_env=False,
        follow_redirects=False,
        timeout=timeout_ms / 1000,
    ) as client:
        for prompt in SAFE_PROBES:
            probes.append(
                one_probe(
                    client=client,
                    url=url,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    timeout_ms=timeout_ms,
                )
            )
    ok_count = sum(1 for item in probes if item.get("status") == "ok")
    return {
        "status": "ok" if ok_count == PROBE_COUNT else "blocked",
        "source": "env-smoke-not-aip-health",
        "host": host,
        "model": model,
        "probeCount": PROBE_COUNT,
        "okCount": ok_count,
        "timeoutMs": timeout_ms,
        "probes": probes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    args = parser.parse_args()
    print(json.dumps(smoke(env_file=args.env_file, timeout_ms=args.timeout_ms), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
