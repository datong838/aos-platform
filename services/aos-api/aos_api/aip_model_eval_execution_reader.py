"""Read a descriptive Model execution plan; never verify execution authority.

Private storage hash equality is not issuer trust, current approval, joint
admission, Usage, settlement, or a verified Report. Those checks remain required.
"""
import hashlib
import json
import re
import base64
import binascii
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_eval_execution_authority import OWNER, SCHEMA, ISSUER_OWNER, ISSUER_SCHEMA
from aos_api.aip_model_eval_execution_contracts import (
    ModelEvalExecutionManifest, ModelEvalExecutorCertificateSigningInput,
    ModelEvalIssuerVerificationInput, canonical_model_certificate_signing_bytes,
    _plain_contract_input, ModelEvalSignedCertificateEnvelope,
    ModelEvalSignedCaseEnvelope, canonical_model_signed_case_bytes, ModelEvalCasePersistenceBinding,
)
from aos_api.aip_model_runtime_store import canonical_hash


class ModelExecutionPlanRejected(ValueError):
    """A stored descriptive plan is missing, inaccessible, or not exact."""


def _require(ok, reason):
    if not ok:
        raise ModelExecutionPlanRejected(reason)


def read_model_issuer_epoch(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    issuer_id: str, issuer_key_id: str, expected_epoch: int, root_hash: str,
) -> tuple[int, str]:
    """Lock/check current epoch only; never prove root provenance or execution.

    No role switching or transaction repair: the original caller retains the
    shared lock until it commits/rolls back. Stale SERIAL snapshots fail closed.
    """
    _require(isinstance(expected_tenant,TenantContext), 'typed issuer tenant required')
    tenant=TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id,tenant.project_id)==('org-org','dev-project'), 'positive issuer tenant required')
    _require(all(type(v) is str and 1<=len(v)<=200 and v==v.strip()
                 for v in (issuer_id,issuer_key_id)), 'exact issuer identifiers required')
    _require(type(expected_epoch) is int and expected_epoch>=1, 'native positive issuer epoch required')
    _require(type(root_hash) is str and re.fullmatch(r'[0-9a-f]{64}',root_hash) is not None, 'exact issuer root hash required')
    _require(conn.info.transaction_status==TransactionStatus.INTRANS, 'caller issuer transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context=cur.execute("""SELECT current_user AS role,
              current_setting('aos.org_id',true) AS org_id,
              current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(context is not None and context['role']==ISSUER_OWNER
                     and (context['org_id'],context['project_id'])==(tenant.org_id,tenant.project_id)
                     and context['isolation']=='serializable', 'exact private Issuer SERIAL snapshot required')
            row=cur.execute(f"""SELECT epoch,root_hash FROM {ISSUER_SCHEMA}.issuer_epoch
              WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s FOR SHARE""",
              (tenant.org_id,tenant.project_id,issuer_id,issuer_key_id)).fetchone()
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('current Model issuer epoch unavailable') from exc
    _require(row is not None and row['epoch']==expected_epoch and row['root_hash']==root_hash,
             'current Model issuer epoch or root drifted')
    return row['epoch'],row['root_hash']


def read_model_certificate_epoch(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    issuer_id: str, issuer_key_id: str, expected_epoch: int, root_hash: str,
    certificate_hash: str, expected_certificate_epoch: int,
    execution_id: str, case_id: str, purpose: str,
) -> tuple[int,str]:
    """Root-then-certificate locks and exact metadata only; never issuer trust."""
    _require(type(certificate_hash) is str and re.fullmatch(r'[0-9a-f]{64}',certificate_hash) is not None,
             'exact certificate hash required')
    _require(type(expected_certificate_epoch) is int and expected_certificate_epoch>=1,
             'native positive certificate epoch required')
    _require(all(type(v) is str and 1<=len(v)<=200 and v==v.strip() for v in (execution_id,case_id))
             and purpose in ('target','judge'), 'exact certificate case identity required')
    read_model_issuer_epoch(conn,expected_tenant=expected_tenant,issuer_id=issuer_id,
        issuer_key_id=issuer_key_id,expected_epoch=expected_epoch,root_hash=root_hash)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            row=cur.execute(f"""SELECT h.epoch,h.active_hash
              FROM {ISSUER_SCHEMA}.certificate_epoch h
              JOIN {ISSUER_SCHEMA}.executor_certificate c
                ON (h.org_id,h.project_id,h.certificate_hash)=(c.org_id,c.project_id,c.content_hash)
              WHERE h.org_id=%s AND h.project_id=%s AND h.certificate_hash=%s
                AND c.issuer_id=%s AND c.key_id=%s AND c.execution_id=%s
                AND c.case_id=%s AND c.purpose=%s AND c.attempt=1 FOR SHARE OF h""",
              (expected_tenant.org_id,expected_tenant.project_id,certificate_hash,
               issuer_id,issuer_key_id,execution_id,case_id,purpose)).fetchone()
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('current Model certificate epoch unavailable') from exc
    _require(row is not None and row['epoch']==expected_certificate_epoch
             and row['active_hash']==certificate_hash, 'current Model certificate epoch or binding drifted')
    return row['epoch'],row['active_hash']


def validate_model_certificate_signature(
    manifest, certificate, *, issuer_input, signature_base64: str,
    checked_at: datetime, revoked_identity_ids: frozenset[str],
) -> None:
    """Necessary crypto/time checks only; presented issuer facts confer no trust.

    A future persisted consumer must supply current roots and withdrawals from
    its same authoritative snapshot. This helper does not query or grant access.
    """
    claim = ModelEvalExecutorCertificateSigningInput.model_validate(certificate)
    root = ModelEvalIssuerVerificationInput.model_validate(issuer_input)
    raw = canonical_model_certificate_signing_bytes(manifest, claim)
    _require(type(checked_at) is datetime and checked_at.utcoffset() is not None,
             'aware certificate check time required')
    _require(type(revoked_identity_ids) is frozenset
             and all(type(item) is str and item and item == item.strip()
                     for item in revoked_identity_ids), 'exact immutable identity revocations required')
    _require(root.tenant == claim.tenant
             and root.issuer_id == claim.issuer_id
             and root.issuer_key_id == claim.issuer_key_id,
             'exact Model issuer tenant and key required')
    _require(root.valid_from <= claim.valid_from < claim.valid_until <= root.valid_until
             and claim.valid_from <= checked_at < claim.valid_until
             and root.valid_from <= checked_at < root.valid_until,
             'current contained half-open certificate interval required')
    _require((root.revoked_at is None or checked_at < root.revoked_at)
             and claim.leg.identity_id not in revoked_identity_ids,
             'Model issuer or executor identity revoked')
    _require(type(signature_base64) is str and len(signature_base64) == 88,
             'canonical Ed25519 certificate signature required')
    try:
        signature = base64.b64decode(signature_base64, validate=True)
        _require(len(signature) == 64
                 and base64.b64encode(signature).decode('ascii') == signature_base64,
                 'canonical Ed25519 certificate signature required')
        Ed25519PublicKey.from_public_bytes(base64.b64decode(root.public_key_base64, validate=True)).verify(signature, raw)
    except (InvalidSignature, binascii.Error, ValueError) as exc:
        raise ModelExecutionPlanRejected('invalid Model certificate signature') from exc


def read_model_execution_plan(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    execution_id: str, manifest_hash: str,
) -> ModelEvalExecutionManifest:
    """Read only within the caller's exact private Owner tenant snapshot.

    The returned plan always has execution_allowed=False. It carries no proof
    that its historical request, source, hold, or joint refs are currently valid.
    """
    _require(isinstance(expected_tenant, TenantContext), 'typed tenant required')
    try:
        tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
    except (ValidationError, TypeError, ValueError) as exc:
        raise ModelExecutionPlanRejected('exact tenant required') from exc
    _require((tenant.org_id, tenant.project_id) == ('org-org', 'dev-project'),
             'positive Model tenant required')
    _require(type(execution_id) is str and 1 <= len(execution_id) <= 200
             and execution_id == execution_id.strip(), 'exact execution identity required')
    _require(type(manifest_hash) is str and re.fullmatch(r'[0-9a-f]{64}', manifest_hash) is not None,
             'exact manifest hash required')
    _require(conn.info.transaction_status == TransactionStatus.INTRANS,
             'caller transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
              current_setting('aos.org_id',true) AS org_id,
              current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(context is not None and context['role'] == OWNER
                     and (context['org_id'], context['project_id']) == (tenant.org_id, tenant.project_id)
                     and context['isolation'] in ('repeatable read', 'serializable'),
                     'private Owner tenant snapshot required')
            row = cur.execute(f"""SELECT org_id,project_id,execution_id,content_hash,body
                FROM {SCHEMA}.manifest WHERE org_id=%s AND project_id=%s AND execution_id=%s""",
                (tenant.org_id, tenant.project_id, execution_id)).fetchone()
    except psycopg.Error as exc:
        # The caller owns rollback/reconciliation; never silently start or repair
        # a transaction and lose the snapshot which supplied the other facts.
        raise ModelExecutionPlanRejected('private Model plan read failed') from exc
    _require(row is not None, 'persisted Model plan unavailable')
    _require(isinstance(row['body'], (bytes, bytearray, memoryview)), 'byte-preserved plan required')
    raw = bytes(row['body'])
    _require(hashlib.sha256(raw).hexdigest() == row['content_hash'] == manifest_hash,
             'persisted Model plan bytes or hash drifted')
    try:
        plan = ModelEvalExecutionManifest.model_validate_json(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        raise ModelExecutionPlanRejected('strict Model plan required') from exc
    _require(plan.tenant == tenant and plan.execution_id == execution_id
             and (row['org_id'], row['project_id'], row['execution_id'])
                 == (tenant.org_id, tenant.project_id, execution_id),
             'persisted Model plan identity drifted')
    _require(canonical_hash(plan.model_dump(mode='json', by_alias=True)) == manifest_hash,
             'canonical complete Model plan bytes required')
    return plan


def _read_persisted_model_certificate(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    execution_id: str, manifest_hash: str, certificate_hash: str,
    root_hash: str, expected_root_epoch: int, expected_certificate_epoch: int,
):
    """Private necessary facts only, not trusted output.

    Necessary byte/signature/current-head checks, never execution permission.

    Root bootstrap provenance, current subject approval, identity withdrawal,
    Usage and Report proof still require their independent authoritative gates.
    The caller retains root-then-certificate shared locks until transaction end.
    """
    _require(isinstance(expected_tenant, TenantContext), 'typed tenant required')
    tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id, tenant.project_id) == ('org-org', 'dev-project'),
             'positive Model tenant required')
    _require(type(execution_id) is str and 1 <= len(execution_id) <= 200
             and execution_id == execution_id.strip(), 'exact execution identity required')
    _require(all(type(h) is str and re.fullmatch(r'[0-9a-f]{64}', h) is not None
                 for h in (manifest_hash, certificate_hash, root_hash)), 'exact content hashes required')
    _require(all(type(e) is int and e >= 1 for e in
                 (expected_root_epoch, expected_certificate_epoch)), 'native positive epochs required')
    _require(conn.info.transaction_status == TransactionStatus.INTRANS, 'caller transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
              current_setting('aos.org_id',true) AS org_id,
              current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(context is not None and context['role'] == ISSUER_OWNER
                     and (context['org_id'], context['project_id']) == (tenant.org_id, tenant.project_id)
                     and context['isolation'] == 'serializable', 'exact private Issuer SERIAL snapshot required')
            plan_row = cur.execute(f"SELECT * FROM {SCHEMA}.manifest WHERE org_id=%s AND project_id=%s AND execution_id=%s",
                (tenant.org_id, tenant.project_id, execution_id)).fetchone()
            cert_row = cur.execute(f"SELECT * FROM {ISSUER_SCHEMA}.executor_certificate WHERE org_id=%s AND project_id=%s AND content_hash=%s",
                (tenant.org_id, tenant.project_id, certificate_hash)).fetchone()
            _require(cert_row is not None, 'persisted Model certificate unavailable')
            root_row = cur.execute(f"SELECT * FROM {ISSUER_SCHEMA}.issuer_root WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s",
                (tenant.org_id, tenant.project_id, cert_row['issuer_id'], cert_row['key_id'])).fetchone()
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('persisted Model certificate read failed') from exc

    def parse(row, digest, model):
        _require(row is not None and isinstance(row['body'], (bytes, bytearray, memoryview)),
                 'persisted original bytes required')
        raw = bytes(row['body'])
        _require(hashlib.sha256(raw).hexdigest() == row['content_hash'] == digest,
                 'persisted original byte hash drifted')
        try:
            value = model.model_validate_json(raw)
        except (ValidationError, TypeError, ValueError) as exc:
            raise ModelExecutionPlanRejected('strict persisted Model contract required') from exc
        _require(canonical_hash(value.model_dump(mode='json', by_alias=True)) == digest,
                 'canonical complete persisted bytes required')
        _require((row['org_id'], row['project_id']) == (tenant.org_id, tenant.project_id),
                 'persisted tenant header drifted')
        return value

    plan = parse(plan_row, manifest_hash, ModelEvalExecutionManifest)
    root = parse(root_row, root_hash, ModelEvalIssuerVerificationInput)
    envelope = parse(cert_row, certificate_hash, ModelEvalSignedCertificateEnvelope)
    claim = envelope.certificate
    _require(plan.tenant == tenant and plan.execution_id == execution_id
             and plan_row['execution_id'] == execution_id, 'persisted manifest identity drifted')
    _require(claim.tenant == tenant and claim.execution_id == execution_id
             and (cert_row['execution_id'], cert_row['case_id'], cert_row['purpose'], cert_row['attempt'],
                  cert_row['issuer_id'], cert_row['key_id']) ==
                 (execution_id, claim.case_id, claim.purpose, claim.leg.attempt, claim.issuer_id, claim.issuer_key_id),
             'persisted certificate header drifted')
    _require(root.tenant == tenant and (root_row['issuer_id'], root_row['key_id']) ==
             (root.issuer_id, root.issuer_key_id), 'persisted root header drifted')
    read_model_certificate_epoch(conn, expected_tenant=tenant, issuer_id=claim.issuer_id,
        issuer_key_id=claim.issuer_key_id, expected_epoch=expected_root_epoch, root_hash=root_hash,
        certificate_hash=certificate_hash, expected_certificate_epoch=expected_certificate_epoch,
        execution_id=execution_id, case_id=claim.case_id, purpose=claim.purpose)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            checked_at = cur.execute('SELECT clock_timestamp() AS checked_at').fetchone()['checked_at']
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('native certificate check clock unavailable') from exc
    _require(root_row['created_at'] <= cert_row['created_at'] <= checked_at,
             'persisted certificate creation order drifted')
    # Exact root/certificate withdrawal heads were checked under retained locks;
    # global identity withdrawal remains a separate gate, not an inferred pass.
    validate_model_certificate_signature(plan, claim, issuer_input=root,
        signature_base64=envelope.signature_base64, checked_at=checked_at,
        revoked_identity_ids=frozenset())
    return plan, root, envelope, cert_row['created_at'], checked_at


def validate_persisted_model_certificate(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    execution_id: str, manifest_hash: str, certificate_hash: str,
    root_hash: str, expected_root_epoch: int, expected_certificate_epoch: int,
) -> None:
    """Necessary persisted certificate checks only; no verified authority."""
    _read_persisted_model_certificate(conn, expected_tenant=expected_tenant,
        execution_id=execution_id, manifest_hash=manifest_hash, certificate_hash=certificate_hash,
        root_hash=root_hash, expected_root_epoch=expected_root_epoch,
        expected_certificate_epoch=expected_certificate_epoch)


def validate_model_case_signature(
    manifest, envelope, *, certificate_envelope, issuer_input,
    checked_at: datetime, revoked_identity_ids: frozenset[str],
    input_bytes: bytes, output_bytes: bytes, target_claim=None,
) -> None:
    """Necessary executor signature and exact case binding; never execution proof.

    All inputs here are presented facts. Persisted current heads, bootstrap,
    transport/Usage and Report must still be checked by the future full reader.
    """
    signed = ModelEvalSignedCaseEnvelope.model_validate(envelope)
    certificate = ModelEvalSignedCertificateEnvelope.model_validate(certificate_envelope)
    cert = certificate.certificate
    claim = signed.payload.claim
    _require(signed.payload.certificate_hash == canonical_hash(
        certificate.model_dump(mode='json', by_alias=True)), 'exact signed certificate envelope required')
    validate_model_certificate_signature(manifest, cert, issuer_input=issuer_input,
        signature_base64=certificate.signature_base64, checked_at=checked_at,
        revoked_identity_ids=revoked_identity_ids)
    _require((claim.tenant, claim.execution_id, claim.manifest_hash, claim.request_hash,
              claim.case_id, claim.purpose, claim.candidate_ref, claim.leg) ==
             (cert.tenant, cert.execution_id, cert.manifest_hash, cert.request_hash,
              cert.case_id, cert.purpose, cert.candidate_ref, cert.leg),
             'case must bind exact original executor certificate')
    _require(cert.valid_from <= claim.occurred_at < cert.valid_until
             and claim.occurred_at <= checked_at, 'case time outside current certificate interval')
    raw = canonical_model_signed_case_bytes(manifest, signed.payload, input_bytes=input_bytes,
        output_bytes=output_bytes, target_claim=target_claim)
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(cert.public_key_base64, validate=True)).verify(
            base64.b64decode(signed.signature_base64, validate=True), raw)
    except (InvalidSignature, binascii.Error, ValueError) as exc:
        raise ModelExecutionPlanRejected('invalid Model executor case signature') from exc


def _read_persisted_model_case(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    execution_id: str, manifest_hash: str, case_id: str,
    target_binding, judge_binding, target_input: bytes, target_output: bytes,
    judge_input: bytes, judge_output: bytes,
):
    """Same-caller original Target/Judge signatures and current heads only.

    Never verifies bootstrap provenance, subject approval, actual transport,
    Usage, settlement or Report. All shared locks survive until caller exit.
    """
    _require(isinstance(expected_tenant, TenantContext), 'typed tenant required')
    tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id, tenant.project_id) == ('org-org', 'dev-project'), 'positive case tenant required')
    _require(all(type(v) is str and 1 <= len(v) <= 200 and v == v.strip()
                 for v in (execution_id, case_id)), 'exact case identifiers required')
    _require(type(manifest_hash) is str and re.fullmatch(r'[0-9a-f]{64}', manifest_hash) is not None,
             'exact manifest hash required')
    bindings = {'target': ModelEvalCasePersistenceBinding.model_validate(target_binding),
                'judge': ModelEvalCasePersistenceBinding.model_validate(judge_binding)}
    _require(bindings['target'].certificate_hash != bindings['judge'].certificate_hash,
             'independent case certificates required')
    _require(conn.info.transaction_status == TransactionStatus.INTRANS, 'caller case transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
              current_setting('aos.org_id',true) AS org_id,
              current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(context is not None and context['role'] == ISSUER_OWNER
                     and (context['org_id'], context['project_id']) == (tenant.org_id, tenant.project_id)
                     and context['isolation'] == 'serializable', 'exact private Issuer SERIAL snapshot required')
            roots = []
            for purpose, binding in bindings.items():
                row = cur.execute(f"SELECT issuer_id,key_id FROM {ISSUER_SCHEMA}.executor_certificate WHERE org_id=%s AND project_id=%s AND content_hash=%s",
                    (tenant.org_id, tenant.project_id, binding.certificate_hash)).fetchone()
                _require(row is not None, 'original case certificate unavailable')
                roots.append((row['issuer_id'], row['key_id'], purpose))
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('original case certificate metadata unavailable') from exc
    # Lock every root before any certificate, with deterministic ordering.
    for issuer_id, key_id, purpose in sorted(roots):
        binding = bindings[purpose]
        read_model_issuer_epoch(conn, expected_tenant=tenant, issuer_id=issuer_id,
            issuer_key_id=key_id, expected_epoch=binding.root_epoch, root_hash=binding.root_hash)
    facts = {}
    for purpose in sorted(bindings, key=lambda p: bindings[p].certificate_hash):
        binding = bindings[purpose]
        facts[purpose] = _read_persisted_model_certificate(conn, expected_tenant=tenant,
            execution_id=execution_id, manifest_hash=manifest_hash, certificate_hash=binding.certificate_hash,
            root_hash=binding.root_hash, expected_root_epoch=binding.root_epoch,
            expected_certificate_epoch=binding.certificate_epoch)
    cases = {}
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            for purpose, binding in bindings.items():
                row = cur.execute(f"SELECT * FROM {SCHEMA}.case_result WHERE org_id=%s AND project_id=%s AND execution_id=%s AND case_id=%s AND purpose=%s AND attempt=1",
                    (tenant.org_id, tenant.project_id, execution_id, case_id, purpose)).fetchone()
                _require(row is not None and isinstance(row['body'], (bytes, bytearray, memoryview)),
                         'original case bytes unavailable')
                raw = bytes(row['body'])
                _require(hashlib.sha256(raw).hexdigest() == row['content_hash'] == binding.case_hash,
                         'original case byte hash drifted')
                try:
                    case = ModelEvalSignedCaseEnvelope.model_validate_json(raw)
                except (ValidationError, TypeError, ValueError) as exc:
                    raise ModelExecutionPlanRejected('strict persisted case required') from exc
                _require(canonical_hash(case.model_dump(mode='json', by_alias=True)) == binding.case_hash,
                         'canonical complete case bytes required')
                claim = case.payload.claim
                _require((row['org_id'], row['project_id'], row['execution_id'], row['case_id'], row['purpose'], row['attempt']) ==
                         (tenant.org_id, tenant.project_id, execution_id, case_id, purpose, 1)
                         and claim.tenant == tenant and claim.execution_id == execution_id
                         and claim.case_id == case_id and claim.purpose == purpose,
                         'persisted case header drifted')
                _require(facts[purpose][3] <= claim.occurred_at, 'case predates persisted certificate')
                cases[purpose] = case
            checked_at = cur.execute('SELECT clock_timestamp() AS checked_at').fetchone()['checked_at']
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('persisted case read failed') from exc
    for purpose, input_bytes, output_bytes in (
        ('target', target_input, target_output), ('judge', judge_input, judge_output),
    ):
        plan, root, cert, _, _ = facts[purpose]
        validate_model_case_signature(plan, cases[purpose], certificate_envelope=cert,
            issuer_input=root, checked_at=checked_at, revoked_identity_ids=frozenset(),
            input_bytes=input_bytes, output_bytes=output_bytes,
            target_claim=cases['target'].payload.claim if purpose == 'judge' else None)

    return facts


def validate_judge_parent_hold(
    conn: psycopg.Connection, *, expected_tenant: TenantContext, parent_limit,
    release_policy, artifact_bytes,
) -> None:
    """Read new-purpose current parent backing; never verify joint execution.

    Only the internal original guard can establish Source/checker facts. No
    caller facts callback, hold creation, COMMIT, role switch or transport.
    """
    from aos_api.aip_model_eval_execution_contracts import ModelJudgeParentBudgetLimit
    from aos_api.aip_model_eval_judge_budget import ModelJudgeBudgetStore
    from aos_api.aip_budget_reservation_store import BudgetReservationBlocked
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.tenant_scope import TenantScope
    try:
        _require(isinstance(expected_tenant, TenantContext), 'typed Judge parent tenant required')
        tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
        parent = ModelJudgeParentBudgetLimit.model_validate(_plain_contract_input(parent_limit))
        _require(tenant == parent.tenant, 'Judge parent tenant drifted')
        ModelJudgeBudgetStore(release_policy=release_policy, artifact_bytes=artifact_bytes).require_current_parent(
            conn, TenantScope(tenant.org_id, tenant.project_id), parent)
    except (ValidationError, psycopg.Error, BudgetReservationBlocked, AipActionTransitionBlocked) as exc:
        raise ModelExecutionPlanRejected('current original Judge parent unavailable or drifted') from exc


def validate_model_parent_hold(
    conn: psycopg.Connection, *, expected_tenant: TenantContext, parent_limit,
) -> None:
    """Check original committed hold/backing only; never grant execution.

    Current governance/checker guards, allocations, Source and joint admission
    remain separate. Caller retains bucket locks; no roles or transactions are
    created, switched or repaired and no reservation writes are performed.
    """
    from aos_api.aip_model_eval_execution_contracts import ModelEvalParentBudgetLimit
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
    from aos_api.aip_budget_reservation_store import canonical_hash as budget_hash, BudgetReservationBlocked
    _require(isinstance(expected_tenant, TenantContext), 'typed parent tenant required')
    tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
    parent = ModelEvalParentBudgetLimit.model_validate(_plain_contract_input(parent_limit))
    key = (tenant.org_id, tenant.project_id)
    _require(key == ('org-org', 'dev-project'), 'positive parent tenant required')
    _require(conn.info.transaction_status == TransactionStatus.INTRANS, 'caller parent transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            ctx = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(ctx is not None and (ctx['role'],ctx['org_id'],ctx['project_id'],ctx['isolation'])
                     == ('aos_runtime',*key,'serializable'), 'original runtime SERIAL parent caller required')
            row = cur.execute('''SELECT * FROM aip_model_eval_budget_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s''',
                (*key,parent.parent_hold_ref.resource_id)).fetchone()
            _require(row is not None and parent.parent_hold_ref.revision == 1
                     and row['content_hash'] == parent.parent_hold_ref.content_hash, 'exact immutable parent hold required')
            expected = dict(reservationId=str(row['reservation_id']),requestId=parent.request_id,
                requestHash=parent.request_hash,proposalId=row['proposal_id'],proposalHash=row['proposal_hash'],
                approvalEventId=parent.approval_ref.resource_id,
                budgetPolicyRef=parent.budget_policy_ref.model_dump(mode='json',by_alias=True),
                budgetRevisionRef=row['budget_revision_ref'],
                priceRef=AipModelEvalBudgetReservationStore._ref(parent.price_ref,'ModelPriceSnapshotRevision').model_dump(mode='json',by_alias=True),
                currency=parent.currency,upperBoundMinor=parent.upper_bound_minor,state='held')
            AipModelEvalBudgetReservationStore._require_exact_hold(row,expected)
            now = cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            request = cur.execute('''SELECT request_hash,request_json,expires_at FROM aip_model_eval_request
                WHERE org_id=%s AND project_id=%s AND request_id=%s''',(*key,parent.request_id)).fetchone()
            _require(request is not None and request['expires_at'] > now
                     and request['request_hash'] == parent.request_hash
                     and budget_hash(request['request_json']) == parent.request_hash, 'current immutable parent request required')
            from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
            application = ModelEvalRequestCreate.model_validate(request['request_json'])
            _require((application.tenant.org_id,application.tenant.project_id)==key
                     and application.budget_policy_ref==parent.budget_policy_ref
                     and application.price_ref==parent.price_ref
                     and application.currency==parent.currency
                     and application.upper_bound_minor==parent.upper_bound_minor,
                     'parent declaration must match original application')
            approval = cur.execute('''SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,
                decision,actor_id,reason,expires_at,created_at,action_binding_hash
                FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s''',
                (*key,parent.approval_ref.resource_id)).fetchone()
            _require(approval is not None and approval['decision']=='approved'
                     and approval['expires_at'] is not None and approval['expires_at'] > now
                     and approval['proposal_version']==parent.approval_ref.revision
                     and budget_hash(dict(approval),prefixed=True)==parent.approval_ref.content_hash
                     and approval['proposal_id']==row['proposal_id'] and approval['proposal_hash']==row['proposal_hash'],
                     'exact current parent approval record required')
            buckets = cur.execute('''SELECT l.bucket_kind,l.account_id,l.currency,l.reserved_minor,b.held_minor
                FROM aip_model_eval_budget_reservation_bucket l JOIN aip_budget_bucket b
                USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
                WHERE l.org_id=%s AND l.project_id=%s AND l.reservation_id=%s
                ORDER BY b.bucket_kind,b.account_id,b.period_start,b.currency FOR SHARE OF b''',
                (*key,row['reservation_id'])).fetchall()
            budget_id=row['budget_revision_ref']['resourceId']
            accounts={'task':f'model-eval/{parent.request_id}','daily':f'{budget_id}:daily','pilot':f'{budget_id}:pilot'}
            _require(len(buckets)==3 and {b['bucket_kind'] for b in buckets}==set(accounts)
                     and all(b['account_id']==accounts[b['bucket_kind']] and b['currency']==parent.currency
                             and b['reserved_minor']==parent.upper_bound_minor and b['held_minor']>=b['reserved_minor'] for b in buckets),
                     'exact three original parent bucket backing required')
            final_now=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            _require(request['expires_at']>final_now and approval['expires_at']>final_now,
                     'parent request and approval must remain current after bucket locks')
    except (psycopg.Error, BudgetReservationBlocked) as exc:
        raise ModelExecutionPlanRejected('original parent hold unavailable or drifted') from exc


def _lock_persisted_model_identity(conn, tenant, envelope, certificate_hash, expected_epoch):
    """Called after original root/certificate locks, never as standalone trust."""
    _require(type(expected_epoch) is int and expected_epoch >= 1,
             'native positive identity epoch required')
    leg=envelope.certificate.leg
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            row=cur.execute(f"""SELECT h.epoch,h.active,h.key_hash,h.purpose
              FROM {ISSUER_SCHEMA}.identity_epoch h
              JOIN {ISSUER_SCHEMA}.certificate_identity_binding b ON
                (h.org_id,h.project_id,h.identity_id,h.purpose,h.key_hash)=
                (b.org_id,b.project_id,b.identity_id,b.purpose,b.key_hash)
              WHERE b.org_id=%s AND b.project_id=%s AND b.certificate_hash=%s
                AND b.identity_id=%s FOR SHARE OF h""",
                (tenant.org_id,tenant.project_id,certificate_hash,leg.identity_id)).fetchone()
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('current Model identity binding unavailable') from exc
    _require(row is not None and row['active'] and row['epoch']==expected_epoch
             and row['key_hash']==leg.identity_key_hash
             and row['purpose']==envelope.certificate.purpose,
             'current Model identity revoked or binding drifted')


def register_persisted_model_identity(conn, **certificate_args):
    """Verify original persisted signature before metadata binding; no COMMIT.

    This registration is necessary metadata, not approved executor identity or
    trusted root provenance. Missing artifact fails; no runtime DDL/backfill.
    """
    facts=_read_persisted_model_certificate(conn,**certificate_args)
    envelope=facts[2]
    tenant=certificate_args['expected_tenant'];digest=certificate_args['certificate_hash']
    with conn.cursor(row_factory=dict_row) as cur:
        present=cur.execute(f'SELECT certificate_hash FROM {ISSUER_SCHEMA}.certificate_identity_binding WHERE org_id=%s AND project_id=%s AND certificate_hash=%s',
            (tenant.org_id,tenant.project_id,digest)).fetchone()
        if present is None:
            cur.execute(f'INSERT INTO {ISSUER_SCHEMA}.certificate_identity_binding(org_id,project_id,certificate_hash) VALUES (%s,%s,%s)',
                (tenant.org_id,tenant.project_id,digest))
    _lock_persisted_model_identity(conn,tenant,envelope,digest,1)
    _recheck_locked_model_certificate_windows(conn,(facts,))


def validate_persisted_model_identity(conn, *, expected_identity_epoch: int, **certificate_args):
    """Mandatory root→certificate→identity checks; still no execution grant."""
    _require(type(expected_identity_epoch) is int and expected_identity_epoch >= 1,
             'native positive identity epoch required')
    facts=_read_persisted_model_certificate(conn,**certificate_args)
    envelope=facts[2]
    _lock_persisted_model_identity(conn,certificate_args['expected_tenant'],envelope,
        certificate_args['certificate_hash'],expected_identity_epoch)
    _recheck_locked_model_certificate_windows(conn,(facts,))


def validate_persisted_model_case(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    execution_id: str, manifest_hash: str, case_id: str,
    target_binding, judge_binding, target_input: bytes, target_output: bytes,
    judge_input: bytes, judge_output: bytes,
) -> None:
    """Original necessary signature/current-certificate checks; no global trust."""
    _read_persisted_model_case(conn, expected_tenant=expected_tenant,
        execution_id=execution_id, manifest_hash=manifest_hash, case_id=case_id,
        target_binding=target_binding, judge_binding=judge_binding,
        target_input=target_input, target_output=target_output,
        judge_input=judge_input, judge_output=judge_output)


def validate_persisted_model_identity_case(
    conn: psycopg.Connection, *, target_identity_epoch: int,
    judge_identity_epoch: int, **case_args,
) -> None:
    """Both signed case legs and global identities in the original transaction.

    All original roots and certificates are locked before either identity head.
    No optional identity bypass, transaction repair or execution permission.
    Formal issuer provenance, subject approval and terminal joint commitment
    remain independent gates. Caller retains all locks until transaction end.
    """
    epochs={'target':target_identity_epoch,'judge':judge_identity_epoch}
    _require(all(type(epoch) is int and epoch>=1 for epoch in epochs.values()),
             'native positive case identity epochs required')
    facts=_read_persisted_model_case(conn,**case_args)
    for purpose in sorted(facts,key=lambda p:facts[p][2].certificate.leg.identity_id):
        envelope=facts[purpose][2]
        _lock_persisted_model_identity(conn,case_args['expected_tenant'],envelope,
            canonical_hash(envelope.model_dump(mode='json',by_alias=True)),epochs[purpose])
    _recheck_locked_model_certificate_windows(conn,facts.values())


def _recheck_locked_model_certificate_windows(conn, facts):
    """Fresh native clock after ALL identity locks, not a caller COMMIT gate.

    Root/certificate/identity heads already remain locked and validated by the
    caller. Reuse the original strict crypto/half-open interval check without
    taking new locks, changing roles or authorizing execution.
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            checked_at=cur.execute('SELECT clock_timestamp() AS checked_at').fetchone()['checked_at']
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('post-identity-lock native clock unavailable') from exc
    for plan,root,envelope,_,_ in facts:
        validate_model_certificate_signature(plan,envelope.certificate,
            issuer_input=root,signature_base64=envelope.signature_base64,
            checked_at=checked_at,revoked_identity_ids=frozenset())


def validate_persisted_model_case_set(
    conn, *, expected_tenant, execution_id, manifest_hash, cases,
) -> None:
    """Verify every stored case's necessary signature/current identity facts.

    Root provenance, original approvals, joint admission, transport, Usage,
    settlement and Report remain independent gates. No roles, transactions or
    writes are created; all root/certificate/identity locks survive caller exit.
    """
    from aos_api.aip_model_eval_execution_contracts import ModelEvalPersistedCaseInput
    _require(isinstance(expected_tenant,TenantContext), 'typed whole-case tenant required')
    tenant=TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id,tenant.project_id)==('org-org','dev-project'), 'positive whole-case tenant required')
    _require(type(execution_id) is str and 1<=len(execution_id)<=200 and execution_id==execution_id.strip(),
             'exact whole-case execution required')
    _require(type(manifest_hash) is str and re.fullmatch(r'[0-9a-f]{64}',manifest_hash) is not None,
             'exact whole-case manifest hash required')
    _require(type(cases) is tuple and bool(cases), 'immutable complete case witnesses required')
    items=[ModelEvalPersistedCaseInput.model_validate(item) for item in cases]
    _require(conn.info.transaction_status==TransactionStatus.INTRANS, 'caller whole-case transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            ctx=cur.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org,
              current_setting('aos.project_id',true) AS project,current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(ctx is not None and (ctx['role'],ctx['org'],ctx['project'],ctx['isolation'])==
                     (ISSUER_OWNER,tenant.org_id,tenant.project_id,'serializable'), 'exact private whole-case SERIAL caller required')
            row=cur.execute(f'SELECT * FROM {SCHEMA}.manifest WHERE org_id=%s AND project_id=%s AND execution_id=%s',
                            (tenant.org_id,tenant.project_id,execution_id)).fetchone()
            _require(row is not None and isinstance(row['body'],(bytes,bytearray,memoryview)), 'original whole-case manifest required')
            raw=bytes(row['body'])
            _require(hashlib.sha256(raw).hexdigest()==row['content_hash']==manifest_hash,'whole-case manifest hash drifted')
            plan=ModelEvalExecutionManifest.model_validate_json(raw)
            _require(plan.tenant==tenant and plan.execution_id==execution_id and
                     canonical_hash(plan.model_dump(mode='json',by_alias=True))==manifest_hash, 'canonical whole-case manifest required')
            wanted={case.case_id for case in plan.cases}
            _require(len(items)==len(wanted) and {item.case_id for item in items}==wanted, 'complete unique case witnesses required')
            stored=cur.execute(f'SELECT case_id,purpose,attempt FROM {SCHEMA}.case_result WHERE org_id=%s AND project_id=%s AND execution_id=%s',
                               (tenant.org_id,tenant.project_id,execution_id)).fetchall()
            expected={(case,purpose,1) for case in wanted for purpose in ('target','judge')}
            _require(len(stored)==len(expected) and {(r['case_id'],r['purpose'],r['attempt']) for r in stored}==expected,
                     'persisted complete case set required')
            certificates={};roots={}
            for item in items:
                for purpose in ('target','judge'):
                    binding=getattr(item,purpose+'_binding')
                    _require(binding.certificate_hash not in certificates, 'unique whole-case certificates required')
                    meta=cur.execute(f'SELECT issuer_id,key_id,execution_id,case_id,purpose FROM {ISSUER_SCHEMA}.executor_certificate WHERE org_id=%s AND project_id=%s AND content_hash=%s',
                        (tenant.org_id,tenant.project_id,binding.certificate_hash)).fetchone()
                    _require(meta is not None and (meta['execution_id'],meta['case_id'],meta['purpose'])==
                             (execution_id,item.case_id,purpose),'exact whole-case certificate metadata required')
                    root_key=(meta['issuer_id'],meta['key_id']);root_value=(binding.root_epoch,binding.root_hash)
                    _require(root_key not in roots or roots[root_key]==root_value, 'consistent whole-case root binding required')
                    roots[root_key]=root_value
                    certificates[binding.certificate_hash]=(item,purpose,binding)
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('whole-case original records unavailable') from exc
    # Global ordering: all roots, then all certificates, then all identities.
    for (issuer,key),(epoch,digest) in sorted(roots.items()):
        read_model_issuer_epoch(conn,expected_tenant=tenant,issuer_id=issuer,issuer_key_id=key,
                               expected_epoch=epoch,root_hash=digest)
    facts={}
    for digest,(_,_,binding) in sorted(certificates.items()):
        facts[digest]=_read_persisted_model_certificate(conn,expected_tenant=tenant,execution_id=execution_id,
            manifest_hash=manifest_hash,certificate_hash=digest,root_hash=binding.root_hash,
            expected_root_epoch=binding.root_epoch,expected_certificate_epoch=binding.certificate_epoch)
    for digest in sorted(facts,key=lambda d:(facts[d][2].certificate.leg.identity_id,d)):
        item,purpose,_=certificates[digest]
        _lock_persisted_model_identity(conn,tenant,facts[digest][2],digest,getattr(item,purpose+'_identity_epoch'))
    for item in sorted(items,key=lambda item:item.case_id):
        _read_persisted_model_case(conn,expected_tenant=tenant,execution_id=execution_id,manifest_hash=manifest_hash,
            case_id=item.case_id,target_binding=item.target_binding,judge_binding=item.judge_binding,
            target_input=item.target_input,target_output=item.target_output,judge_input=item.judge_input,judge_output=item.judge_output)
    _recheck_locked_model_certificate_windows(conn,facts.values())


def validate_persisted_model_executor_set(
    conn, *, expected_tenant, execution_id, manifest_hash, certificates,
) -> None:
    """Necessary complete pretransport certificates, without output dependency.

    Same private caller, original immutable manifest, signatures and current
    heads only. Formal root provenance, approvals/Source/joint admission and
    execution authority remain independent; no roles, writes or transactions.
    """
    from aos_api.aip_model_eval_execution_contracts import ModelEvalPersistedExecutorInput
    _require(isinstance(expected_tenant,TenantContext),'typed executor-set tenant required')
    tenant=TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id,tenant.project_id)==('org-org','dev-project'),'positive executor-set tenant required')
    _require(type(execution_id) is str and 1<=len(execution_id)<=200 and execution_id==execution_id.strip(),
             'exact executor-set execution required')
    _require(type(manifest_hash) is str and re.fullmatch(r'[0-9a-f]{64}',manifest_hash) is not None,
             'exact executor-set manifest hash required')
    _require(type(certificates) is tuple and 0<len(certificates)<=40000,'immutable executor-set witnesses required')
    items=[ModelEvalPersistedExecutorInput.model_validate(value) for value in certificates]
    _require(conn.info.transaction_status==TransactionStatus.INTRANS,'caller executor-set transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            ctx=cur.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org,
                current_setting('aos.project_id',true) AS project,current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(ctx is not None and (ctx['role'],ctx['org'],ctx['project'],ctx['isolation'])==
                     (ISSUER_OWNER,tenant.org_id,tenant.project_id,'serializable'),'exact private executor-set SERIAL caller required')
            row=cur.execute(f'SELECT * FROM {SCHEMA}.manifest WHERE org_id=%s AND project_id=%s AND execution_id=%s',
                            (tenant.org_id,tenant.project_id,execution_id)).fetchone()
            _require(row is not None and isinstance(row['body'],(bytes,bytearray,memoryview)), 'original executor-set manifest required')
            raw=bytes(row['body']);plan=ModelEvalExecutionManifest.model_validate_json(raw)
            _require(hashlib.sha256(raw).hexdigest()==row['content_hash']==manifest_hash and plan.tenant==tenant
                     and plan.execution_id==execution_id and canonical_hash(plan.model_dump(mode='json',by_alias=True))==manifest_hash,
                     'canonical executor-set manifest required')
            wanted={(case.case_id,purpose) for case in plan.cases for purpose in ('target','judge')}
            _require(len(items)==len(wanted) and {(x.case_id,x.purpose) for x in items}==wanted
                     and len({x.certificate_hash for x in items})==len(items),'complete unique executor certificates required')
            rows=cur.execute(f'SELECT content_hash,case_id,purpose,attempt,issuer_id,key_id FROM {ISSUER_SCHEMA}.executor_certificate WHERE org_id=%s AND project_id=%s AND execution_id=%s',
                             (tenant.org_id,tenant.project_id,execution_id)).fetchall()
            _require(len(rows)==len(items) and {(r['case_id'],r['purpose'],r['attempt'],r['content_hash']) for r in rows}==
                     {(x.case_id,x.purpose,1,x.certificate_hash) for x in items},'persisted complete executor certificates required')
            meta={r['content_hash']:r for r in rows};roots={}
            for item in items:
                r=meta[item.certificate_hash];key=(r['issuer_id'],r['key_id']);value=(item.root_epoch,item.root_hash)
                _require(key not in roots or roots[key]==value,'consistent executor-set roots required');roots[key]=value
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('original executor-set records unavailable') from exc
    for (issuer,key),(epoch,digest) in sorted(roots.items()):
        read_model_issuer_epoch(conn,expected_tenant=tenant,issuer_id=issuer,issuer_key_id=key,expected_epoch=epoch,root_hash=digest)
    facts={}
    for item in sorted(items,key=lambda value:value.certificate_hash):
        facts[item.certificate_hash]=_read_persisted_model_certificate(conn,expected_tenant=tenant,execution_id=execution_id,
            manifest_hash=manifest_hash,certificate_hash=item.certificate_hash,root_hash=item.root_hash,
            expected_root_epoch=item.root_epoch,expected_certificate_epoch=item.certificate_epoch)
    for item in sorted(items,key=lambda value:(facts[value.certificate_hash][2].certificate.leg.identity_id,value.certificate_hash)):
        _lock_persisted_model_identity(conn,tenant,facts[item.certificate_hash][2],item.certificate_hash,item.identity_epoch)
    _recheck_locked_model_certificate_windows(conn,facts.values())


def _read_runtime_model_executor_set(conn, *, expected_tenant, execution_id, manifest_hash, certificates):
    """Runtime consumes same-caller server facts, never presented trust or authority."""
    from aos_api.aip_model_eval_execution_contracts import ModelEvalPersistedExecutorInput
    _require(type(conn) is psycopg.Connection and isinstance(expected_tenant,TenantContext),'native runtime executor caller required')
    tenant=TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id,tenant.project_id)==('org-org','dev-project'),'positive runtime executor tenant required')
    _require(type(execution_id) is str and 1<=len(execution_id)<=200 and execution_id==execution_id.strip(),'exact runtime executor identity required')
    _require(type(manifest_hash) is str and re.fullmatch(r'[0-9a-f]{64}',manifest_hash) is not None,'exact runtime executor hash required')
    _require(type(certificates) is tuple and 0<len(certificates)<=40000,'immutable runtime executor witnesses required')
    items=[ModelEvalPersistedExecutorInput.model_validate(value) for value in certificates]
    _require(conn.info.transaction_status==TransactionStatus.INTRANS,'runtime executor transaction required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            ctx=cur.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org,
                current_setting('aos.project_id',true) AS project,current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(ctx is not None and (ctx['role'],ctx['org'],ctx['project'],ctx['isolation'])==
                     ('aos_runtime',tenant.org_id,tenant.project_id,'serializable'),'exact runtime executor SERIAL caller required')
            facts=cur.execute('SELECT public.read_model_executor_set_facts(%s,%s) AS facts',(execution_id,manifest_hash)).fetchone()['facts']
            caller=cur.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('original runtime executor facts unavailable') from exc
    _require(facts['callerXid']==caller['xid'] and facts['callerPid']==caller['pid'] and facts['executionAllowed'] is False,
             'same-caller nonexecuting executor facts required')
    def parse(encoded,digest,model):
        try:raw=base64.b64decode(encoded,validate=True);value=model.model_validate_json(raw)
        except (TypeError,ValueError,ValidationError,binascii.Error) as exc:
            raise ModelExecutionPlanRejected('strict original runtime executor bytes required') from exc
        _require(hashlib.sha256(raw).hexdigest()==digest==canonical_hash(value.model_dump(mode='json',by_alias=True)),
                 'canonical original runtime executor bytes required')
        return value
    plan=parse(facts['manifestBody'],manifest_hash,ModelEvalExecutionManifest)
    _require(facts['manifestHash']==manifest_hash and plan.tenant==tenant and plan.execution_id==execution_id,'original runtime executor manifest required')
    wanted={(case.case_id,purpose) for case in plan.cases for purpose in ('target','judge')}
    stored=facts['certificates']
    _require(len(items)==len(stored)==len(wanted) and {(i.case_id,i.purpose) for i in items}==wanted
             and len({i.certificate_hash for i in items})==len(items)
             and {(r['caseId'],r['purpose'],r['certificateHash']) for r in stored}==
                 {(i.case_id,i.purpose,i.certificate_hash) for i in items},'complete original runtime executor set required')
    indexed={i.certificate_hash:i for i in items};verified=[]
    for row in stored:
        item=indexed[row['certificateHash']]
        _require((row['rootHash'],row['rootEpoch'],row['certificateEpoch'],row['identityEpoch'])==
                 (item.root_hash,item.root_epoch,item.certificate_epoch,item.identity_epoch),'exact runtime executor current epochs required')
        root=parse(row['rootBody'],row['rootHash'],ModelEvalIssuerVerificationInput)
        envelope=parse(row['certificateBody'],row['certificateHash'],ModelEvalSignedCertificateEnvelope)
        claim=envelope.certificate
        _require(claim.tenant==tenant and root.tenant==tenant and claim.execution_id==execution_id
                 and (claim.case_id,claim.purpose,claim.leg.attempt,claim.issuer_id,claim.issuer_key_id)==
                 (row['caseId'],row['purpose'],row['attempt'],row['issuerId'],row['issuerKeyId'])
                 and (root.issuer_id,root.issuer_key_id)==(row['issuerId'],row['issuerKeyId']), 'original runtime executor headers required')
        _require(row['identityActive'] is True and (row['identityId'],row['identityPurpose'],row['identityKeyHash'])==
                 (claim.leg.identity_id,claim.purpose,claim.leg.identity_key_hash),'original runtime executor identity binding required')
        verified.append((plan,root,envelope))
    # Server has locked every root/certificate/identity. Fresh clock follows
    # all waits AND parsing; no later business reads or caller COMMIT claim.
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            checked_at=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('runtime executor final clock unavailable') from exc
    for plan,root,envelope in verified:
        validate_model_certificate_signature(plan,envelope.certificate,issuer_input=root,signature_base64=envelope.signature_base64,
            checked_at=checked_at,revoked_identity_ids=frozenset())

    return plan,verified


def validate_runtime_model_executor_set(conn, *, expected_tenant, execution_id, manifest_hash, certificates) -> None:
    """Original public necessary validation contract; no fact or authority return."""
    _read_runtime_model_executor_set(conn,expected_tenant=expected_tenant,
        execution_id=execution_id,manifest_hash=manifest_hash,certificates=certificates)


def validate_persisted_model_target_result(
    conn: psycopg.Connection, *, expected_tenant: TenantContext,
    execution_id: str, manifest_hash: str, case_id: str,
    target_binding, target_input: bytes, target_output: bytes,
    expected_identity_epoch: int,
) -> None:
    """Necessary original Target proof before Judge exists; no admission.

    Requires private issuer SERIAL caller. Formal root provenance, actual
    transport, original joint Intent, Usage and settlement remain separate.
    No Judge output dependency, caller flag, role switch or transaction repair.
    """
    _require(type(conn) is psycopg.Connection, 'native Target result caller required')
    _require(type(case_id) is str and 1 <= len(case_id) <= 200
             and case_id == case_id.strip(), 'exact Target case required')
    _require(type(expected_identity_epoch) is int and expected_identity_epoch >= 1,
             'native positive Target identity epoch required')
    binding=ModelEvalCasePersistenceBinding.model_validate(target_binding)
    facts=_read_persisted_model_certificate(conn,expected_tenant=expected_tenant,
        execution_id=execution_id,manifest_hash=manifest_hash,
        certificate_hash=binding.certificate_hash,root_hash=binding.root_hash,
        expected_root_epoch=binding.root_epoch,
        expected_certificate_epoch=binding.certificate_epoch)
    plan,root,certificate,created_at,_=facts
    _require(certificate.certificate.purpose=='target'
             and certificate.certificate.case_id==case_id,
             'exact original Target certificate required')
    _lock_persisted_model_identity(conn,plan.tenant,certificate,
        binding.certificate_hash,expected_identity_epoch)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            row=cur.execute(f"SELECT * FROM {SCHEMA}.case_result WHERE org_id=%s AND project_id=%s AND execution_id=%s AND case_id=%s AND purpose='target' AND attempt=1",
                (plan.tenant.org_id,plan.tenant.project_id,execution_id,case_id)).fetchone()
            _require(row is not None and isinstance(row['body'],(bytes,bytearray,memoryview)),
                     'original Target case bytes unavailable')
            raw=bytes(row['body'])
            _require(hashlib.sha256(raw).hexdigest()==row['content_hash']==binding.case_hash,
                     'original Target case byte hash drifted')
            case=ModelEvalSignedCaseEnvelope.model_validate_json(raw)
            _require(canonical_hash(case.model_dump(mode='json',by_alias=True))==binding.case_hash,
                     'canonical complete Target case bytes required')
            claim=case.payload.claim
            _require(claim.purpose=='target' and claim.case_id==case_id
                     and claim.execution_id==execution_id and claim.tenant==plan.tenant
                     and created_at<=claim.occurred_at,
                     'persisted Target case header or creation order drifted')
            checked_at=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('original Target case read unavailable') from exc
    validate_model_case_signature(plan,case,certificate_envelope=certificate,
        issuer_input=root,checked_at=checked_at,revoked_identity_ids=frozenset(),
        input_bytes=target_input,output_bytes=target_output)



def _read_runtime_model_target_result(conn, *, expected_tenant, execution_id,
    manifest_hash, case_id, certificates, target_binding, target_input: bytes,
    target_output: bytes) -> None:
    """Same-caller original Target proof before Judge, never joint admission."""
    _require(type(case_id) is str and 1<=len(case_id)<=200 and case_id==case_id.strip(),
             'exact runtime Target case required')
    binding=ModelEvalCasePersistenceBinding.model_validate(target_binding)
    plan,verified=_read_runtime_model_executor_set(conn,expected_tenant=expected_tenant,
        execution_id=execution_id,manifest_hash=manifest_hash,certificates=certificates)
    matching=[(root,cert) for _,root,cert in verified
              if cert.certificate.case_id==case_id and cert.certificate.purpose=='target']
    _require(len(matching)==1,'original runtime Target certificate required')
    root,certificate=matching[0]
    from aos_api.aip_model_eval_execution_contracts import ModelEvalPersistedExecutorInput
    item=next(ModelEvalPersistedExecutorInput.model_validate(v) for v in certificates
              if ModelEvalPersistedExecutorInput.model_validate(v).certificate_hash==canonical_hash(certificate.model_dump(mode='json',by_alias=True)))
    _require((binding.certificate_hash,binding.root_hash,binding.root_epoch,binding.certificate_epoch)==
             (item.certificate_hash,item.root_hash,item.root_epoch,item.certificate_epoch),
             'exact runtime Target proof binding required')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            facts=cur.execute('SELECT public.read_model_target_result_facts(%s,%s,%s) AS facts',
                (execution_id,manifest_hash,case_id)).fetchone()['facts']
            caller=cur.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        _require(facts['callerXid']==caller['xid'] and facts['callerPid']==caller['pid']
                 and facts['executionAllowed'] is False,'same-caller nonexecuting Target facts required')
        _require(type(facts.get('producerXid')) is str and re.fullmatch(r'[1-9][0-9]*',facts['producerXid']) is not None
                 and facts.get('producerStatus')=='committed','native committed original Target producer required')
        raw=base64.b64decode(facts['targetBody'],validate=True)
        case=ModelEvalSignedCaseEnvelope.model_validate_json(raw)
        _require(hashlib.sha256(raw).hexdigest()==facts['targetHash']==binding.case_hash==
                 canonical_hash(case.model_dump(mode='json',by_alias=True)),
                 'canonical original runtime Target bytes required')
        created=datetime.fromisoformat(facts['certificateCreatedAt'])
        claim=case.payload.claim
        _require(claim.tenant==plan.tenant and claim.execution_id==execution_id
                 and claim.case_id==case_id and claim.purpose=='target'
                 and created<=claim.occurred_at,'original runtime Target header and creation order required')
        with conn.cursor(row_factory=dict_row) as cur:
            checked_at=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    except psycopg.Error as exc:
        raise ModelExecutionPlanRejected('original runtime Target facts unavailable') from exc
    # Every original executor lock survives; recheck ALL windows after result
    # reads/parsing, without a new lock or any claim about actual COMMIT.
    for original,issuer,envelope in verified:
        validate_model_certificate_signature(original,envelope.certificate,issuer_input=issuer,
            signature_base64=envelope.signature_base64,checked_at=checked_at,revoked_identity_ids=frozenset())
    validate_model_case_signature(plan,case,certificate_envelope=certificate,
        issuer_input=root,checked_at=checked_at,revoked_identity_ids=frozenset(),
        input_bytes=target_input,output_bytes=target_output)

    return plan, verified, case


def validate_runtime_model_target_result(conn, *, expected_tenant, execution_id,
    manifest_hash: str, case_id: str, target_binding, certificates, target_input: bytes,
    target_output: bytes) -> None:
    """Verify committed original Target; preserve the nonexecuting public API."""
    _read_runtime_model_target_result(conn, expected_tenant=expected_tenant,
        execution_id=execution_id, manifest_hash=manifest_hash, case_id=case_id,
        target_binding=target_binding, certificates=certificates,
        target_input=target_input, target_output=target_output)


def prepare_runtime_model_judge_input(conn, *, expected_output: bytes | None, **target_args) -> bytes:
    """Bind Judge bytes to committed Target, without authority or transport grants.

    Expected bytes are a manifest-hash witness only. Their original artifact,
    joint admission, token/cost allocation and actual transport remain required.
    """
    plan, verified, target = _read_runtime_model_target_result(conn, **target_args)
    case = next(item for item in plan.cases if item.case_id == target.payload.claim.case_id)
    if case.expected_hash is None:
        _require(expected_output is None, 'absent expected artifact requires no bytes')
    else:
        _require(type(expected_output) is bytes and hashlib.sha256(expected_output).hexdigest() == case.expected_hash,
                 'exact original expected hash witness required')
    payload = dict(schemaVersion='aos.model-eval-judge-input/v1',
        tenant=plan.tenant.model_dump(mode='json', by_alias=True),
        executionId=plan.execution_id, manifestHash=target.payload.claim.manifest_hash,
        caseId=case.case_id, judgeLeg=case.judge.model_dump(mode='json', by_alias=True),
        targetCaseHash=canonical_hash(target.model_dump(mode='json', by_alias=True)),
        actualHash=target.payload.claim.output_hash,
        actualBase64=base64.b64encode(target_args['target_output']).decode('ascii'),
        expectedHash=case.expected_hash,
        expectedBase64=None if expected_output is None else base64.b64encode(expected_output).decode('ascii'),
        executionAllowed=False)
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    with conn.cursor(row_factory=dict_row) as cur:
        checked_at = cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    for original, issuer, envelope in verified:
        validate_model_certificate_signature(original, envelope.certificate, issuer_input=issuer,
            signature_base64=envelope.signature_base64, checked_at=checked_at, revoked_identity_ids=frozenset())
    return raw
