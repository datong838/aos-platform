#!/usr/bin/env python3
"""Fail-closed ownership check for the detached local AOS API runtime."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _command_reader(pid: int) -> str:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _listener_reader(port: int) -> set[int]:
    completed = subprocess.run(
        ["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError("listener inspection failed")
    return {
        int(raw)
        for line in completed.stdout.splitlines()
        if (raw := line.strip()).isdigit()
    }


def _result(
    ok: bool,
    code: str,
    *,
    pid: int | None,
    port: int,
    listener_pids: set[int] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "code": code,
        "pid": pid,
        "port": port,
        "listenerPids": sorted(listener_pids or set()),
    }


def evaluate_runtime_owner(
    *,
    pid_file: Path,
    port: int,
    expected_tokens: tuple[str, ...],
    process_exists: Callable[[int], bool] = _process_exists,
    command_reader: Callable[[int], str] = _command_reader,
    listener_reader: Callable[[int], set[int]] = _listener_reader,
) -> dict[str, Any]:
    """Require one live expected process to be the sole listener for ``port``."""
    if not pid_file.is_file():
        return _result(False, "PID_FILE_MISSING", pid=None, port=port)
    try:
        raw_pid = pid_file.read_text(encoding="utf-8").strip()
        pid = int(raw_pid)
        if pid <= 0:
            raise ValueError
    except (OSError, ValueError):
        return _result(False, "PID_FILE_INVALID", pid=None, port=port)

    if not process_exists(pid):
        return _result(False, "PROCESS_NOT_ALIVE", pid=pid, port=port)

    command = command_reader(pid)
    if not command or any(token not in command for token in expected_tokens):
        return _result(False, "PROCESS_IDENTITY_MISMATCH", pid=pid, port=port)

    try:
        listener_pids = listener_reader(port)
    except (OSError, RuntimeError, ValueError):
        return _result(False, "LISTENER_INSPECTION_FAILED", pid=pid, port=port)
    if listener_pids != {pid}:
        return _result(
            False,
            "LISTENER_OWNER_MISMATCH",
            pid=pid,
            port=port,
            listener_pids=listener_pids,
        )
    return _result(
        True,
        "RUNTIME_OWNER_EXACT",
        pid=pid,
        port=port,
        listener_pids=listener_pids,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid-file", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--expected-token", action="append", default=[])
    args = parser.parse_args()
    result = evaluate_runtime_owner(
        pid_file=args.pid_file,
        port=args.port,
        expected_tokens=tuple(args.expected_token),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
