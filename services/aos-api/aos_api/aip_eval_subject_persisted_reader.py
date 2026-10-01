"""Read signed subject-review evidence from one tenant's stable Eval snapshot.

This proves a persisted structure claim. It does not authorize execution,
publication, or the provenance that later source Owners must supply.
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime
import re

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_subject_proof_contracts import SubjectReviewEnvelope, subject_envelope_hash
from aos_api.aip_eval_subject_proof_authority import (
    SubjectCertificate, SubjectIssuerRoot, SubjectReceipt, VerifiedSubjectPair,
    claim_hash, verify_subject_pair,
)
from aos_api.asset_registry.signature import TrustRoot


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _key(value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('persisted subject public key is invalid') from exc
    _require(len(key) == 32 and base64.b64encode(key).decode() == value,
             'persisted subject public key is not canonical')
    return key


def _json(value):
    return value.model_dump(mode='json', by_alias=True)


def read_persisted_subject_pair(
    conn: psycopg.Connection,
    *,
    expected_envelope: SubjectReviewEnvelope,
    expected_tenant: TenantContext,
    expected_report_id: str,
    expected_report_revision: int,
    expected_report_hash: str,
    now: datetime,
    source_certificate: SubjectCertificate,
    source_receipt: SubjectReceipt,
    judge_certificate: SubjectCertificate,
    judge_receipt: SubjectReceipt,
) -> VerifiedSubjectPair:
    """Require persisted current rows, then verify both original signatures.

    Caller retains the repeatable-read transaction for source Owner checks;
    presented objects alone never grant authority.
    """
    envelope = SubjectReviewEnvelope.model_validate(expected_envelope.model_dump(mode='python'))
    _require(now.utcoffset() is not None and envelope.tenant == expected_tenant,
             'subject tenant or cutoff is invalid')
    _require(type(expected_report_id) is str and 0 < len(expected_report_id) <= 200
             and expected_report_id.strip() == expected_report_id
             and type(expected_report_revision) is int and expected_report_revision >= 1
             and type(expected_report_hash) is str
             and re.fullmatch(r'[0-9a-f]{64}', expected_report_hash) is not None,
             'exact subject EvalReport reference required')
    scope = (expected_tenant.org_id, expected_tenant.project_id)
    digest = subject_envelope_hash(envelope)
    roots = {}
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(context['role'] == 'aos_runtime'
                     and (context['org_id'], context['project_id']) == scope
                     and context['isolation'] in ('repeatable read', 'serializable'),
                     'subject tenant role or stable snapshot is unavailable')
            run = cur.execute("""SELECT * FROM aip_eval_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*scope, envelope.eval_run_id)).fetchone()
            _require(run is not None and run['status'] == 'succeeded'
                     and (run['suite_id'], run['suite_revision'], run['suite_hash'])
                         == (envelope.suite_ref.asset_id, int(envelope.suite_ref.revision),
                             envelope.suite_ref.content_hash)
                     and run['target_ref'] == _json(envelope.generation_skill_ref)
                     and run['judge_ref'] == _json(envelope.judge_ref)
                     and run['eval_contract_ref'] == _json(envelope.contract_ref)
                     and run['subject_artifact_ref'] == _json(envelope.subject_artifact_ref)
                     and run['stage_attempt_ref'] == _json(envelope.stage_attempt_ref)
                     and run['gate_policy_ref'] == _json(envelope.policy_ref)
                     and run['evidence_cutoff_at'] == envelope.cutoff
                     and run['created_at'] <= now,
                     'current subject EvalRun context is unavailable')
            for cert, receipt, purpose in (
                (source_certificate, source_receipt, 'source-witness'),
                (judge_certificate, judge_receipt, 'judge'),
            ):
                _require(cert.purpose == purpose and receipt.purpose == purpose,
                         'subject proof purpose drifted')
                issuer = cur.execute("""SELECT * FROM aip_eval_issuer_root
                    WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s""",
                    (*scope, cert.issuer_id, cert.issuer_key_id)).fetchone()
                _require(issuer is not None, 'current subject issuer root is unavailable')
                issuer_key = _key(issuer['public_key_base64'])
                _require(issuer['purpose'] == 'subject-review'
                         and issuer['public_key_hash'] == hashlib.sha256(issuer_key).hexdigest()
                         and bool(issuer['owner_ref'] and issuer['approval_ref'] and issuer['source_hash'])
                         and issuer['created_at'] <= receipt.occurred_at,
                         'persisted subject issuer root drifted')
                roots[(cert.issuer_id, cert.issuer_key_id)] = SubjectIssuerRoot(TrustRoot(
                    cert.issuer_id, cert.issuer_key_id, issuer_key,
                    'sha256:' + issuer['public_key_hash'], issuer['valid_from'], issuer['valid_until']))
                identity = cur.execute("""SELECT * FROM aip_eval_executor_identity
                    WHERE org_id=%s AND project_id=%s AND identity_id=%s""",
                    (*scope, cert.identity_id)).fetchone()
                _require(identity is not None, 'current subject identity is unavailable')
                identity_key = _key(identity['public_key_base64'])
                _require(identity['purpose'] == purpose
                         and (identity['issuer_id'], identity['issuer_key_id'])
                             == (cert.issuer_id, cert.issuer_key_id)
                         and identity['certificate_json'] == _json(cert)
                         and identity['certificate_hash'] == claim_hash(cert)
                         and identity['executor_ref'] == _json(cert.executor_ref)
                         and identity['public_key_base64'] == cert.public_key_base64
                         and identity['public_key_hash'] == hashlib.sha256(identity_key).hexdigest()
                         and (identity['valid_from'], identity['valid_until'])
                             == (cert.valid_from, cert.valid_until)
                         and identity['created_at'] <= receipt.occurred_at
                         and bool(identity['owner_ref'] and identity['approval_ref']),
                         'persisted subject identity drifted')
                persisted = cur.execute("""SELECT * FROM aip_eval_subject_receipt
                    WHERE org_id=%s AND project_id=%s AND eval_run_id=%s
                      AND case_id=%s AND envelope_hash=%s AND purpose=%s""",
                    (*scope, envelope.eval_run_id, envelope.case_id, digest, purpose)).fetchone()
                _require(persisted is not None, 'current subject receipt is unavailable')
                _require(persisted['receipt_id'] == receipt.receipt_id
                         and persisted['identity_id'] == cert.identity_id
                         and persisted['certificate_hash'] == claim_hash(cert)
                         and persisted['claim_hash'] == claim_hash(receipt)
                         and persisted['source_receipt_hash'] == receipt.source_receipt_hash
                         and persisted['structure_passed'] == receipt.structure_passed
                         and persisted['detail_code'] == receipt.detail_code
                         and persisted['occurred_at'] == receipt.occurred_at
                         and persisted['created_at'] <= now
                         and persisted['signature_base64'] == receipt.signature_base64,
                         'persisted subject receipt drifted')
            linked = cur.execute("""SELECT proof.*, report.content_hash AS report_hash,
                report.run_id AS report_run_id, report.suite_ref AS report_suite_ref,
                report.target_ref AS report_target_ref, report.dataset_ref AS report_dataset_ref,
                report.judge_ref AS report_judge_ref, report.eval_contract_ref AS report_contract_ref,
                report.subject_artifact_ref AS report_subject_ref,
                report.stage_attempt_ref AS report_attempt_ref,
                report.gate_policy_ref AS report_policy_ref,
                report.evidence_cutoff_at AS report_cutoff,
                report.results AS report_results, report.gate_passed AS report_gate_passed,
                report.created_at AS report_created_at
                FROM aip_eval_subject_case_proof proof
                JOIN aip_eval_report_revision report
                  ON report.org_id=proof.org_id AND report.project_id=proof.project_id
                 AND report.run_id=proof.eval_run_id AND report.report_id=proof.report_id
                 AND report.revision=proof.report_revision
                WHERE proof.org_id=%s AND proof.project_id=%s
                  AND proof.eval_run_id=%s AND proof.case_id=%s
                  AND proof.envelope_hash=%s""",
                (*scope, envelope.eval_run_id, envelope.case_id, digest)).fetchone()
            _require(linked is not None
                     and (linked['report_id'], linked['report_revision'], linked['report_hash'])
                         == (expected_report_id, expected_report_revision, expected_report_hash)
                     and linked['report_run_id'] == envelope.eval_run_id
                     and linked['report_suite_ref'] == _json(envelope.suite_ref)
                     and linked['report_target_ref'] == _json(envelope.generation_skill_ref)
                     and linked['report_dataset_ref'] == run['dataset_ref']
                     and linked['report_judge_ref'] == _json(envelope.judge_ref)
                     and linked['report_contract_ref'] == _json(envelope.contract_ref)
                     and linked['report_subject_ref'] == _json(envelope.subject_artifact_ref)
                     and linked['report_attempt_ref'] == _json(envelope.stage_attempt_ref)
                     and linked['report_policy_ref'] == _json(envelope.policy_ref)
                     and linked['report_cutoff'] == envelope.cutoff
                     and linked['source_receipt_id'] == source_receipt.receipt_id
                     and linked['source_claim_hash'] == claim_hash(source_receipt)
                     and linked['judge_receipt_id'] == judge_receipt.receipt_id
                     and linked['judge_claim_hash'] == claim_hash(judge_receipt)
                     and judge_receipt.occurred_at <= linked['verified_at'] <= linked['created_at'] <= now
                     and judge_receipt.occurred_at <= linked['report_created_at'] <= now,
                     'subject proof does not bind the exact EvalReport')
            results = linked['report_results']
            _require(type(results) is list and len(results) == 1
                     and type(results[0]) is dict
                     and results[0].get('caseId') == envelope.case_id
                     and type(results[0].get('passed')) is bool
                     and results[0]['passed'] is judge_receipt.structure_passed
                     and results[0].get('detailCode') == judge_receipt.detail_code
                     and type(linked['report_gate_passed']) is bool,
                     'signed subject case result differs from EvalReport')
            revoked = cur.execute("""SELECT identity_id,issuer_id,issuer_key_id
                FROM aip_eval_authority_revocation
                WHERE org_id=%s AND project_id=%s AND revoked_at<=%s""",
                (*scope, now)).fetchall()
            revoked_ids = frozenset(row['identity_id'] for row in revoked if row['identity_id'])
            revoked_roots = {(row['issuer_id'], row['issuer_key_id'])
                             for row in revoked if row['issuer_id']}
            _require(not revoked_roots.intersection(roots), 'current subject issuer is revoked')
    except psycopg.Error as exc:
        raise ValueError('persisted subject authority read failed') from exc
    return verify_subject_pair(
        expected_envelope=envelope, issuer_roots=roots, revoked_identity_ids=revoked_ids,
        now=now, source_certificate=source_certificate, source_receipt=source_receipt,
        judge_certificate=judge_certificate, judge_receipt=judge_receipt)
