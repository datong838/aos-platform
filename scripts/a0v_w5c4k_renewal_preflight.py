#!/usr/bin/env python3
"""Dry-check twelve rev2 selection drafts with a 24-hour window, no source read."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from psycopg import Rollback

from a0v_formal_text_model_renewal import database_connect
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection_store import decode_selection_row
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c4f_successor_bindings as bindings
import a0v_w5c4h_disabled_definition as definition
import a0v_w5c4i_natural_timing as timing

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4k-renewal-preflight")


def _wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _write(value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / "material.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def preflight():
    if STATE.exists():
        raise ValueError("W5C4K_MATERIAL_ALREADY_EXISTS")
    if (definition.audit()["outcome"] != "W5C4H_DISABLED_DEFINITION_GREEN"
            or timing.inspect()["budgetRevision"] != 13):
        raise ValueError("W5C4K_DEFINITION_OR_BUDGET_DRIFT")
    runtime = enabled.observe()
    if (runtime["host"]["pid"] != definition._load("intent")["hostPid"]
            or runtime["counts"]["business"] != definition._load("intent")["businessCounts"]
            or runtime["counts"]["canary"] != 0
            or runtime["counts"]["attempts"] != 0
            or not enabled.configured._held(runtime["resources"])):
        raise ValueError("W5C4K_RUNTIME_DRIFT")
    from aos_api.tenant_scope import TenantScope
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    scope = TenantScope("org-org", "dev-project")
    services = prepared._plane().pipeline_control_factory.build(scope)
    expected = {item["pipelineId"]: item for item in
                bindings._load("wave-result")["members"]}
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=24)
    members = []
    with consumer_connection(runtime_worker_connection,
            {"org_id": scope.org_id, "project_id": scope.project_id}) as conn:
        rows = conn.execute("""SELECT DISTINCT ON (pipeline_id) *
          FROM pipeline_source_selection_revision WHERE org_id=%s AND project_id=%s
          AND installation_id=%s AND generation=%s
          ORDER BY pipeline_id,revision DESC""",
          (*scope.key, prepared.registered.INSTALLATION,
           prepared.registered.GENERATION)).fetchall()
        if len(rows) != 12:
            raise ValueError("W5C4K_SELECTION_COUNT_DRIFT")
        for row in rows:
            saved = decode_selection_row(row)
            pipeline = saved.draft.pipeline_id
            if (pipeline not in expected or row["revision"] != 1
                    or saved.ref.content_hash != row["content_hash"]):
                raise ValueError("W5C4K_PREDECESSOR_DRIFT")
            draft = _wire(saved.draft)
            draft["notBefore"], draft["expiresAt"] = now.isoformat(), end.isoformat()
            candidate = PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft))
            members.append({"pipelineId": pipeline,
                "draft": _wire(candidate), "previousRef": _wire(saved.ref)})
        checked = []
        try:
            with conn.transaction():
                for item in members:
                    candidate = PipelineSourceSelectionDraft.model_validate_json(
                        json.dumps(item["draft"]))
                    services.selections._guarded(conn, candidate, prepared.ACTOR,
                                                 lambda _compiled: True, snapshot=True)
                    checked.append(item["pipelineId"])
                raise Rollback()
        except Rollback:
            pass
    if len(members) != 12 or len(checked) != 12:
        raise ValueError("W5C4K_DRY_CHECK_INCOMPLETE")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        running = conn.execute("""SELECT count(*) AS n FROM meta_schedule_run
          WHERE org_id='org-org' AND project_id='dev-project'
          AND schedule_id=ANY(%s) AND (status='running' OR executor_stopped IS NOT TRUE)""",
          ([m["scheduleId"] for m in definition._load("intent")["members"]],)).fetchone()["n"]
    if running:
        raise ValueError("W5C4K_UNRESOLVED_RUNS")
    _write({"checkedAt": now.isoformat(), "notBefore": now.isoformat(),
            "expiresAt": end.isoformat(), "members": members,
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]})
    return {"outcome": "W5C4K_TWELVE_RENEWAL_DRAFTS_GREEN", "members": 12,
            "dryChecked": 12, "notBefore": now.isoformat(),
            "expiresAt": end.isoformat(), "runningRuns": 0,
            "sourceRowsRead": 0, "databaseWrites": 0,
            "hostPid": runtime["host"]["pid"]}


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False, default=str))
