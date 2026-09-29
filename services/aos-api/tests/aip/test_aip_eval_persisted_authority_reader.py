"""Test-only PostgreSQL proof for the persisted Eval reader; every seed rolls back."""
from __future__ import annotations

import base64
import hashlib
import os
from datetime import timedelta

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_execution_authority import (
    EvalExecutionRejected, canonical_receipt_bytes, certificate_hash,
)
from aos_api.aip_eval_persisted_authority_reader import read_persisted_execution_pair
from test_aip_eval_execution_authority import (
    ACTUAL_HASH, EXPECTED_HASH, INPUT_HASH, JUDGE, NOW, SUITE, TARGET, TENANT,
    _signed_pair,
)


@pytest.fixture()
def connection():
    dsn = os.getenv("AOS_BG00AB_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("isolated BG-00ab PostgreSQL URL required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "aos_bg00z_acl_20260929"
        assert conn.info.port == 5433
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        yield conn
        conn.rollback()


def _seed(conn, root, target, judge, *, stage="complete", bad_claim=False,
          future_receipt=False, suite_ref=SUITE):
    if stage == "empty":
        return
    root_key = root.public_key
    conn.execute("""INSERT INTO aip_eval_issuer_root
        (org_id,project_id,issuer_id,key_id,purpose,public_key_base64,
         public_key_hash,valid_from,valid_until,owner_ref,approval_ref,source_hash,created_at)
        VALUES (%s,%s,%s,%s,'eval-execution',%s,%s,%s,%s,%s,%s,%s,%s)""",
        (TENANT.org_id,TENANT.project_id,root.issuer_id,root.key_id,
         base64.b64encode(root_key).decode(),hashlib.sha256(root_key).hexdigest(),
         root.not_before,root.not_after,"bg00ab-test-owner",Jsonb({"testOnly": True}),
         "a"*64,NOW-timedelta(hours=2)))
    if stage == "root":
        return
    for cert, _, _ in (target, judge):
        public_key = base64.b64decode(cert.public_key_base64)
        conn.execute("""INSERT INTO aip_eval_executor_identity
            (org_id,project_id,identity_id,purpose,executor_ref,issuer_id,
             issuer_key_id,certificate_json,certificate_hash,public_key_base64,
             public_key_hash,valid_from,valid_until,owner_ref,approval_ref,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (TENANT.org_id,TENANT.project_id,cert.identity_id,cert.purpose,
             Jsonb(cert.executor_ref.model_dump(mode="json",by_alias=True)),
             cert.issuer_id,cert.issuer_key_id,
             Jsonb(cert.model_dump(mode="json",by_alias=True)),certificate_hash(cert),
             cert.public_key_base64,hashlib.sha256(public_key).hexdigest(),
             cert.valid_from,cert.valid_until,"bg00ab-test-owner",
             Jsonb({"testOnly": True}),NOW-timedelta(minutes=30)))
    conn.execute("""INSERT INTO aip_eval_run
        (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
         target_ref,dataset_ref,judge_ref,status,idempotency_key,created_by)
        VALUES (%s,%s,'run-1',%s,1,%s,%s,%s,%s,'queued',%s,%s)""",
        (TENANT.org_id,TENANT.project_id,suite_ref.asset_id,suite_ref.content_hash,
         Jsonb(TARGET.model_dump(mode="json",by_alias=True)),
         Jsonb({"testOnly":True}),Jsonb(JUDGE.model_dump(mode="json",by_alias=True)),
         "bg00ab-test-key","bg00ab-test-owner"))
    if stage == "identities":
        return
    for cert, receipt, _ in (target, judge):
        if stage == "one_receipt" and receipt.purpose == "judge":
            continue
        claim_hash = hashlib.sha256(canonical_receipt_bytes(receipt)).hexdigest()
        if bad_claim and receipt.purpose == "judge":
            claim_hash = "f" * 64
        conn.execute("""INSERT INTO aip_eval_execution_receipt
            (org_id,project_id,receipt_id,run_id,case_id,purpose,identity_id,
             certificate_hash,suite_ref,executor_ref,claim_hash,input_hash,
             output_hash,actual_hash,expected_hash,passed,detail_code,
             occurred_at,signature_base64,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (TENANT.org_id,TENANT.project_id,receipt.receipt_id,receipt.run_id,
             receipt.case_id,receipt.purpose,receipt.identity_id,
             receipt.certificate_hash,Jsonb(receipt.suite_ref.model_dump(mode="json",by_alias=True)),
             Jsonb(receipt.executor_ref.model_dump(mode="json",by_alias=True)),
             claim_hash,receipt.input_hash,receipt.output_hash,receipt.actual_hash,
             receipt.expected_hash,receipt.passed,receipt.detail_code,receipt.occurred_at,
             receipt.signature_base64,
             NOW+timedelta(minutes=30) if future_receipt and receipt.purpose=="judge" else NOW))


def _read(conn, target, judge, *, at=NOW):
    return read_persisted_execution_pair(
        conn,evaluated_at=at,expected_tenant=TENANT,expected_run_id="run-1",
        expected_suite_ref=SUITE,expected_case_id="case-1",
        expected_target_ref=TARGET,expected_judge_ref=JUDGE,
        expected_input_hash=INPUT_HASH,expected_expected_hash=EXPECTED_HASH,
        target_certificate=target[0],target_receipt=target[1],
        judge_certificate=judge[0],judge_receipt=judge[1],
    )


@pytest.mark.parametrize("stage", ["empty", "root", "identities", "one_receipt"])
def test_missing_persisted_authority_rejects(connection, stage):
    root,target,judge = _signed_pair()
    _seed(connection,root,target,judge,stage=stage)
    connection.execute("SET LOCAL ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    with pytest.raises(EvalExecutionRejected):
        _read(connection,target,judge)


@pytest.mark.parametrize("scenario", ["valid", "cross_tenant", "revoked", "root_revoked", "bad_claim", "expired", "wrong_role", "future_receipt"])
def test_signed_persisted_pair_and_negative_boundaries(connection, scenario):
    root,target,judge = _signed_pair()
    _seed(connection,root,target,judge,bad_claim=scenario=="bad_claim",
          future_receipt=scenario=="future_receipt")
    if scenario == "revoked":
        connection.execute("""INSERT INTO aip_eval_authority_revocation
            (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
             approval_ref,reason_hash)
            VALUES ('org-org','dev-project','bg00ab-revoke',%s,%s,%s,%s,%s)""",
            (target[0].identity_id,NOW,"bg00ab-test-owner",Jsonb({"testOnly":True}),"e"*64))
    if scenario == "root_revoked":
        connection.execute("""INSERT INTO aip_eval_authority_revocation
            (org_id,project_id,event_id,issuer_id,issuer_key_id,revoked_at,
             owner_ref,approval_ref,reason_hash)
            VALUES ('org-org','dev-project','bg00ab-root-revoke',%s,%s,%s,%s,%s,%s)""",
            (root.issuer_id,root.key_id,NOW,"bg00ab-test-owner",
             Jsonb({"testOnly":True}),"e"*64))
    if scenario != "wrong_role":
        connection.execute("SET LOCAL ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id',%s,true)",
                       ("dev-org" if scenario=="cross_tenant" else "org-org",))
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    if scenario == "valid":
        assert _read(connection,target,judge).passed is True
    else:
        with pytest.raises(EvalExecutionRejected):
            _read(connection,target,judge,
                  at=NOW+timedelta(days=2) if scenario=="expired" else NOW)
