"""One saved group may be classified read-only, never authorized for ACK."""

from uuid import UUID, uuid4

import pytest

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)

from aos_api.pipeline_snapshot_group_witness_classifier import (
    GroupWitnessStatus, classify_group, classify_rows,
)
from aos_api.ec_ingress_journal import _digest
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c8d_original_attempt_receipt_resolver_pg import _factory


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_exact_saved_group_candidate_is_read_only_and_tenant_scoped(chain_case):
    conn, state, analysis, _session, _root, _requirement = chain_case
    run_id = analysis.source.reader._journal._run_id
    group_id = conn.execute("""SELECT group_id FROM pipeline_snapshot_group_member
        WHERE org_id=%s AND project_id=%s AND run_id=%s""",
        (*analysis.scope.key, run_id)).fetchone()["group_id"]
    conn.rollback()
    with _factory(conn, read_only=True)(analysis.scope) as reader:
        assert classify_group(reader, analysis.scope, group_id).status is GroupWitnessStatus.READY_CANDIDATE
        assert classify_group(reader, analysis.scope, uuid4()).status is GroupWitnessStatus.MISSING_GROUP
    with _factory(conn, read_only=True)(TenantScope("dev-org", "dev-project")) as reader:
        assert classify_group(reader, TenantScope("dev-org", "dev-project"),
                              group_id).status is GroupWitnessStatus.MISSING_GROUP
    with _factory(conn, read_only=False)(analysis.scope) as writer:
        with pytest.raises(ValueError, match="READ_ONLY"):
            classify_group(writer, analysis.scope, group_id)
    assert state["calls"] == 1


def test_row_classifier_fails_closed_for_missing_or_drifted_evidence():
    group_id = UUID("00000000-0000-4000-8000-000000000001")
    assert classify_rows(group_id, None, None, ()) is GroupWitnessStatus.MISSING_GROUP
    claim = {"org_id": "org-org", "project_id": "dev-project",
             "binding": {"members": [{"runId": "run-1"}]},
             "request_hash": "sha256:" + "0" * 64,
             "member_count": 1, "actor": "operator"}
    assert classify_rows(group_id, claim, None, ()) is GroupWitnessStatus.MISSING_INPUT
    input_row = {"manifest": {"members": [{"runId": "run-1"}]},
                 "manifest_hash": "sha256:" + "0" * 64,
                 "request_hash": claim["request_hash"]}
    assert classify_rows(group_id, claim, input_row, ((1, "run-1"),)) is GroupWitnessStatus.HASH_DRIFT
    binding = {"schemaVersion": "aos.snapshot-group-claim/v1",
               "orgId": "org-org", "projectId": "dev-project",
               "groupId": str(group_id), "actor": "operator",
               "members": [{"runId": "run-1"}]}
    manifest = {"members": [{"runId": "run-1"}]}
    claim = {"org_id": "org-org", "project_id": "dev-project",
             "binding": binding, "request_hash": "sha256:" + _digest(binding),
             "member_count": 1, "actor": "operator"}
    input_row = {"manifest": manifest, "manifest_hash": "sha256:" + _digest(manifest),
                 "request_hash": claim["request_hash"]}
    assert classify_rows(group_id, claim, input_row, ((1, "run-1"),)) is GroupWitnessStatus.READY_CANDIDATE
    assert classify_rows(group_id, claim, input_row, ((1, "other"),)) is GroupWitnessStatus.MEMBER_DRIFT
    assert classify_rows(group_id, claim, input_row,
                         tuple((n, "run-1") for n in range(1, 14))) is GroupWitnessStatus.MEMBER_DRIFT
