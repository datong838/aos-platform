#!/usr/bin/env python3
"""Offline, advisory assessment of W5c4r samples; never executes work."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from stat import S_IMODE


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
SAMPLES = PRIVATE / "20260924-w5c4r-natural-observation/samples.jsonl"
ENABLE = PRIVATE / "20260924-w5c4q-natural-enable"


def _frozen(reason: str) -> dict:
    return {"outcome": "FROZEN_ASSESSMENT_BOUNDARY", "reason": reason,
            "automaticAction": False}


def _same_definition(value: dict, result: dict) -> bool:
    head = value["definition"]
    ref = result["ref"]
    return (head["revision"] == ref["revision"] == 3
            and head["state"] == "enabled"
            and head["content_hash"] == ref["contentHash"])


def assess(before: dict, after: dict, intent: dict, result: dict) -> dict:
    """Classify only an exact single natural terminal; never grant authority."""
    try:
        slot = datetime.fromisoformat(intent["nextSlotUtc"])
        if (datetime.fromisoformat(before["observedAt"]) >= slot
                or before["observation"] != "WAITING_FOR_NATURAL_TERMINAL"
                or before["claims"] or before["attempts"]
                or not _same_definition(before, result)
                or not _same_definition(after, result)
                or any(value["workerPid"] != intent["workerPid"]
                       or value["hostPid"] != intent["hostPid"]
                       for value in (before, after))):
            return _frozen("BASELINE_OR_IDENTITY_DIFFERS")
        if after["observation"] == "WAITING_FOR_NATURAL_TERMINAL":
            return {"outcome": "NOT_TERMINAL_NO_ACTION", "automaticAction": False}
        if (datetime.fromisoformat(after["observedAt"]) < slot
                or after["observation"] != "ATTEMPT_FORMAL_TERMINAL"
                or len(after["claims"]) != 1 or len(after["attempts"]) != 1):
            return _frozen("NOT_EXACT_SINGLE_TERMINAL")
        claim = after["claims"][0]
        attempt = after["attempts"][0]
        group_id = claim["group_id"]
        if (not group_id or claim["trigger"] != "cron"
                or datetime.fromisoformat(str(claim["scheduled_for"])) != slot
                or attempt["operation_kind"] != "recoverable_store"
                or not attempt["attempt_id"]
                or attempt["state"] not in {"succeeded", "failed", "abandoned"}):
            return _frozen("NATURAL_CLAIM_OR_ATTEMPT_DIFFERS")
        if any(value["facts"]["routes"] != 9
               or value["facts"]["unpaused_gate"] != 1
               or value["facts"]["schedules_enabled"] != 12
               or value["facts"]["canary"] != 0 for value in (before, after)):
            return _frozen("ROUTING_OR_CANARY_DIFFERS")
        keys = ("store_receipts", "live_links", "projection_pending")
        deltas = {key: after["facts"][key] - before["facts"][key] for key in keys}
        if any(type(value) is not int or value < 0 for value in deltas.values()):
            return _frozen("COUNTER_REGRESSED")
        runs = after["runGroups"]
        if (not runs or any(row["group_id"] != group_id or type(row["n"]) is not int
                            or row["n"] <= 0 for row in runs)
                or sum(row["n"] for row in runs) != 12):
            return _frozen("RUN_GROUP_DIFFERS")
        common = {"automaticAction": False, "groupId": group_id,
                  "attemptId": attempt["attempt_id"],
                  "attemptState": attempt["state"],
                  "terminalReason": attempt["terminal_reason_code"],
                  "storeReceiptDelta": deltas["store_receipts"],
                  "liveLinkDelta": deltas["live_links"],
                  "projectionPendingDelta": deltas["projection_pending"]}
        if attempt["state"] == "succeeded":
            if (attempt["terminal_reason_code"] is None
                    and attempt["terminal_error_type"] is None
                    and all(row["status"] == "succeeded"
                            and row["executor_stopped"] is True
                            and row["finished_at"] is not None for row in runs)
                    and deltas["store_receipts"] == 12
                    and deltas["live_links"] > 0
                    and deltas["projection_pending"] == 0):
                return {**common, "outcome": "SUCCEEDED_REQUIRES_INDEPENDENT_AUDIT"}
            return _frozen("SUCCESS_WITH_INCOMPLETE_EFFECT")
        if attempt["state"] == "failed":
            if (attempt["terminal_reason_code"] == "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED"
                    and attempt["terminal_error_type"] == "IngressJournalConflict"
                    and all(row["status"] == "running"
                            and row["executor_stopped"] is False
                            and row["finished_at"] is None for row in runs)
                    and all(value == 0 for value in deltas.values())):
                return {**common,
                        "outcome": "FAILED_PRESTORE_CANDIDATE_REQUIRES_INDEPENDENT_AUDIT"}
            return _frozen("FAILED_WITH_UNKNOWN_EFFECT")
        return _frozen("ABANDONED_REQUIRES_FORMAL_RECONCILIATION")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return _frozen(type(error).__name__)


def _read_private(path: Path) -> dict:
    if not path.is_file() or S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("W5C4R_PRIVATE_EVIDENCE_REQUIRED")
    return json.loads(path.read_text())


def _samples() -> tuple[dict, dict]:
    if not SAMPLES.is_file() or S_IMODE(SAMPLES.stat().st_mode) != 0o600:
        raise ValueError("W5C4R_PRIVATE_SAMPLES_REQUIRED")
    first = last = None
    with SAMPLES.open() as source:
        for line in source:
            value = json.loads(line)
            if first is None:
                first = value
            last = value
    if first is None or last is None:
        raise ValueError("W5C4R_SAMPLES_EMPTY")
    return first, last


def main() -> int:
    try:
        before, after = _samples()
        value = assess(before, after, _read_private(ENABLE / "intent.json"),
                       _read_private(ENABLE / "result.json"))
    except (OSError, ValueError, TypeError, KeyError) as error:
        value = _frozen(type(error).__name__)
    print(json.dumps(value, ensure_ascii=False))
    return 0 if value["outcome"] in {
        "SUCCEEDED_REQUIRES_INDEPENDENT_AUDIT",
        "FAILED_PRESTORE_CANDIDATE_REQUIRES_INDEPENDENT_AUDIT",
        "NOT_TERMINAL_NO_ACTION",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
