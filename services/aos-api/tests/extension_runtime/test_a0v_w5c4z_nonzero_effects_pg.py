"""Disposable nonzero-effect closure and rollback; no shared business DB."""

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

pytest_plugins = ("test_analysis_snapshot_native_claims_pg",)

from test_pipeline_snapshot_schedule_claim_pg import schedule_group
from test_pipeline_snapshot_schedule_definition_pg import definition_case
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.ec_ingress_journal import _digest
from aos_api.source_read_observation import observed_rows_hash
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner
from aos_api.pipeline_snapshot_stalled_group_closure import StalledSnapshotGroupClosureRequest


@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
@pytest.mark.parametrize("with_empty_input", [False, True])
def test_nonzero_effects_survive_and_mid_update_failure_rolls_back(
        definition_case, stored, with_empty_input):
    conn, definition_owner, args = definition_case
    initial = definition_owner.configure(conn, **args)
    shared = {key: args[key] for key in ("scope", "definition_id", "actor")}
    enabled = definition_owner.transition(conn, **shared, intent="enable",
                                          expected_ref=initial["ref"],
                                          idempotency_key="w5c4z-enable")
    controls = definition_owner._groups._groups._controls
    group_id = str(uuid4())
    slot = conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS slot").fetchone()["slot"]
    schedule_owner = PipelineSnapshotScheduleClaimOwner(controls=controls)
    claim = schedule_owner.claim(conn, scope=args["scope"], group_id=group_id,
                                 actor=args["actor"], scheduled_for=slot, trigger="cron",
                                 bindings=args["bindings"], definition_ref=enabled["ref"])
    members = claim["members"]
    claims = PipelineSourceClaimOwner(controls=controls)
    group_owner = PipelineSnapshotGroupClaimOwner(claims=claims)
    reservation = group_owner.reserve(
        conn, scope=args["scope"], group_id=group_id, actor=args["actor"],
        bindings=tuple((m["controlRef"], m["runId"]) for m in members))
    if with_empty_input:
        run_by_control = {m["controlRef"]["resourceId"]: m["runId"] for m in members}
        current = group_owner._groups.run_current(
            conn, scope=args["scope"], actor=args["actor"],
            refs=tuple(m["controlRef"] for m in members), execute=lambda group: group)
        leaves = []
        for ref, draft, _ in current.members:
            run = run_by_control[ref.resource_id]
            journal = ControlledIngressJournal(
                claims=claims, scope=args["scope"], run_id=run,
                control_ref=ref, actor=args["actor"])
            parent = journal.save_empty_for_running_schedule(
                conn, args["scope"], run_id=run, pipeline_id=draft.pipeline_id,
                source_id=draft.source_id,
                source_revision=draft.source_configuration_ref.resource_id.removeprefix(
                    "source-config-"), pipeline_hash=draft.graph_hash)
            leaves.append({"runId": run, "envelopeHash": _digest(parent),
                           "rowsHash": observed_rows_hash([]), "rowCount": 0})
        manifest = {"members": leaves}
        conn.execute("""INSERT INTO pipeline_snapshot_group_input
            (org_id,project_id,group_id,request_hash,read_started_at,read_completed_at,
             snapshot_basis,manifest_hash,manifest)
            VALUES(%s,%s,%s,%s,clock_timestamp(),clock_timestamp(),
                   'innodb-repeatable-read',%s,%s)""",
                     (*args["scope"].key, group_id, reservation.record.request_hash,
                      "sha256:" + _digest(manifest), Jsonb(manifest)))
        conn.execute("SET CONSTRAINTS complete_snapshot_group IMMEDIATE")
    disabled = definition_owner.transition(conn, **shared, intent="disable",
                                           expected_ref=enabled["ref"],
                                           idempotency_key="w5c4z-disable")
    conn.execute("RESET ROLE")
    run_ids = [m["runId"] for m in members]
    conn.execute("UPDATE meta_schedule_run SET started_at=clock_timestamp()-interval '25 hours' "
                 "WHERE org_id=%s AND project_id=%s AND id=ANY(%s)",
                 (*args["scope"].key, run_ids))
    wire = StalledSnapshotGroupClosureRequest.model_validate({
        "schemaVersion": "aos.pipeline-snapshot.stalled-group-closure/v1",
        "groupId": group_id,
        "originalDefinitionRef": enabled["ref"],
        "currentDisabledDefinitionRef": disabled["ref"],
        "reasonCode": "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS",
        "idempotencyKey": "fixture-w5c4z-" + group_id,
    }).model_dump(mode="json", by_alias=True)
    # Disposable test-only trigger fails after the receipt insert but before the
    # first terminal Run update. The original SQL function remains unchanged.
    conn.execute("""CREATE FUNCTION pg_temp.w5c4z_fail_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF NEW.error_code='STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS' THEN
            RAISE EXCEPTION 'w5c4z injected update failure' USING ERRCODE='P0001';
          END IF;
          RETURN NEW;
        END $$""")
    conn.execute("""CREATE TRIGGER w5c4z_fail_update BEFORE UPDATE ON public.meta_schedule_run
        FOR EACH ROW EXECUTE FUNCTION pg_temp.w5c4z_fail_update()""")
    conn.execute("SET SESSION AUTHORIZATION aos_extension_maintainer")
    conn.execute("SET LOCAL ROLE aos_extension_maintainer")
    with pytest.raises(psycopg.Error) as injected, conn.transaction():
        conn.execute("SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s)",
                     (Jsonb(wire), args["actor"]))
    assert injected.value.sqlstate == "P0001"
    assert conn.execute("SELECT count(*) AS n FROM pipeline_snapshot_stalled_group_closure_receipt "
                        "WHERE group_id=%s", (group_id,)).fetchone()["n"] == 0
    conn.execute("RESET SESSION AUTHORIZATION")
    conn.execute("RESET ROLE")
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run "
                        "WHERE id=ANY(%s) AND status='running'", (run_ids,)).fetchone()["n"] == 12
    conn.execute("DROP TRIGGER w5c4z_fail_update ON public.meta_schedule_run")
    conn.execute("DROP FUNCTION pg_temp.w5c4z_fail_update()")
    conn.execute("SET SESSION AUTHORIZATION aos_extension_maintainer")
    conn.execute("SET LOCAL ROLE aos_extension_maintainer")
    receipt = conn.execute(
        "SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s) AS receipt",
        (Jsonb(wire), args["actor"])).fetchone()["receipt"]
    assert receipt["businessAccepted"] is False
    assert receipt["effectEvidence"]["groupClaimCount"] == 1
    assert receipt["effectEvidence"]["groupMemberCount"] == 12
    assert receipt["effectEvidence"]["sourceClaimCount"] == 12
    assert receipt["effectEvidence"]["groupInputCount"] == int(with_empty_input)
    assert receipt["effectEvidence"]["ingressCommandCount"] == (12 if with_empty_input else 0)
    conn.execute("RESET SESSION AUTHORIZATION")
    conn.execute("RESET ROLE")
    for table, expected in (("pipeline_snapshot_group_claim", 1),
                            ("pipeline_snapshot_group_member", 12)):
        assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE group_id=%s",
                            (group_id,)).fetchone()["n"] == expected
    assert conn.execute("SELECT count(*) AS n FROM pipeline_controlled_source_claim "
                        "WHERE run_id=ANY(%s)", (run_ids,)).fetchone()["n"] == 12
    if with_empty_input:
        assert conn.execute("SELECT count(*) AS n FROM pipeline_snapshot_group_input "
                            "WHERE group_id=%s", (group_id,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM ecommerce_ingress_command "
                            "WHERE run_id=ANY(%s)", (run_ids,)).fetchone()["n"] == 12
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run "
                        "WHERE id=ANY(%s) AND status='failed'", (run_ids,)).fetchone()["n"] == 12
