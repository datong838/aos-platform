#!/usr/bin/env python3
"""Read-only authority/cron timing for the disabled successor definition."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

from a0v_formal_text_model_renewal import database_connect
from aos_api.qyh_cron_scheduler import cron_matches
import a0v_w5c4h_disabled_definition as definition


def inspect():
    if definition.audit()["outcome"] != "W5C4H_DISABLED_DEFINITION_GREEN":
        raise ValueError("W5C4I_DEFINITION_DRIFT")
    saved = definition._load("result")["body"]
    now = datetime.now(timezone.utc)
    slot = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    next_due = None
    for _ in range(48 * 60):
        if cron_matches(saved["cron"], slot.astimezone(ZoneInfo(saved["timezone"]))):
            next_due = slot
            break
        slot += timedelta(minutes=1)
    if next_due is None:
        raise ValueError("W5C4I_NO_DUE_SLOT_WITHIN_48H")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        budget = conn.execute("""SELECT r.revision,r.effective_from,r.effective_until
          FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r
          ON (r.org_id,r.project_id,r.policy_id,r.revision)=
             (h.org_id,h.project_id,h.policy_id,h.current_revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project'
          AND h.policy_id='a0v-ecommerce-budget-policy-v1'""").fetchone()
    if budget is None:
        raise ValueError("W5C4I_BUDGET_HEAD_MISSING")
    control = json.loads((definition.ROOT.parent / ".aos-recovery-20260920/state/"
        "q-advisor-baseline/20260924-w5c4c-controls-preflight/material.json").read_text())
    starts = [datetime.fromisoformat(m["draft"]["notBefore"].replace("Z", "+00:00"))
              for m in control["members"]]
    ends = [datetime.fromisoformat(m["draft"]["expiresAt"].replace("Z", "+00:00"))
            for m in control["members"]]
    if len(starts) != 12 or len(ends) != 12:
        raise ValueError("W5C4I_CONTROL_COUNT_DRIFT")
    control_covers = max(starts) <= next_due < min(ends)
    budget_covers = budget["effective_from"] <= next_due < budget["effective_until"]
    return {"outcome": "W5C4I_NATURAL_TIMING_READ", "definitionState": saved["state"],
        "cron": saved["cron"], "timezone": saved["timezone"],
        "observedAtUtc": now.isoformat(), "nextDueUtc": next_due.isoformat(),
        "nextDueLocal": next_due.astimezone(ZoneInfo(saved["timezone"])).isoformat(),
        "controlStartUtc": max(starts).isoformat(),
        "controlEndUtc": min(ends).isoformat(), "controlCoversDue": control_covers,
        "budgetRevision": budget["revision"],
        "budgetEndUtc": budget["effective_until"].isoformat(),
        "budgetCoversDue": budget_covers,
        "enableAllowedByTiming": control_covers and budget_covers}


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, default=str))
