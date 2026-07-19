"""TWC.10+ / 165 — Local-First dependency probe + ensure (PG/MinIO)."""
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from aos_api.logging_facade import get_logger
from aos_api.oidc import allow_dev

log = get_logger("aos-api.local-deps")

# (id, label, host, port)
CORE_DEPS: tuple[tuple[str, str, str, int], ...] = (
    ("pg", "PostgreSQL", "127.0.0.1", 5433),
    ("minio", "MinIO", "127.0.0.1", 9000),
)

COMPOSE_SERVICES = ("aos-dev-pg", "aos-dev-minio", "aos-dev-minio-init")


def platform_root() -> Path:
    # aos_api/local_deps.py → services/aos-api → aos-platform
    return Path(__file__).resolve().parents[2]


def compose_file() -> Path:
    override = os.getenv("AOS_DEV_COMPOSE_FILE", "").strip()
    if override:
        return Path(override)
    return platform_root() / "deploy" / "dev" / "docker-compose.yml"


def ensure_allowed() -> bool:
    if os.getenv("AOS_LOCAL_DEPS_ENSURE", "").strip() in ("1", "true", "yes"):
        return True
    return allow_dev()


def tcp_up(host: str, port: int, *, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_deps() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for dep_id, label, host, port in CORE_DEPS:
        ok = tcp_up(host, port)
        items.append(
            {
                "id": dep_id,
                "name": label,
                "host": host,
                "port": port,
                "ok": ok,
                "endpoint": f"{host}:{port}",
            }
        )
    all_ok = all(i["ok"] for i in items)
    return {
        "ok": all_ok,
        "items": items,
        "ensureAllowed": ensure_allowed(),
    }


def _docker_bin() -> str | None:
    for candidate in (
        os.getenv("DOCKER_BIN", "").strip(),
        str(Path.home() / "Applications/Docker.app/Contents/Resources/bin/docker"),
        "docker",
    ):
        if not candidate:
            continue
        p = Path(candidate)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
        # bare name on PATH
        if candidate == "docker":
            from shutil import which

            found = which("docker")
            if found:
                return found
    return None


def ensure_deps(*, wait_seconds: float = 45.0) -> dict[str, Any]:
    """Start core compose services if ports are down. Returns probe + action."""
    before = probe_deps()
    if before["ok"]:
        return {
            **before,
            "action": "already_up",
            "message": "依赖已就绪",
            "started": False,
        }
    if not ensure_allowed():
        return {
            **before,
            "action": "forbidden",
            "message": "本环境不允许自动拉起依赖（需 AOS_AUTH_ALLOW_DEV 或 AOS_LOCAL_DEPS_ENSURE）",
            "started": False,
            "ok": False,
        }

    docker = _docker_bin()
    compose = compose_file()
    if not docker:
        return {
            **before,
            "action": "failed",
            "message": "未找到 docker，无法自动拉起依赖",
            "started": False,
            "ok": False,
        }
    if not compose.is_file():
        return {
            **before,
            "action": "failed",
            "message": f"缺少 compose 文件：{compose}",
            "started": False,
            "ok": False,
        }

    cmd = [
        docker,
        "compose",
        "-f",
        str(compose),
        "up",
        "-d",
        *COMPOSE_SERVICES,
    ]
    log.info("local_deps_ensure cmd=%s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(platform_root()),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("local_deps_ensure_exc err=%s", exc)
        return {
            **before,
            "action": "failed",
            "message": f"启动失败：{exc}",
            "started": False,
            "ok": False,
        }

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[-800:]
        log.warning("local_deps_ensure_failed code=%s err=%s", proc.returncode, err)
        return {
            **before,
            "action": "failed",
            "message": f"docker compose 失败（exit {proc.returncode}）：{err or '无输出'}",
            "started": False,
            "ok": False,
        }

    deadline = time.time() + max(5.0, wait_seconds)
    after = probe_deps()
    while time.time() < deadline and not after["ok"]:
        time.sleep(1.0)
        after = probe_deps()

    if after["ok"]:
        log.info("local_deps_ensure_ok")
        return {
            **after,
            "action": "started",
            "message": "依赖已自动拉起并就绪",
            "started": True,
        }

    down = [i["name"] for i in after["items"] if not i["ok"]]
    return {
        **after,
        "action": "failed",
        "message": f"compose 已执行，但端口未就绪：{', '.join(down)}",
        "started": True,
        "ok": False,
    }


DOCKER_HUB_V2 = "https://registry-1.docker.io/v2/"


def probe_docker_hub(*, timeout: float = 8.0) -> dict[str, Any]:
    """Active probe: Hub registry reachable? (401 = OK for anonymous)."""
    import urllib.error
    import urllib.request

    started = time.monotonic()
    try:
        req = urllib.request.Request(DOCKER_HUB_V2, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200) or 200)
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "endpoint": DOCKER_HUB_V2,
            "httpStatus": code,
            "latencyMs": latency_ms,
            "message": "可达",
            "hint": "可用 bash scripts/demo/start-local.sh",
        }
    except urllib.error.HTTPError as exc:
        # Anonymous v2 often returns 401 — registry is reachable.
        latency_ms = int((time.monotonic() - started) * 1000)
        code = int(exc.code)
        ok = code < 500
        return {
            "ok": ok,
            "endpoint": DOCKER_HUB_V2,
            "httpStatus": code,
            "latencyMs": latency_ms,
            "message": "可达" if ok else f"HTTP {code}",
            "hint": (
                "可用 bash scripts/demo/start-local.sh"
                if ok
                else "改用 bash scripts/demo/start-local-native.sh"
            ),
        }
    except Exception as exc:  # noqa: BLE001 — surface any network/timeout to UI
        latency_ms = int((time.monotonic() - started) * 1000)
        detail = str(exc).strip() or exc.__class__.__name__
        return {
            "ok": False,
            "endpoint": DOCKER_HUB_V2,
            "httpStatus": None,
            "latencyMs": latency_ms,
            "message": f"不可达 · {detail}",
            "hint": "改用 bash scripts/demo/start-local-native.sh（见启停手册 72 §1.3.1）",
        }
