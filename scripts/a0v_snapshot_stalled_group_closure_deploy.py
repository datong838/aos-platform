#!/usr/bin/env python3
"""Back up and deploy only a0v091 (stalled group closure) to the A0-V recovery database."""
from __future__ import annotations

import json

import a0v_snapshot_prior_recovery_anchor_deploy as deploy


deploy.STATE = deploy.ROOT.parent / ".aos-recovery-20260920/state/snapshot-stalled-group-closure-deploy"
deploy.SOURCE = "a0v_090"
deploy.TARGET = "a0v_091"
deploy.MIGRATION = deploy.ROOT / "services/aos-api/alembic/versions/a0v_091_snapshot_stalled_group_closure.py"
# 091 is additive: new receipt table + functions + triggers; must not touch authority rows.
deploy.TABLES = (
    'pipeline_snapshot_schedule_definition_revision', 'pipeline_snapshot_schedule_definition_head',
    'pipeline_snapshot_group_recovery_receipt', 'pipeline_snapshot_schedule_claim',
    'pipeline_snapshot_schedule_member', 'meta_schedule_run', 'meta_schedule')


def verify(conn):
    version = deploy.storage.version(conn)
    definition = conn.execute(
        "SELECT pg_get_functiondef('public.pipeline_snapshot_stalled_group_close_a0v_091(jsonb,text)'::regprocedure) AS body"
    ).fetchone()["body"]
    markers = (
        "twelve stalled disabled schedule runs older than 24h required",
        "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS",
        "pipeline_snapshot_stalled_group_closure_receipt",
    )
    if version != [deploy.TARGET] or any(marker not in definition for marker in markers):
        raise ValueError("a0v091 stalled closure function readback differs")
    trigger = conn.execute(
        "SELECT count(*) AS n FROM information_schema.triggers"
        " WHERE event_object_table='meta_schedule_run' AND trigger_name='snapshot_stalled_group_terminal'"
    ).fetchone()["n"]
    if trigger != 2:
        raise ValueError("a0v091 stalled terminal trigger missing")
    return {"version": version, "stalledClosureFunctionBound": True, "terminalTriggerEvents": trigger}


deploy.verify = verify


if __name__ == "__main__":
    print(json.dumps(deploy.apply(), ensure_ascii=False, indent=2, default=str))
