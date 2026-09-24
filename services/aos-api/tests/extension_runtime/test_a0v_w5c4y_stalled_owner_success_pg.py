"""Disposable 12-Run stalled closure; never connects to the shared business DB."""

from uuid import uuid4

pytest_plugins = ("test_analysis_snapshot_native_claims_pg",)

import psycopg
from psycopg.types.json import Jsonb
import pytest

from test_pipeline_snapshot_schedule_claim_pg import schedule_group
from test_pipeline_snapshot_schedule_definition_pg import definition_case
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner
from aos_api.pipeline_snapshot_stalled_group_closure import StalledSnapshotGroupClosureRequest


@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_original_owner_closes_complete_fixture_and_replays(definition_case, stored):
    conn, definition_owner, args = definition_case
    disabled_initial = definition_owner.configure(conn, **args)
    shared = {key: args[key] for key in ("scope", "definition_id", "actor")}
    enabled = definition_owner.transition(conn, **shared, intent="enable",
                                          expected_ref=disabled_initial["ref"],
                                          idempotency_key="fixture-enable")
    claim_owner = PipelineSnapshotScheduleClaimOwner(
        controls=definition_owner._groups._groups._controls)
    group_id = str(uuid4())
    slot = conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS slot").fetchone()["slot"]
    claim = claim_owner.claim(conn, scope=args["scope"], group_id=group_id,
                              actor=args["actor"], scheduled_for=slot, trigger="cron",
                              bindings=args["bindings"], definition_ref=enabled["ref"])
    assert len(claim["members"]) == 12
    disabled = definition_owner.transition(conn, **shared, intent="disable",
                                           expected_ref=enabled["ref"],
                                           idempotency_key="fixture-disable")
    conn.execute("RESET ROLE")
    run_ids = [m["runId"] for m in claim["members"]]
    conn.execute("UPDATE meta_schedule_run SET started_at=clock_timestamp()-interval '23 hours' "
                 "WHERE org_id=%s AND project_id=%s AND id=ANY(%s)",
                 (*args["scope"].key, run_ids))

    wire = StalledSnapshotGroupClosureRequest.model_validate({
        "schemaVersion": "aos.pipeline-snapshot.stalled-group-closure/v1",
        "groupId": group_id,
        "originalDefinitionRef": enabled["ref"],
        "currentDisabledDefinitionRef": disabled["ref"],
        "reasonCode": "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS",
        "idempotencyKey": "fixture-w5c4y-" + group_id,
    }).model_dump(mode="json", by_alias=True)
    conn.execute("SET SESSION AUTHORIZATION aos_extension_maintainer")
    conn.execute("SET LOCAL ROLE aos_extension_maintainer")

    with pytest.raises(psycopg.Error) as too_early, conn.transaction():
        conn.execute("SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s)",
                     (Jsonb(wire), args["actor"]))
    assert too_early.value.sqlstate == "55000"
    assert conn.execute("SELECT count(*) AS n FROM pipeline_snapshot_stalled_group_closure_receipt "
                        "WHERE group_id=%s", (group_id,)).fetchone()["n"] == 0
    conn.execute("RESET SESSION AUTHORIZATION")
    conn.execute("RESET ROLE")
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run "
                        "WHERE id=ANY(%s) AND status='running'", (run_ids,)).fetchone()["n"] == 12
    conn.execute("UPDATE meta_schedule_run SET started_at=clock_timestamp()-interval '25 hours' "
                 "WHERE org_id=%s AND project_id=%s AND id=ANY(%s)",
                 (*args["scope"].key, run_ids))
    conn.execute("SET SESSION AUTHORIZATION aos_extension_maintainer")
    conn.execute("SET LOCAL ROLE aos_extension_maintainer")
    first = conn.execute(
        "SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s) AS receipt",
        (Jsonb(wire), args["actor"])).fetchone()["receipt"]
    assert first["businessAccepted"] is False
    assert first["runEvidence"]["staleOver24hCount"] == 12
    assert first["replayed"] is False
    second = conn.execute(
        "SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s) AS receipt",
        (Jsonb(wire), args["actor"])).fetchone()["receipt"]
    assert second["replayed"] is True
    assert second["receiptId"] == first["receiptId"]
    drifted = {**wire, "currentDisabledDefinitionRef": enabled["ref"]}
    with pytest.raises(psycopg.Error) as drift, conn.transaction():
        conn.execute("SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s)",
                     (Jsonb(drifted), args["actor"]))
    assert drift.value.sqlstate == "40001"
    conn.execute("RESET SESSION AUTHORIZATION")
    conn.execute("RESET ROLE")
    runs = conn.execute("SELECT status,error_code FROM meta_schedule_run "
                        "WHERE org_id=%s AND project_id=%s AND id=ANY(%s)",
                        (*args["scope"].key, run_ids)).fetchall()
    assert len(runs) == 12
    assert all(row == {"status": "failed", "error_code":
                       "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS"} for row in runs)
    count = conn.execute("SELECT count(*) AS n FROM pipeline_snapshot_stalled_group_closure_receipt "
                         "WHERE org_id=%s AND project_id=%s AND group_id=%s",
                         (*args["scope"].key, group_id)).fetchone()["n"]
    assert count == 1
