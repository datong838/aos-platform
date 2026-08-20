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
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
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
RECOVERY_OUTCOMES = frozenset(
    {"resumed-progress", "safe-blocked", "completed", "reentry-noop"}
)
TERMINAL_FAILURE_OUTCOMES = frozenset(
    {"paused-failure", "protocol-failed", "outcome-uncertain"}
)
ACK_SCHEMA = "aos-watchdog-recovery-ack/v1"
RECOVERY_PROTOCOL_MARKER = "[WORKSHOP_WATCHDOG_RECOVERY_PROTOCOL]"


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
    latest_work_activity_at: float | None
    post_final_activity: bool
    latest_user_is_watchdog: bool


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


def _response_message_text(record: dict[str, Any]) -> str:
    if record.get("type") != "response_item":
        return ""
    payload = record.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "message":
        return ""
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def inspect_transcript(path: Path) -> TranscriptStatus:
    latest_user_at: float | None = None
    latest_assistant_at: float | None = None
    latest_final_at: float | None = None
    latest_task_started_at: float | None = None
    latest_task_completed_at: float | None = None
    last_activity_at = path.stat().st_mtime
    latest_work_activity_at: float | None = None
    latest_user_is_watchdog = False
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
                latest_user_is_watchdog = (
                    RECOVERY_PROTOCOL_MARKER in _response_message_text(record)
                )
            elif role == "assistant" and ts is not None:
                latest_assistant_at = ts
                if phase in FINAL_PHASES:
                    latest_final_at = ts
                elif phase == "commentary":
                    latest_work_activity_at = ts
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
                    if ts is not None and payload.get("type") in {
                        "reasoning",
                        "custom_tool_call",
                        "custom_tool_call_output",
                        "function_call",
                        "function_call_output",
                    }:
                        latest_work_activity_at = ts
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
    post_final_activity = (
        latest_final_at is not None
        and latest_work_activity_at is not None
        and latest_work_activity_at > latest_final_at
    )
    active = post_final_activity or (latest_user_at is not None and (
        latest_final_at is None or latest_final_at < latest_user_at
    ))
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
        latest_work_activity_at,
        post_final_activity,
        latest_user_is_watchdog,
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


def _config_revision(config: dict[str, Any]) -> str:
    explicit = config.get("config_revision")
    if isinstance(explicit, str) and explicit:
        return explicit
    relevant = {
        key: config.get(key)
        for key in (
            "thread_id",
            "project_root",
            "expected_branch",
            "sandbox_mode",
            "network_access",
            "writable_roots",
            "resume_prompt",
            "retry_schedule_seconds",
            "max_transport_failures",
            "dependency_watch",
            "fact_watch",
            "blocked_recheck_watch",
        )
    }
    payload = json.dumps(relevant, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _ack_path(config: dict[str, Any]) -> Path:
    configured = config.get("ack_path")
    if not isinstance(configured, str) or not configured:
        raise RuntimeError("ack_path is required")
    return Path(configured)


def _remove_stale_ack(config: dict[str, Any]) -> None:
    path = _ack_path(config)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _git_head(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _git_value(project_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _current_branch(project_root: Path) -> str | None:
    return _git_value(project_root, "branch", "--show-current")


def _git_common_dir(project_root: Path) -> Path | None:
    value = _git_value(project_root, "rev-parse", "--git-common-dir")
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def _probe_writable(path: Path) -> tuple[bool, str]:
    if not path.is_dir():
        return False, "missing-directory"
    probe_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".aos-watchdog-probe-", dir=path, delete=False
        ) as handle:
            probe_path = Path(handle.name)
            handle.write(b"probe")
        os.chmod(probe_path, 0o600)
        probe_path.unlink()
        return True, "writable"
    except OSError as exc:
        if probe_path is not None:
            with contextlib.suppress(OSError):
                probe_path.unlink()
        return False, f"{type(exc).__name__}:{exc.errno}"


def _probe_loopback() -> tuple[bool, str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
        return True, "loopback-bind-ok"
    except OSError as exc:
        return False, f"{type(exc).__name__}:{exc.errno}"


def permission_preflight(config: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(str(config["project_root"]))
    checks: dict[str, dict[str, Any]] = {}
    roots = [project_root]
    roots.extend(Path(item) for item in config.get("writable_roots", []))
    common_dir = _git_common_dir(project_root)
    if common_dir is not None and common_dir not in roots:
        roots.append(common_dir)
    for index, root in enumerate(roots):
        ok, detail = _probe_writable(root)
        checks[f"writable_root_{index}"] = {
            "path": str(root),
            "ok": ok,
            "detail": detail,
        }
    network_ok, network_detail = _probe_loopback()
    checks["loopback_network"] = {
        "path": "127.0.0.1:ephemeral",
        "ok": network_ok,
        "detail": network_detail,
    }
    return {
        "status": "GREEN" if all(item["ok"] for item in checks.values()) else "BLOCKED",
        "checks": checks,
        "git_common_dir": str(common_dir) if common_dir is not None else None,
    }


def _authority_revision(config: dict[str, Any]) -> str | None:
    raw = config.get("authority_path")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        text = Path(raw).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, dict) and isinstance(value.get("project_revision"), str):
        return value["project_revision"]
    match = re.search(r"^\s*\"?project_revision\"?\s*[:=]\s*\"?([^\"\s,]+)", text, re.MULTILINE)
    return match.group(1) if match else None


def record_recovery_ack(
    config_path: Path,
    state_path: Path,
    *,
    episode_id: str,
    outcome: str,
    task_id: str,
    next_task: str | None,
    reason_code: str,
    blocker_fingerprint: str | None,
    evidence_refs: list[str],
) -> dict[str, Any]:
    config = _load_json(config_path, {})
    state = _load_json(state_path, {})
    if not config or state.get("recovery_episode_id") != episode_id:
        raise RuntimeError("ack episode is not current")
    if outcome not in RECOVERY_OUTCOMES:
        raise RuntimeError("invalid recovery outcome")
    if not task_id or not reason_code or not evidence_refs:
        raise RuntimeError("task_id, reason_code and evidence_refs are required")
    if outcome in {"safe-blocked", "reentry-noop"} and not blocker_fingerprint:
        raise RuntimeError("blocked outcomes require blocker_fingerprint")
    preflight = permission_preflight(config)
    if outcome in {"resumed-progress", "completed"} and preflight["status"] != "GREEN":
        raise RuntimeError("progress outcome requires GREEN permission preflight")
    project_root = Path(str(config["project_root"]))
    ack = {
        "schema": ACK_SCHEMA,
        "episode_id": episode_id,
        "thread_id": str(config["thread_id"]),
        "project_root": str(project_root),
        "expected_branch": str(config.get("expected_branch", "")),
        "actual_branch": _current_branch(project_root),
        "outcome": outcome,
        "permission_status": preflight["status"],
        "permission_preflight": preflight,
        "authority_revision": _authority_revision(config),
        "head_before": state.get("episode_head_before"),
        "head_after": _git_head(project_root),
        "task_id": task_id,
        "next_task": next_task,
        "reason_code": reason_code,
        "blocker_fingerprint": blocker_fingerprint,
        "evidence_refs": evidence_refs,
        "written_at": time.time(),
    }
    _write_json(_ack_path(config), ack)
    return ack


def resume_command(
    config: dict[str, Any], *, episode_id: str | None = None
) -> list[str]:
    command = [
        str(config.get("codex_path", DEFAULT_CODEX)),
        "exec",
    ]
    project_root = str(config["project_root"])
    command.extend(["--cd", project_root])
    sandbox_mode = str(config.get("sandbox_mode", "workspace-write"))
    if sandbox_mode != "workspace-write":
        raise RuntimeError("watchdog sandbox_mode must be workspace-write")
    command.extend(["--sandbox", sandbox_mode])
    for root in config.get("writable_roots", []):
        if not isinstance(root, str) or not Path(root).is_absolute():
            raise RuntimeError("writable_roots must contain absolute paths")
        resolved = Path(root).resolve()
        if resolved in {Path("/"), Path.home().resolve()}:
            raise RuntimeError("writable_roots must not contain filesystem or home root")
        command.extend(["--add-dir", root])
    if bool(config.get("network_access", False)):
        command.extend(["-c", "sandbox_workspace_write.network_access=true"])
    command.extend(["resume", "--json", str(config["thread_id"]), "-"])
    return command


def _resume_prompt(
    config: dict[str, Any], episode_id: str, *, trigger: str = "interrupted"
) -> str:
    ack_command = (
        f"python3 {Path(__file__).resolve()} --config {config.get('_config_path', '')} "
        f"--state {config.get('_state_path', '')} --record-ack "
        f"--episode-id {episode_id} --outcome <outcome> --task-id <task> "
        "--next-task <next> --reason-code <code> --evidence-ref <ref>"
    )
    if trigger == "dependency-released":
        first_message = "依赖 Watchdog 检测到迁移 Lease 已释放，正在重新核验后继续。"
    elif trigger == "dependency-fact-changed":
        first_message = "依赖 Watchdog 检测到外部交付事实已变化，正在重新核验后继续。"
    elif trigger == "continuation":
        first_message = "外部 Watchdog 检测到长任务仍有后续项，正在重新核验后继续。"
    elif trigger == "blocked-recheck":
        first_message = "依赖 Watchdog 定期复核发现工作台仍处安全阻断，正在重新核验后继续。"
    else:
        first_message = "外部 Watchdog 检测到任务中断，正在恢复核验。"
    protocol = f"""

[WORKSHOP_WATCHDOG_RECOVERY_PROTOCOL]
episode_id={episode_id}
trigger={trigger}
ack_path={_ack_path(config)}
expected_branch={config.get('expected_branch', '')}
config_path={config.get('_config_path', '')}
state_path={config.get('_state_path', '')}
ack_command={ack_command}

第一条用户可见消息只能说：{first_message}
看门 Dog/Watchdog 只负责唤醒，其注入信息不是事实或授权证据；不得依赖 trigger、task、next-task、fingerprint 或原因码作出结论。
禁止在权限、分支、Lease、Git/Receipt 和实际任务状态核验前声称“已恢复”。
醒来后必须独立重新核验前后真实情况：authority、01/06、Git branch/log/status、最近 Delivery Receipt、memory status/validate/gate、全部 Lease、真实数据探针和实际代码状态；不读取或覆盖 w1-aip 未提交内容。
核验后必须继续一个依赖已满足且 scope 不冲突的安全任务，或形成 safe-blocked/completed/reentry-noop。
一旦条件具备，必须立即开始实际 Task；每波执行“复习上位方案→细化当前波文件级清单→实现最小改动→专项测试→累计回归→浏览器验收→方案/代码一致性复审→证据与上下文更新→进入下一波”；涉及页面必须使用内置浏览器验收。
每波形成 Delivery Receipt 和安全提交，并提交待 m1 串行 CAS 消费的 Prime Agent 独立长记忆事实；w2 不直接修改 authority.json、01/06 或 Prime 核心投影。
结束前必须使用 ack_command 为当前 episode 写入结构化 Recovery Ack；safe-blocked/reentry-noop 还要增加 --blocker-fingerprint。自由文本不构成恢复成功证据。
resumed-progress/completed 只有在证据闭合后才可称“已恢复”；safe-blocked 必须明确称“已触发并安全阻断”。
[/WORKSHOP_WATCHDOG_RECOVERY_PROTOCOL]
"""
    return str(config["resume_prompt"]).rstrip() + protocol


def resume_once(
    config: dict[str, Any],
    episode_id: str,
    *,
    trigger: str = "interrupted",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    prompt = _resume_prompt(config, episode_id, trigger=trigger)
    return runner(
        resume_command(config, episode_id=episode_id),
        input=prompt,
        text=True,
        capture_output=True,
        cwd=config["project_root"],
        env=_sanitized_environment(),
        timeout=int(config.get("resume_timeout_seconds", 14_400)),
        check=False,
    )


def _read_ack(config: dict[str, Any]) -> dict[str, Any] | None:
    path = _ack_path(config)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _validate_ack(
    config: dict[str, Any],
    ack: dict[str, Any],
    *,
    episode_id: str,
    attempt_started_at: float,
) -> tuple[bool, str]:
    exact = {
        "schema": ACK_SCHEMA,
        "episode_id": episode_id,
        "thread_id": str(config["thread_id"]),
        "project_root": str(config["project_root"]),
        "expected_branch": str(config.get("expected_branch", "")),
    }
    for key, expected in exact.items():
        if ack.get(key) != expected:
            return False, f"ack {key} mismatch"
    written_at = ack.get("written_at")
    if not isinstance(written_at, (int, float)) or written_at < attempt_started_at:
        return False, "ack is stale"
    outcome = ack.get("outcome")
    if outcome not in RECOVERY_OUTCOMES:
        return False, "ack outcome invalid"
    actual_branch = ack.get("actual_branch")
    expected_branch = config.get("expected_branch")
    if outcome in {"resumed-progress", "completed"} and actual_branch != expected_branch:
        return False, "progress outcome branch mismatch"
    if outcome in {"resumed-progress", "completed"} and ack.get("permission_status") != "GREEN":
        return False, "progress outcome permission preflight not GREEN"
    if not isinstance(ack.get("task_id"), str) or not ack["task_id"]:
        return False, "ack task_id missing"
    evidence_refs = ack.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs or not all(
        isinstance(item, str) and item for item in evidence_refs
    ):
        return False, "ack evidence_refs missing"
    if outcome in {"safe-blocked", "reentry-noop"} and not ack.get(
        "blocker_fingerprint"
    ):
        return False, "blocked outcome fingerprint missing"
    if not isinstance(ack.get("reason_code"), str) or not ack["reason_code"]:
        return False, "ack reason_code missing"
    return True, "valid"


def _record_terminal_outcome(
    state: dict[str, Any],
    *,
    config: dict[str, Any],
    outcome: str,
    final_at: float | None,
    ack: dict[str, Any] | None,
    resolved_at: float,
    latest_user_at: float | None,
) -> None:
    state.update(
        {
            "consecutive_failures": 0,
            "next_retry_at": 0,
            "retry_delay_seconds": 0,
            "last_recovery_outcome": outcome,
            "last_decision": outcome,
            "visible_ack_at": final_at,
            "last_resolved_at": resolved_at,
            "last_ack": ack,
            "last_error": None,
        }
    )
    state["last_recovered_at"] = (
        resolved_at if outcome in {"resumed-progress", "completed"} else None
    )
    continuation = config.get("continuation_watch")
    continuation_enabled = False
    continuation_delay = 300
    if continuation is not None:
        if not isinstance(continuation, dict):
            raise RuntimeError("continuation_watch must be an object")
        continuation_enabled = bool(continuation.get("enabled", False))
        continuation_delay = continuation.get("delay_seconds", 300)
        if (
            not isinstance(continuation_delay, int)
            or isinstance(continuation_delay, bool)
            or continuation_delay <= 0
        ):
            raise RuntimeError(
                "continuation_watch delay_seconds must be a positive integer"
            )
    next_task = ack.get("next_task") if isinstance(ack, dict) else None
    should_continue = (
        outcome == "resumed-progress"
        and continuation_enabled
        and isinstance(next_task, str)
        and bool(next_task.strip())
        and next_task.strip().upper() not in {"NONE", "COMPLETED"}
    )
    if should_continue:
        state.update(
            {
                "continuation_armed": True,
                "continuation_source_episode_id": state.get("recovery_episode_id"),
                "continuation_next_task": next_task.strip(),
                "continuation_ack_at": ack.get("written_at"),
                "continuation_ready_at": resolved_at + continuation_delay,
                "continuation_user_cutoff_at": latest_user_at,
                "continuation_disarm_reason": None,
            }
        )
    else:
        state["continuation_armed"] = False
        state["continuation_disarm_reason"] = outcome
    blocked_recheck_enabled, blocked_recheck_delay = _blocked_recheck_settings(
        config
    )
    should_recheck = (
        outcome == "safe-blocked"
        and blocked_recheck_enabled
        and isinstance(ack, dict)
        and isinstance(ack.get("blocker_fingerprint"), str)
        and bool(ack["blocker_fingerprint"].strip())
    )
    if should_recheck:
        state.update(
            {
                "blocked_recheck_armed": True,
                "blocked_recheck_source_episode_id": state.get("recovery_episode_id"),
                "blocked_recheck_task_id": ack.get("task_id"),
                "blocked_recheck_blocker_fingerprint": ack[
                    "blocker_fingerprint"
                ].strip(),
                "blocked_recheck_ready_at": resolved_at + blocked_recheck_delay,
                "blocked_recheck_armed_at": resolved_at,
                "blocked_recheck_disarm_reason": None,
            }
        )
    else:
        state["blocked_recheck_armed"] = False
        state["blocked_recheck_disarm_reason"] = outcome
    if state.get("episode_trigger") == "dependency-released":
        state["dependency_wait_armed"] = False
        state["dependency_release_resolved_at"] = resolved_at


def _log(message: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    print(f"{now} {message}", flush=True)


def _retry_delay_seconds(config: dict[str, Any], failure_count: int) -> int:
    raw = config.get(
        "retry_schedule_seconds", [300, 600, 900, 1800, 3600, 7200]
    )
    if (
        not isinstance(raw, list)
        or not raw
        or any(
            not isinstance(item, int) or isinstance(item, bool) or item <= 0
            for item in raw
        )
    ):
        raise RuntimeError(
            "retry_schedule_seconds must be a non-empty list of positive integers"
        )
    return raw[min(max(failure_count, 1) - 1, len(raw) - 1)]


def _blocked_recheck_settings(config: dict[str, Any]) -> tuple[bool, int]:
    raw = config.get("blocked_recheck_watch")
    if raw is None:
        return False, 1800
    if not isinstance(raw, dict):
        raise RuntimeError("blocked_recheck_watch must be an object")
    delay = raw.get("delay_seconds", 1800)
    if (
        not isinstance(delay, int)
        or isinstance(delay, bool)
        or delay <= 0
    ):
        raise RuntimeError(
            "blocked_recheck_watch delay_seconds must be a positive integer"
        )
    return bool(raw.get("enabled", False)), delay


def _dependency_scope_overlaps(watched: str, leased: str) -> bool:
    if watched == leased:
        return True
    if "/" not in watched or "/" not in leased:
        return False
    watched_path = watched.rstrip("/")
    leased_path = leased.rstrip("/")
    if not watched_path or not leased_path:
        return False
    return (
        leased_path.startswith(watched_path + "/")
        or watched_path.startswith(leased_path + "/")
    )


def _dependency_blockers(config: dict[str, Any], *, now: float) -> list[dict[str, Any]]:
    raw = config.get("dependency_watch")
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise RuntimeError("dependency_watch must be an object")
    if not raw.get("enabled", False):
        return []
    leases_path = raw.get("leases_path")
    scope_tokens = raw.get("scope_tokens")
    ignore_task_ids = raw.get("ignore_task_ids", [])
    if not isinstance(leases_path, str) or not Path(leases_path).is_absolute():
        raise RuntimeError("dependency_watch leases_path must be absolute")
    if (
        not isinstance(scope_tokens, list)
        or not scope_tokens
        or not all(isinstance(item, str) and item for item in scope_tokens)
    ):
        raise RuntimeError("dependency_watch scope_tokens must be non-empty strings")
    if not isinstance(ignore_task_ids, list) or not all(
        isinstance(item, str) and item for item in ignore_task_ids
    ):
        raise RuntimeError("dependency_watch ignore_task_ids must be strings")
    try:
        payload = json.loads(Path(leases_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"dependency_watch leases unavailable: {type(exc).__name__}") from exc
    leases = payload.get("leases") if isinstance(payload, dict) else None
    if not isinstance(leases, list):
        raise RuntimeError("dependency_watch leases payload is invalid")
    ignored = set(ignore_task_ids)
    blockers: list[dict[str, Any]] = []
    for lease in leases:
        if not isinstance(lease, dict) or lease.get("status") != "ACTIVE":
            continue
        task_id = lease.get("task_id")
        if not isinstance(task_id, str) or task_id in ignored:
            continue
        scopes = lease.get("scope")
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            raise RuntimeError("dependency_watch active lease scope is invalid")
        expiry_raw = lease.get("lease_expires_at")
        expiry = _timestamp(expiry_raw)
        if expiry is None:
            raise RuntimeError("dependency_watch active lease expiry is invalid")
        if expiry <= now:
            continue
        matched = sorted(
            token
            for token in scope_tokens
            if any(_dependency_scope_overlaps(token, scope) for scope in scopes)
        )
        if not matched:
            continue
        blockers.append(
            {
                "task_id": task_id,
                "owner": lease.get("owner"),
                "scope_tokens": matched,
                "lease_expires_at": expiry_raw,
            }
        )
    return sorted(blockers, key=lambda item: item["task_id"])


def _dependency_fingerprint(blockers: list[dict[str, Any]]) -> str:
    encoded = json.dumps(blockers, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _fact_file_hash(path: Path, *, max_file_bytes: int) -> str:
    if path.is_symlink():
        raise RuntimeError("fact_watch symbolic links are forbidden")
    if not path.is_file():
        raise RuntimeError(f"fact_watch path is not a regular file: {path}")
    size = path.stat().st_size
    if size > max_file_bytes:
        raise RuntimeError(f"fact_watch file exceeds max_file_bytes: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fact_fingerprint(config: dict[str, Any]) -> str | None:
    raw = config.get("fact_watch")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise RuntimeError("fact_watch must be an object")
    if not raw.get("enabled", False):
        return None
    paths = raw.get("paths", [])
    probes = raw.get("probes", [])
    if not isinstance(paths, list) or not all(
        isinstance(item, str) and item for item in paths
    ):
        raise RuntimeError("fact_watch paths must be strings")
    if not isinstance(probes, list):
        raise RuntimeError("fact_watch probes must be a list")
    if not paths and not probes:
        raise RuntimeError("fact_watch requires paths or probes")
    max_files = raw.get("max_files", 10_000)
    max_file_bytes = raw.get("max_file_bytes", 16 * 1024 * 1024)
    if (
        not isinstance(max_files, int)
        or isinstance(max_files, bool)
        or max_files <= 0
        or not isinstance(max_file_bytes, int)
        or isinstance(max_file_bytes, bool)
        or max_file_bytes <= 0
    ):
        raise RuntimeError("fact_watch limits must be positive integers")
    records: list[tuple[str, str]] = []
    for raw_path in sorted(set(paths)):
        path = Path(raw_path)
        if not path.is_absolute():
            raise RuntimeError("fact_watch paths must be absolute")
        if path.is_symlink():
            raise RuntimeError("fact_watch symbolic links are forbidden")
        if path.is_file():
            records.append((raw_path, _fact_file_hash(path, max_file_bytes=max_file_bytes)))
            if len(records) > max_files:
                raise RuntimeError("fact_watch exceeds max_files")
            continue
        if not path.is_dir():
            raise RuntimeError(f"fact_watch path is unavailable: {path}")
        for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
            if child.is_symlink():
                raise RuntimeError("fact_watch symbolic links are forbidden")
            if child.is_dir():
                continue
            relative = child.relative_to(path).as_posix()
            records.append(
                (
                    f"{raw_path}/{relative}",
                    _fact_file_hash(child, max_file_bytes=max_file_bytes),
                )
            )
            if len(records) > max_files:
                raise RuntimeError("fact_watch exceeds max_files")
    records.extend(_fact_probe_records(config, probes))
    encoded = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _fact_probe_records(
    config: dict[str, Any], probes: list[object]
) -> list[tuple[str, str]]:
    project_root = Path(str(config["project_root"])).resolve()
    records: list[tuple[str, str]] = []
    names: set[str] = set()
    for raw_probe in probes:
        if not isinstance(raw_probe, dict):
            raise RuntimeError("fact_watch probe must be an object")
        name = raw_probe.get("name")
        argv = raw_probe.get("argv")
        cwd_raw = raw_probe.get("cwd", str(project_root))
        timeout_seconds = raw_probe.get("timeout_seconds", 30)
        max_output_bytes = raw_probe.get("max_output_bytes", 64 * 1024)
        if not isinstance(name, str) or not name or name in names:
            raise RuntimeError("fact_watch probe names must be unique non-empty strings")
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(item, str) and item for item in argv)
        ):
            raise RuntimeError("fact_watch probe argv must be non-empty strings")
        executable = Path(argv[0])
        if not executable.is_absolute() or not executable.exists():
            raise RuntimeError("fact_watch probe executable must be an existing absolute path")
        cwd = Path(cwd_raw) if isinstance(cwd_raw, str) else Path("")
        if not cwd.is_absolute() or not cwd.is_dir():
            raise RuntimeError("fact_watch probe cwd must be an existing absolute directory")
        resolved_cwd = cwd.resolve()
        if not resolved_cwd.is_relative_to(project_root):
            raise RuntimeError("fact_watch probe cwd must stay within project_root")
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 60
            or not isinstance(max_output_bytes, int)
            or isinstance(max_output_bytes, bool)
            or not 1 <= max_output_bytes <= 1024 * 1024
        ):
            raise RuntimeError("fact_watch probe limits are invalid")
        try:
            completed = subprocess.run(
                argv,
                cwd=resolved_cwd,
                env=_sanitized_environment(),
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                f"fact_watch probe failed: {name}:{type(exc).__name__}"
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(f"fact_watch probe exited nonzero: {name}")
        stdout = completed.stdout
        if not isinstance(stdout, bytes):
            stdout = str(stdout).encode("utf-8")
        if not stdout or len(stdout) > max_output_bytes:
            raise RuntimeError(f"fact_watch probe output is empty or too large: {name}")
        try:
            stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"fact_watch probe output is not utf-8: {name}") from exc
        names.add(name)
        records.append((f"probe:{name}", hashlib.sha256(stdout).hexdigest()))
    return sorted(records)


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
    if state.get("last_recovery_outcome") in TERMINAL_FAILURE_OUTCOMES:
        paused_user_at = state.get("paused_user_at")
        same_user = (
            isinstance(paused_user_at, (int, float))
            and status.latest_user_at is not None
            and status.latest_user_at <= paused_user_at
        )
        same_config = state.get("paused_config_revision") == _config_revision(config)
        if same_user and same_config:
            return str(state["last_recovery_outcome"]), status
    if not status.active:
        return "idle", status
    turn_silence_limit = int(
        config.get(
            "max_turn_silence_seconds",
            config.get("max_tool_silence_seconds", 300),
        )
    )
    if turn_silence_limit <= 0:
        raise RuntimeError("max_turn_silence_seconds must be positive")
    dependency_watch_enabled = bool(
        isinstance(config.get("dependency_watch"), dict)
        and config["dependency_watch"].get("enabled", False)
    )
    fact_watch_enabled = bool(
        isinstance(config.get("fact_watch"), dict)
        and config["fact_watch"].get("enabled", False)
    )
    blocked_recheck_enabled = bool(
        isinstance(config.get("blocked_recheck_watch"), dict)
        and config["blocked_recheck_watch"].get("enabled", False)
    )
    if status.turn_running and (
        dependency_watch_enabled
        or fact_watch_enabled
        or blocked_recheck_enabled
        or now - status.last_activity_at < turn_silence_limit
    ):
        return "turn-running", status
    if status.pending_tool_calls and status.oldest_pending_tool_at is not None and (
        now - status.oldest_pending_tool_at
        < int(config.get("max_tool_silence_seconds", 300))
    ):
        return "tool-running", status
    if now - status.last_activity_at < int(config.get("grace_seconds", 240)):
        return "live", status
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
    config["_config_path"] = str(config_path)
    config["_state_path"] = str(state_path)
    state = _load_json(state_path, {})
    rollout_path = Path(config.get("rollout_path") or find_rollout_path(config["thread_id"]))
    current = time.time() if now is None else now
    blocked_recheck_enabled, blocked_recheck_delay = _blocked_recheck_settings(config)
    last_ack = state.get("last_ack")
    bootstrap_blocker = (
        last_ack.get("blocker_fingerprint") if isinstance(last_ack, dict) else None
    )
    if (
        blocked_recheck_enabled
        and state.get("last_recovery_outcome") == "safe-blocked"
        and not bool(state.get("blocked_recheck_armed", False))
        and isinstance(bootstrap_blocker, str)
        and bool(bootstrap_blocker.strip())
    ):
        state.update(
            {
                "blocked_recheck_armed": True,
                "blocked_recheck_source_episode_id": state.get(
                    "recovery_episode_id"
                ),
                "blocked_recheck_task_id": last_ack.get("task_id"),
                "blocked_recheck_blocker_fingerprint": bootstrap_blocker.strip(),
                "blocked_recheck_ready_at": current + blocked_recheck_delay,
                "blocked_recheck_armed_at": current,
                "blocked_recheck_bootstrapped_at": current,
                "blocked_recheck_disarm_reason": None,
            }
        )
    decision, status = evaluate(
        config, state, now=current, rollout_path=rollout_path
    )
    blockers = _dependency_blockers(config, now=current)
    fact_fingerprint = _fact_fingerprint(config)
    previous_fact_fingerprint = state.get("fact_watch_fingerprint")
    fact_changed = (
        fact_fingerprint is not None
        and isinstance(previous_fact_fingerprint, str)
        and fact_fingerprint != previous_fact_fingerprint
    )
    if fact_fingerprint is not None:
        state["fact_watch_fingerprint"] = fact_fingerprint
        state["fact_watch_last_checked_at"] = current
    dependency_armed = bool(state.get("dependency_wait_armed", False))
    if blockers:
        state.update(
            {
                "dependency_wait_armed": True,
                "dependency_blocker_fingerprint": _dependency_fingerprint(blockers),
                "dependency_blocking_task_ids": [item["task_id"] for item in blockers],
                "dependency_last_blocked_at": current,
            }
        )
        if decision not in {
            "turn-running",
            "tool-running",
            "live",
            *TERMINAL_FAILURE_OUTCOMES,
        }:
            decision = "dependency-blocked"
    else:
        state["dependency_blocking_task_ids"] = []
        if dependency_armed and decision in {"idle", "recover"}:
            decision = "dependency-released"
            state["dependency_released_at"] = current
        elif fact_changed and decision in {"idle", "recover"}:
            decision = "dependency-fact-changed"
            state["fact_changed_at"] = current
            state["fact_previous_fingerprint"] = previous_fact_fingerprint
    last_attempt_at = state.get("last_attempt_at")
    manual_reentry = (
        state.get("episode_trigger")
        in {"dependency-released", "dependency-fact-changed"}
        and state.get("last_recovery_outcome") in {"attempting", "transport-failed"}
        and isinstance(last_attempt_at, (int, float))
        and status.latest_user_at is not None
        and status.latest_user_at >= last_attempt_at
        and not status.latest_user_is_watchdog
    )
    if manual_reentry:
        decision = "manual-reentry"
        state.update(
            {
                "consecutive_failures": 0,
                "next_retry_at": 0,
                "retry_delay_seconds": 0,
                "last_recovery_outcome": "reentry-noop",
                "manual_reentry_at": current,
                "last_recovered_at": None,
                "last_error": None,
            }
        )
        if state.get("episode_trigger") == "dependency-released" and not blockers:
            state["dependency_wait_armed"] = False
            state["dependency_release_resolved_at"] = current
    if bool(state.get("continuation_armed", False)):
        cutoff = state.get("continuation_user_cutoff_at")
        user_reentered = (
            isinstance(cutoff, (int, float))
            and status.latest_user_at is not None
            and status.latest_user_at > cutoff
            and not status.latest_user_is_watchdog
        )
        if user_reentered:
            decision = "continuation-manual-reentry"
            state.update(
                {
                    "continuation_armed": False,
                    "continuation_disarm_reason": "manual-reentry",
                    "continuation_manual_reentry_at": current,
                }
            )
        elif (
            not blockers
            and decision == "idle"
            and current >= float(state.get("continuation_ready_at", float("inf")))
        ):
            decision = "continuation"
    if bool(state.get("blocked_recheck_armed", False)):
        if (
            not blockers
            and decision == "idle"
            and current
            >= float(state.get("blocked_recheck_ready_at", float("inf")))
        ):
            decision = "blocked-recheck"
    state["dependency_watch_last_checked_at"] = current
    state.update(
        {
            "last_check_at": current,
            "last_decision": decision,
            "last_activity_at": status.last_activity_at,
            "active_turn_detected": status.active,
            "rollout_path": str(rollout_path),
        }
    )
    if decision not in {
        "recover",
        "dependency-released",
        "dependency-fact-changed",
        "continuation",
        "blocked-recheck",
    }:
        if decision in {"idle", "dependency-blocked"}:
            state["consecutive_failures"] = 0
            state["next_retry_at"] = 0
            state["retry_delay_seconds"] = 0
        _write_json(state_path, state)
        return decision

    max_failures = int(
        config.get(
            "max_transport_failures",
            config.get("max_consecutive_failures", 12),
        )
    )
    if max_failures <= 0:
        raise RuntimeError("max_transport_failures must be positive")
    _retry_delay_seconds(config, max(int(state.get("consecutive_failures", 0)) + 1, 1))

    if state.get("last_recovery_outcome") in TERMINAL_FAILURE_OUTCOMES:
        state.update(
            {
                "consecutive_failures": 0,
                "next_retry_at": 0,
                "retry_delay_seconds": 0,
                "last_recovery_outcome": "attempting",
            }
        )

    failures = int(state.get("consecutive_failures", 0))
    if failures == 0:
        trigger = decision
        state.update(
            {
                "recovery_episode_id": (
                    f"dependency-release-{int(current * 1000)}"
                    if trigger == "dependency-released"
                    else (
                        f"dependency-fact-{int(current * 1000)}"
                        if trigger == "dependency-fact-changed"
                        else (
                            f"continuation-{int(current * 1000)}"
                            if trigger == "continuation"
                            else (
                                f"blocked-recheck-{int(current * 1000)}"
                                if trigger == "blocked-recheck"
                                else f"recovery-{int(current * 1000)}"
                            )
                        )
                    )
                ),
                "episode_trigger": trigger,
                "last_recovery_outcome": "attempting",
                "visible_ack_at": None,
                "last_recovered_at": None,
                "episode_head_before": _git_head(Path(config["project_root"])),
                "episode_config_revision": _config_revision(config),
            }
        )
        if trigger == "continuation":
            state["continuation_armed"] = False
            state["continuation_consumed_at"] = current
            state["continuation_disarm_reason"] = "episode-created"
        if trigger == "blocked-recheck":
            state["blocked_recheck_armed"] = False
            state["blocked_recheck_consumed_at"] = current
            state["blocked_recheck_disarm_reason"] = "episode-created"
    episode_id = str(state["recovery_episode_id"])
    attempts = 1
    for attempt in range(1, attempts + 1):
        before_resume = inspect_transcript(rollout_path)
        _remove_stale_ack(config)
        attempt_started_at = time.time()
        state["last_attempt_at"] = attempt_started_at
        state["total_attempts"] = int(state.get("total_attempts", 0)) + 1
        _write_json(state_path, state)
        _log(f"resume attempt {attempt}/{attempts} thread={config['thread_id']}")
        try:
            result = resume_once(
                config,
                episode_id,
                trigger=str(state.get("episode_trigger", "interrupted")),
                runner=runner,
            )
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
            ack = _read_ack(config)
            ack_valid = False
            ack_error = "ack missing"
            if ack is not None:
                ack_valid, ack_error = _validate_ack(
                    config,
                    ack,
                    episode_id=episode_id,
                    attempt_started_at=attempt_started_at,
                )
            if ack_valid and visible_final and result.returncode == 0:
                outcome = str(ack["outcome"])
                _record_terminal_outcome(
                    state,
                    config=config,
                    outcome=outcome,
                    final_at=after_resume.latest_final_at,
                    ack=ack,
                    resolved_at=current,
                    latest_user_at=after_resume.latest_user_at,
                )
                _write_json(state_path, state)
                return outcome
            if visible_final and not ack_valid:
                _record_terminal_outcome(
                    state,
                    config=config,
                    outcome="protocol-failed",
                    final_at=after_resume.latest_final_at,
                    ack=ack,
                    resolved_at=current,
                    latest_user_at=after_resume.latest_user_at,
                )
                state["last_error"] = ack_error
                state["paused_user_at"] = after_resume.latest_user_at
                state["paused_config_revision"] = _config_revision(config)
                _write_json(state_path, state)
                return "protocol-failed"
            if ack_valid and (not visible_final or result.returncode != 0):
                _record_terminal_outcome(
                    state,
                    config=config,
                    outcome="outcome-uncertain",
                    final_at=after_resume.latest_final_at if visible_final else None,
                    ack=ack,
                    resolved_at=current,
                    latest_user_at=after_resume.latest_user_at,
                )
                state["last_error"] = "current episode ack exists without clean visible final"
                state["paused_user_at"] = after_resume.latest_user_at
                state["paused_config_revision"] = _config_revision(config)
                _write_json(state_path, state)
                return "outcome-uncertain"
            if result.returncode == 0:
                state["last_error"] = "resume exited 0 without current ack/final"
    state["consecutive_failures"] = failures + attempts
    if state["consecutive_failures"] >= max_failures:
        latest = inspect_transcript(rollout_path)
        state.update(
            {
                "next_retry_at": 0,
                "retry_delay_seconds": 0,
                "last_recovery_outcome": "paused-failure",
                "last_decision": "paused-failure",
                "paused_user_at": latest.latest_user_at,
                "paused_config_revision": _config_revision(config),
                "continuation_armed": False,
                "continuation_disarm_reason": "paused-failure",
                "blocked_recheck_armed": False,
                "blocked_recheck_disarm_reason": "paused-failure",
            }
        )
        if state.get("episode_trigger") == "dependency-released":
            state["dependency_wait_armed"] = False
        _write_json(state_path, state)
        return "paused-failure"
    retry_delay = _retry_delay_seconds(config, state["consecutive_failures"])
    state["retry_delay_seconds"] = retry_delay
    state["next_retry_at"] = current + retry_delay
    state["last_recovery_outcome"] = "transport-failed"
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
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--record-ack", action="store_true")
    parser.add_argument("--episode-id")
    parser.add_argument("--outcome", choices=sorted(RECOVERY_OUTCOMES))
    parser.add_argument("--task-id")
    parser.add_argument("--next-task")
    parser.add_argument("--reason-code")
    parser.add_argument("--blocker-fingerprint")
    parser.add_argument("--evidence-ref", action="append", default=[])
    args = parser.parse_args()
    if args.record_ack:
        required = {
            "episode_id": args.episode_id,
            "outcome": args.outcome,
            "task_id": args.task_id,
            "reason_code": args.reason_code,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            parser.error("record-ack missing: " + ", ".join(missing))
        try:
            ack = record_recovery_ack(
                args.config,
                args.state,
                episode_id=args.episode_id,
                outcome=args.outcome,
                task_id=args.task_id,
                next_task=args.next_task,
                reason_code=args.reason_code,
                blocker_fingerprint=args.blocker_fingerprint,
                evidence_refs=args.evidence_ref,
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        print(json.dumps(ack, ensure_ascii=False, indent=2))
        return 0
    if args.status:
        print(json.dumps(status(args.config, args.state), ensure_ascii=False, indent=2))
        return 0
    if not args.once:
        parser.error("choose --once, --status or --record-ack")
    try:
        with exclusive_lock(args.lock):
            _log(f"decision={run_once(args.config, args.state)}")
    except RuntimeError as exc:
        _log(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
