#!/usr/bin/env python3
"""Cursor session Dog: wake only on stop / fail / interrupt.

This process is independent of the agent's own Loop. While the agent is
working or looping and refreshing its heartbeat, the Dog stays silent.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "aos-cursor-session-dog/v1"
SENTINEL = "AGENT_LOOP_WAKE_aip_dog"
DEFAULT_HOME = Path.home() / ".cursor" / "aip-session-dog"
GRACE_SECONDS = 60
STOP_WAKE_SECONDS = 90
POLL_SECONDS = 15
WAKE_PROMPT = (
    "Cursor session dog 检测到停掉/失败/中断，正在恢复核验。"
    "读 authority.json next_gate，不要等批准。这是 Dog 唤醒，不是 Loop tick。"
    "若心跳已重新变成 working/looping，立即写 reentry-noop 并退出，不要和前台 Loop 抢跑。"
)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _fingerprint(heartbeat: dict[str, Any]) -> str:
    return ":".join(
        [
            str(heartbeat.get("updated_at") or ""),
            str(heartbeat.get("next_gate") or ""),
            str(heartbeat.get("status") or ""),
        ]
    )


def decide_wake(
    *,
    heartbeat: dict[str, Any] | None,
    now: datetime,
    last_wake_fingerprint: str | None = None,
) -> dict[str, Any]:
    if heartbeat is None:
        return {"wake": False, "reason": "no-heartbeat"}
    status = str(heartbeat.get("status") or "")
    if status == "completed":
        return {"wake": False, "reason": "completed"}
    quiet_until = _parse_time(heartbeat.get("quiet_until"))
    if quiet_until is not None and now < quiet_until:
        return {"wake": False, "reason": "quiet-until"}
    updated = _parse_time(heartbeat.get("updated_at"))
    if updated is None:
        return {"wake": False, "reason": "no-heartbeat"}
    age = (now - updated).total_seconds()
    fingerprint = _fingerprint(heartbeat)
    if last_wake_fingerprint == fingerprint:
        return {
            "wake": False,
            "reason": "already-woke-this-stall",
            "fingerprint": fingerprint,
        }
    if status in {"failed-stopped", "interrupted"}:
        if age >= STOP_WAKE_SECONDS:
            return {
                "wake": True,
                "reason": status,
                "fingerprint": fingerprint,
            }
        return {"wake": False, "reason": "healthy"}
    if status in {"working", "looping"} and age >= GRACE_SECONDS:
        return {
            "wake": True,
            "reason": "stale-heartbeat",
            "fingerprint": fingerprint,
        }
    return {"wake": False, "reason": "healthy"}


def _paths(home: Path) -> dict[str, Path]:
    return {
        "home": home,
        "heartbeat": home / "heartbeat.json",
        "state": home / "state.json",
        "lock": home / "dog.lock",
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def write_heartbeat(
    *,
    status: str,
    next_gate: str,
    home: Path = DEFAULT_HOME,
    quiet_until: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "status": status,
        "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "quiet_until": quiet_until,
        "next_gate": next_gate,
        "note": note,
    }
    _write_json(_paths(home)["heartbeat"], payload)
    return payload


def emit_wake(decision: dict[str, Any]) -> None:
    line = {
        "prompt": WAKE_PROMPT,
        "reason": decision.get("reason"),
        "fingerprint": decision.get("fingerprint"),
    }
    print(
        f"{SENTINEL} {json.dumps(line, ensure_ascii=False, separators=(',', ':'))}",
        flush=True,
    )


def tick(*, home: Path = DEFAULT_HOME, now: datetime | None = None) -> dict[str, Any]:
    paths = _paths(home)
    heartbeat = _read_json(paths["heartbeat"])
    state = _read_json(paths["state"]) or {}
    decision = decide_wake(
        heartbeat=heartbeat,
        now=now or datetime.now(timezone.utc),
        last_wake_fingerprint=state.get("last_wake_fingerprint"),
    )
    if decision.get("wake"):
        emit_wake(decision)
        state["last_wake_fingerprint"] = decision.get("fingerprint")
        state["last_wake_at"] = datetime.now(timezone.utc).isoformat()
        state["last_decision"] = decision.get("reason")
        _write_json(paths["state"], state)
    return decision


def run_loop(*, home: Path = DEFAULT_HOME, poll_seconds: int = POLL_SECONDS) -> None:
    paths = _paths(home)
    paths["home"].mkdir(parents=True, exist_ok=True)
    print(
        json.dumps(
            {
                "status": "dog-running",
                "pollSeconds": poll_seconds,
                "sentinel": SENTINEL,
                "note": "silent while agent Loop/work heartbeat is fresh",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    while True:
        tick(home=home)
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    beat = sub.add_parser("heartbeat")
    beat.add_argument("--status", required=True)
    beat.add_argument("--next-gate", required=True)
    beat.add_argument("--quiet-until")
    beat.add_argument("--note", default="")
    sub.add_parser("run")
    sub.add_parser("tick")
    args = parser.parse_args()
    if args.command == "heartbeat":
        payload = write_heartbeat(
            status=args.status,
            next_gate=args.next_gate,
            quiet_until=args.quiet_until,
            note=args.note,
        )
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if args.command == "tick":
        print(json.dumps(tick(), ensure_ascii=False))
        return 0
    run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
