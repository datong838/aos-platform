#!/usr/bin/env python3
"""Recover a configured Codex thread after a likely interrupted response stream.

The watchdog never searches message text for an error string.  It treats a turn as
interrupted only when the newest user message has no later final assistant message
and the rollout transcript has stopped changing for the configured grace period.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


DEFAULT_HOME = Path.home() / ".codex" / "long-task-watchdog"
DEFAULT_CONFIG = DEFAULT_HOME / "config.json"
DEFAULT_STATE = DEFAULT_HOME / "state.json"
DEFAULT_LOCK = DEFAULT_HOME / "watchdog.lock"
DEFAULT_CODEX_STATE = Path.home() / ".codex" / "state_5.sqlite"
DEFAULT_CODEX = Path.home() / ".local" / "bin" / "codex"
FINAL_PHASES = frozenset({"final", "final_answer"})


@dataclass(frozen=True)
class TranscriptStatus:
    active: bool
    last_activity_at: float
    latest_user_at: float | None
    latest_assistant_at: float | None
    latest_final_at: float | None
    latest_task_started_at: float | None
    latest_task_completed_at: float | None
    turn_running: bool
    pending_tool_calls: int
    oldest_pending_tool_at: float | None


def _timestamp(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _message_role_phase(record: dict[str, Any]) -> tuple[str | None, str | None]:
    if record.get("type") == "response_item":
        payload = record.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "message":
            return payload.get("role"), payload.get("phase")
    if record.get("type") == "event_msg":
        payload = record.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "agent_message":
            return "assistant", payload.get("phase")
    return None, None


def inspect_transcript(path: Path) -> TranscriptStatus:
    latest_user_at: float | None = None
    latest_assistant_at: float | None = None
    latest_final_at: float | None = None
    latest_task_started_at: float | None = None
    latest_task_completed_at: float | None = None
    last_activity_at = path.stat().st_mtime
    tool_calls: dict[str, float] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ts = _timestamp(record.get("timestamp"))
            if ts is not None:
                last_activity_at = max(last_activity_at, ts)
            role, phase = _message_role_phase(record)
            if role == "user" and ts is not None:
                latest_user_at = ts
            elif role == "assistant" and ts is not None:
                latest_assistant_at = ts
                if phase in FINAL_PHASES:
                    latest_final_at = ts
            if record.get("type") == "event_msg":
                event_payload = record.get("payload")
                if isinstance(event_payload, dict) and ts is not None:
                    if event_payload.get("type") == "task_started":
                        latest_task_started_at = ts
                    elif event_payload.get("type") == "task_complete":
                        latest_task_completed_at = ts
            if record.get("type") == "response_item":
                payload = record.get("payload")
                if isinstance(payload, dict):
                    call_id = payload.get("call_id")
                    if payload.get("type") in {"custom_tool_call", "function_call"}:
                        if isinstance(call_id, str):
                            tool_calls[call_id] = ts or last_activity_at
                    elif payload.get("type") in {
                        "custom_tool_call_output",
                        "function_call_output",
                    }:
                        if isinstance(call_id, str):
                            tool_calls.pop(call_id, None)
    active = latest_user_at is not None and (
        latest_final_at is None or latest_final_at < latest_user_at
    )
    turn_running = latest_task_started_at is not None and (
        latest_task_completed_at is None
        or latest_task_completed_at < latest_task_started_at
    )
    return TranscriptStatus(
        active,
        last_activity_at,
        latest_user_at,
        latest_assistant_at,
        latest_final_at,
        latest_task_started_at,
        latest_task_completed_at,
        turn_running,
        len(tool_calls),
        min(tool_calls.values()) if tool_calls else None,
    )


def find_rollout_path(thread_id: str, state_db: Path = DEFAULT_CODEX_STATE) -> Path:
    uri = f"file:{state_db}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute(
            "SELECT rollout_path FROM threads WHERE id = ?", (thread_id,)
        ).fetchone()
    if not row:
        raise RuntimeError(f"thread not found: {thread_id}")
    return Path(row[0])


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


@contextlib.contextmanager
def exclusive_lock(path: Path) -> Iterable[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("watchdog already running") from exc
        yield


def _sanitized_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in (
        "AGNES_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
    ):
        environment.pop(key, None)
    return environment


def _additional_writable_dirs(config: dict[str, Any]) -> list[str]:
    configured = config.get("additional_writable_dirs", [])
    if not isinstance(configured, list):
        raise ValueError("additional_writable_dirs must be a list")
    forbidden = {Path("/").resolve(), Path.home().resolve()}
    result: list[str] = []
    seen: set[Path] = set()
    for item in configured:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("additional writable directory must be a path string")
        path = Path(item).expanduser()
        if not path.is_absolute():
            raise ValueError(f"additional writable directory must be absolute: {item}")
        resolved = path.resolve()
        if resolved in forbidden:
            raise ValueError(f"broad writable directory is forbidden: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"additional writable directory does not exist: {resolved}")
        if resolved not in seen:
            seen.add(resolved)
            result.append(str(resolved))
    return result


def resume_command(config: dict[str, Any]) -> list[str]:
    command = [
        str(config.get("codex_path", DEFAULT_CODEX)),
        "exec",
        "--sandbox",
        "workspace-write",
    ]
    for writable_dir in _additional_writable_dirs(config):
        command.extend(["--add-dir", writable_dir])
    command.extend(
        [
            "resume",
            "--json",
            str(config["thread_id"]),
            "-",
        ]
    )
    return command


def resume_once(
    config: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    prompt = config["resume_prompt"]
    return runner(
        resume_command(config),
        input=prompt,
        text=True,
        capture_output=True,
        cwd=config["project_root"],
        env=_sanitized_environment(),
        timeout=int(config.get("resume_timeout_seconds", 14_400)),
        check=False,
    )


def _log(message: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    print(f"{now} {message}", flush=True)


def _max_consecutive_failures(config: dict[str, Any]) -> int:
    maximum = int(config.get("max_consecutive_failures", 3))
    if maximum < 1:
        raise ValueError("max_consecutive_failures must be at least 1")
    return maximum


def reset_circuit(state_path: Path, *, now: float | None = None) -> None:
    state = _load_json(state_path, {})
    reset_at = time.time() if now is None else now
    state.update(
        {
            "consecutive_failures": 0,
            "next_retry_at": 0,
            "last_recovery_outcome": "circuit_reset",
            "last_decision": "circuit-reset",
            "last_circuit_reset_at": reset_at,
            "recovery_episode_id": None,
            "last_recovered_at": None,
            "visible_ack_at": None,
        }
    )
    state.pop("circuit_opened_at", None)
    state.pop("circuit_reason", None)
    _write_json(state_path, state)


def evaluate(
    config: dict[str, Any],
    state: dict[str, Any],
    *,
    now: float,
    rollout_path: Path,
) -> tuple[str, TranscriptStatus]:
    status = inspect_transcript(rollout_path)
    if not config.get("enabled", False):
        return "disabled", status
    if not status.active:
        return "idle", status
    if status.turn_running:
        return "turn-running", status
    if status.pending_tool_calls and status.oldest_pending_tool_at is not None and (
        now - status.oldest_pending_tool_at
        < int(config.get("max_tool_silence_seconds", 300))
    ):
        return "tool-running", status
    if now - status.last_activity_at < int(config.get("grace_seconds", 240)):
        return "live", status
    maximum_failures = _max_consecutive_failures(config)
    if (
        state.get("last_recovery_outcome") == "circuit_open"
        or int(state.get("consecutive_failures", 0)) >= maximum_failures
    ):
        return "circuit-open", status
    next_retry_at = float(state.get("next_retry_at", 0))
    if next_retry_at > now:
        return "backoff", status
    return "recover", status


def run_once(
    config_path: Path = DEFAULT_CONFIG,
    state_path: Path = DEFAULT_STATE,
    *,
    now: float | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    config = _load_json(config_path, {})
    if not config:
        return "missing-config"
    state = _load_json(state_path, {})
    rollout_path = Path(config.get("rollout_path") or find_rollout_path(config["thread_id"]))
    current = time.time() if now is None else now
    decision, status = evaluate(
        config, state, now=current, rollout_path=rollout_path
    )
    state.update(
        {
            "last_check_at": current,
            "last_decision": decision,
            "last_activity_at": status.last_activity_at,
            "active_turn_detected": status.active,
            "rollout_path": str(rollout_path),
        }
    )
    if decision != "recover":
        if (
            decision == "idle"
            and state.get("last_recovery_outcome") != "circuit_open"
        ):
            state["consecutive_failures"] = 0
            state["next_retry_at"] = 0
        elif decision == "circuit-open":
            state["next_retry_at"] = 0
            state["last_recovery_outcome"] = "circuit_open"
            state.setdefault("circuit_opened_at", current)
            state.setdefault(
                "circuit_reason", "maximum consecutive recovery failures reached"
            )
        _write_json(state_path, state)
        return decision

    failures = int(state.get("consecutive_failures", 0))
    maximum_failures = _max_consecutive_failures(config)
    if failures == 0:
        state.update(
            {
                "recovery_episode_id": f"recovery-{int(current * 1000)}",
                "last_recovery_outcome": "attempting",
                "visible_ack_at": None,
                "last_recovered_at": None,
            }
        )
    requested_attempts = 2 if failures == 0 else 1
    attempts = min(requested_attempts, maximum_failures - failures)
    for attempt in range(1, attempts + 1):
        before_resume = inspect_transcript(rollout_path)
        state["last_attempt_at"] = time.time()
        state["total_attempts"] = int(state.get("total_attempts", 0)) + 1
        _write_json(state_path, state)
        _log(f"resume attempt {attempt}/{attempts} thread={config['thread_id']}")
        try:
            result = resume_once(config, runner=runner)
        except (OSError, subprocess.SubprocessError) as exc:
            state["last_error"] = f"{type(exc).__name__}: {exc}"
            result = None
        if result is not None:
            state["last_exit_code"] = result.returncode
            state["last_stdout_tail"] = result.stdout[-4000:]
            state["last_stderr_tail"] = result.stderr[-4000:]
            after_resume = inspect_transcript(rollout_path)
            visible_final = (
                after_resume.latest_final_at is not None
                and (
                    before_resume.latest_final_at is None
                    or after_resume.latest_final_at > before_resume.latest_final_at
                )
            )
            if result.returncode == 0 and visible_final:
                state.update(
                    {
                        "consecutive_failures": 0,
                        "next_retry_at": 0,
                        "last_recovered_at": time.time(),
                        "visible_ack_at": after_resume.latest_final_at,
                        "last_recovery_outcome": "recovered",
                        "last_decision": "recovered",
                    }
                )
                state.pop("circuit_opened_at", None)
                state.pop("circuit_reason", None)
                _write_json(state_path, state)
                return "recovered"
            if result.returncode == 0:
                state["last_error"] = "resume exited 0 without a visible final"
        if attempt < attempts:
            time.sleep(float(config.get("immediate_retry_delay_seconds", 2)))

    total_failures = failures + attempts
    state["consecutive_failures"] = total_failures
    if total_failures >= maximum_failures:
        state["next_retry_at"] = 0
        state["last_recovery_outcome"] = "circuit_open"
        state["last_decision"] = "circuit-open"
        state["circuit_opened_at"] = time.time()
        state["circuit_reason"] = "maximum consecutive recovery failures reached"
        _write_json(state_path, state)
        return "circuit-open"
    state["next_retry_at"] = time.time() + int(
        config.get("retry_interval_seconds", 300)
    )
    state["last_recovery_outcome"] = "failed"
    state["last_decision"] = "retry-scheduled"
    _write_json(state_path, state)
    return "retry-scheduled"


def status(config_path: Path, state_path: Path) -> dict[str, Any]:
    config = _load_json(config_path, {})
    state = _load_json(state_path, {})
    result = {"config": config, "state": state}
    if config.get("thread_id"):
        rollout_path = Path(
            config.get("rollout_path") or find_rollout_path(config["thread_id"])
        )
        result["transcript"] = inspect_transcript(rollout_path).__dict__
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--once", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--reset-circuit", action="store_true")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(args.config, args.state), ensure_ascii=False, indent=2))
        return 0
    if args.reset_circuit:
        try:
            with exclusive_lock(args.lock):
                reset_circuit(args.state)
                _log("circuit reset")
        except RuntimeError as exc:
            _log(str(exc))
        return 0
    try:
        with exclusive_lock(args.lock):
            _log(f"decision={run_once(args.config, args.state)}")
    except RuntimeError as exc:
        _log(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
