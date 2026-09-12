#!/usr/bin/env python3
"""Run the isolated A0-V ecommerce Runtime Host as one fail-closed process."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import sys
import traceback
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
DEFAULT_CREDENTIALS = RECOVERY / "state/ecommerce-runtime-host/runtime-host-identities.json"
DEFAULT_STATUS = RECOVERY / "logs/ecommerce-runtime-host-status.json"
EXPECTED_ROLES = {
    "web": "aos_a0v_web_20260912",
    "runtime": "aos_a0v_runtime_20260912",
    "directory": "aos_a0v_directory_20260912",
}


class HostBlocked(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _load_credentials(path: Path) -> dict[str, dict[str, str]]:
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise HostBlocked("CREDENTIAL_FILE_INVALID")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostBlocked("CREDENTIAL_FILE_INVALID") from exc
    if type(value) is not dict or set(value) != set(EXPECTED_ROLES):
        raise HostBlocked("CREDENTIAL_FILE_INVALID")
    for plane, role in EXPECTED_ROLES.items():
        item = value.get(plane)
        if (
            type(item) is not dict
            or set(item) != {"dsn", "password", "role"}
            or item.get("role") != role
            or any(type(item.get(key)) is not str or not item[key] for key in item)
        ):
            raise HostBlocked("CREDENTIAL_FILE_INVALID")
    return value


def _configure_environment(
    credentials: dict[str, dict[str, str]], *, bundle_root: Path,
    trust_roots_file: Path,
) -> None:
    if not bundle_root.is_dir():
        raise HostBlocked("BUNDLE_ROOT_INVALID")
    if not trust_roots_file.is_file():
        raise HostBlocked("TRUST_ROOTS_INVALID")
    values = {
        "AOS_DOTENV_DISABLED": "1",
        "AOS_DATABASE_URL": credentials["web"]["dsn"],
        "AOS_EXTENSION_RUNTIME_DATABASE_URL": credentials["runtime"]["dsn"],
        "AOS_EXTENSION_DIRECTORY_DATABASE_URL": credentials["directory"]["dsn"],
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "1",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_EXTENSION_RUNTIME_PLATFORM": "linux/arm64",
        "AOS_BUNDLE_ROOT": str(bundle_root.resolve()),
        "AOS_BUNDLE_TRUST_ROOTS_FILE": str(trust_roots_file.resolve()),
    }
    os.environ.update(values)


def _build_host():
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    from aos_api.asset_registry.control_wiring import (
        build_production_runtime_host_selection,
        build_runtime_control_plane,
    )
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent

    plane = build_runtime_control_plane(
        disable_dependent=EcommerceGrowthDisableDependent()
    )
    selected = build_production_runtime_host_selection(control_plane=plane)
    if selected.status != "ACTIVE" or selected.host is None:
        raise HostBlocked(selected.error_code or "HOST_SELECTION_INACTIVE")
    return selected.host


async def _serve(args: argparse.Namespace) -> None:
    credentials = _load_credentials(args.credential_file.resolve())
    _configure_environment(
        credentials,
        bundle_root=args.bundle_root.resolve(),
        trust_roots_file=args.trust_roots_file.resolve(),
    )
    host = _build_host()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)
    public = {
        "outcome": "RUNTIME_HOST_ACTIVE",
        "pid": os.getpid(),
        "hostId": "a0v-local-ecommerce-host-20260912",
        "tenantCount": 1,
        "positiveTenant": "org-org/dev-project",
        "canaryTenantCount": 0,
        "intervalSeconds": args.interval_seconds,
    }
    _write(args.status_file.resolve(), public)
    print(json.dumps(public, ensure_ascii=False, sort_keys=True), flush=True)
    try:
        await host.serve(stop_event, interval_seconds=args.interval_seconds)
    finally:
        stopped = {**public, "outcome": "RUNTIME_HOST_STOPPED"}
        _write(args.status_file.resolve(), stopped)
        print(json.dumps(stopped, ensure_ascii=False, sort_keys=True), flush=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--trust-roots-file", type=Path, required=True)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--interval-seconds", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.interval_seconds <= 300:
        _write(args.status_file.resolve(), {"outcome": "SAFE_BLOCKED", "reasonCode": "INTERVAL_INVALID"})
        return 2
    lock_path = args.status_file.resolve().with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _write(args.status_file.resolve(), {"outcome": "SAFE_BLOCKED", "reasonCode": "HOST_ALREADY_RUNNING"})
            return 2
        try:
            asyncio.run(_serve(args))
            return 0
        except HostBlocked as exc:
            result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code}
        except Exception as exc:
            result = {
                "outcome": "SAFE_BLOCKED",
                "reasonCode": "HOST_RUNTIME_FAILED",
                "errorType": type(exc).__name__,
                "frames": [{"file": frame.filename, "function": frame.name, "line": frame.lineno}
                           for frame in traceback.extract_tb(exc.__traceback__)],
            }
        _write(args.status_file.resolve(), result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
