"""Caller-owned transaction source facts/locks, never an issuance or start grant."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.pq import TransactionStatus

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.tenant_scope import TenantScope


class LicenseSourceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class LicenseSourceFact:
    source: ExactRevisionRef
    issuance_id: str
    epoch: int
    installation_id: str
    installation_etag: int
    receipt_id: str
    owner_authorization_ref: dict[str, Any]
    policy_ref: dict[str, Any]
    expires_at: datetime
    authorization: str = 'SOURCE_FACT_ONLY_NO_START'


def _require_scope(conn: Any, scope: TenantScope) -> None:
    if type(scope) is not TenantScope or conn.info.transaction_status != TransactionStatus.INTRANS:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_CALLER_TRANSACTION_REQUIRED')
    row = conn.execute("SELECT current_setting('aos.org_id',true) AS org,"
                       "current_setting('aos.project_id',true) AS project").fetchone()
    if row is None or (row['org'],row['project']) != scope.key:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_SCOPE_MISMATCH')



def lock_license_source_initialization(conn: Any, scope: TenantScope, ref: ExactRevisionRef, *, shared: bool = True) -> int:
    # Neutral coordination only. Frozen/current/licensed eligibility must be
    # checked by the formal caller; generic historical revocation stays valid.
    _require_scope(conn,scope)
    if not isinstance(ref,ExactRevisionRef) or ref.resource_type != 'EvidenceBundleRevision' or type(shared) is not bool:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_EXACT_REF_REQUIRED')
    try:
        row=conn.execute('SELECT public.aos_license_source_initialization_lock(%s,%s,%s,%s,%s,%s) AS epoch',
            (*scope.key,ref.resource_id,ref.revision,ref.content_hash,shared)).fetchone()
    except psycopg.errors.InsufficientPrivilege as exc:
        reason=exc.diag.message_primary
        if reason not in {'LICENSE_SOURCE_SCOPE_MISMATCH','LICENSE_SOURCE_EXACT_FROZEN_MISSING',
                          'LICENSE_SOURCE_INITIALIZATION_FENCE_MISSING'}:
            reason='LICENSE_SOURCE_FENCE_DENIED'
        raise LicenseSourceUnavailable(reason) from exc
    except psycopg.errors.UndefinedFunction as exc:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_INITIALIZATION_FENCE_UNAVAILABLE') from exc
    if row is None or row['epoch'] is None:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_INITIALIZATION_FENCE_MISSING')
    return int(row['epoch'])


def _lock_initialization_if_migrated(conn: Any, scope: TenantScope, ref: ExactRevisionRef, *, shared: bool) -> None:
    table=conn.execute("SELECT to_regclass('public.aip_license_source_initialization_fence') AS fence").fetchone()
    if table is not None and table['fence'] is not None:
        lock_license_source_initialization(conn,scope,ref,shared=shared)

def lock_license_source_head(conn: Any, scope: TenantScope, ref: ExactRevisionRef, *, shared: bool = True) -> int:
    _require_scope(conn,scope)
    if not isinstance(ref,ExactRevisionRef) or ref.resource_type != 'EvidenceBundleRevision' or type(shared) is not bool:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_EXACT_REF_REQUIRED')
    _lock_initialization_if_migrated(conn,scope,ref,shared=shared)
    try:
        row = conn.execute('SELECT public.aos_license_source_lock(%s,%s,%s,%s,%s,%s) AS epoch',
                           (*scope.key,ref.resource_id,ref.revision,ref.content_hash,shared)).fetchone()
    except psycopg.errors.InsufficientPrivilege as exc:
        reason = exc.diag.message_primary
        if reason not in {'LICENSE_SOURCE_SCOPE_MISMATCH','LICENSE_SOURCE_EXACT_FROZEN_MISSING',
                          'LICENSE_SOURCE_HEAD_MISSING'}:
            reason = 'LICENSE_SOURCE_FENCE_DENIED'
        raise LicenseSourceUnavailable(reason) from exc
    except psycopg.errors.UndefinedFunction as exc:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_FENCE_UNAVAILABLE') from exc
    if row is None or row['epoch'] is None:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_HEAD_MISSING')
    return int(row['epoch'])


def lock_existing_license_source_for_revoke(conn: Any, scope: TenantScope, bundle_id: str,
                                           revision: int, content_hash: str) -> None:
    # The live 135 database has no issuance table. Do not break generic evidence
    # while a separately gated real migration is still pending.
    table = conn.execute("SELECT to_regclass('public.aip_license_source_issuance') AS source_table").fetchone()
    if table is None or table['source_table'] is None:
        return
    actual=conn.execute('SELECT content_hash FROM public.aip_evidence_bundle_revision '
        'WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s',
        (*scope.key,bundle_id,revision)).fetchone()
    if actual is not None:
        # Request hash does not choose the source lock; preserve the original
        # Store's later hash/replay conflict classification.
        _lock_initialization_if_migrated(conn,scope,ExactRevisionRef(resource_type='EvidenceBundleRevision',
            resource_id=bundle_id,revision=revision,content_hash=actual['content_hash']),shared=False)
    issued = conn.execute('SELECT content_hash FROM public.aip_license_source_issuance WHERE '
        'org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s LIMIT 1',
        (*scope.key,bundle_id,revision)).fetchone()
    if issued is not None:
        # Missing function/head in a partially migrated trusted domain is an
        # error, never a fallback to the ordinary evidence path.
        lock_license_source_head(conn,scope,ExactRevisionRef(resource_type='EvidenceBundleRevision',
            resource_id=bundle_id,revision=revision,content_hash=issued['content_hash']),shared=False)


def read_license_source_fact(conn: Any, scope: TenantScope, ref: ExactRevisionRef, *, checked_at: datetime) -> LicenseSourceFact:
    if not isinstance(checked_at,datetime) or checked_at.utcoffset() is None:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_AWARE_CHECKED_AT_REQUIRED')
    epoch = lock_license_source_head(conn,scope,ref)
    row = conn.execute('''SELECT s.*,i.etag_version,i.current_revision,i.active_revision,
        EXISTS (SELECT 1 FROM public.aip_evidence_bundle_revoke_event r
            WHERE r.org_id=s.org_id AND r.project_id=s.project_id AND r.bundle_id=s.bundle_id
              AND r.revision=s.revision AND r.content_hash=s.content_hash) AS revoked
        FROM public.aip_license_source_head h
        JOIN public.aip_license_source_issuance s ON s.org_id=h.org_id AND s.project_id=h.project_id
            AND s.issuance_id=h.issuance_id AND s.bundle_id=h.bundle_id
            AND s.revision=h.revision AND s.content_hash=h.content_hash
        JOIN public.bundle_installation i ON i.org_id=s.org_id AND i.project_id=s.project_id
            AND i.installation_id=s.installation_id
        WHERE h.org_id=%s AND h.project_id=%s AND h.bundle_id=%s AND h.revision=%s AND h.content_hash=%s''',
        (*scope.key,ref.resource_id,ref.revision,ref.content_hash)).fetchone()
    if row is None:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_ISSUANCE_MISSING')
    if row['revoked']:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_REVOKED')
    if not row['issued_at'] <= checked_at < row['expires_at']:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_OUTSIDE_VALIDITY')
    if row['etag_version'] != row['installation_etag'] or row['active_revision'] != row['current_revision']:
        raise LicenseSourceUnavailable('LICENSE_SOURCE_INSTALLATION_DRIFT')
    return LicenseSourceFact(ref,row['issuance_id'],epoch,str(row['installation_id']),
        int(row['installation_etag']),row['receipt_id'],row['owner_authorization_ref'],
        row['policy_ref'],row['expires_at'])


@dataclass(frozen=True, slots=True)
class FormalLicenseSourceFact:
    source: LicenseSourceFact
    request: Any
    signed_policy: Any
    source_request_hash: str
    receipt_request_hash: str
    approval_event_id: str
    owners: tuple[dict[str, str], ...]
    checked_at: datetime
    valid_until: datetime
    authorization: str = 'FORMAL_SOURCE_FACT_ONLY_NO_START'


def _formal_source_issuance_row(conn, scope, ref):
    return conn.execute('''SELECT s.*,h.epoch AS source_epoch FROM public.aip_license_source_head h
        JOIN public.aip_license_source_issuance s ON s.org_id=h.org_id AND s.project_id=h.project_id
          AND s.issuance_id=h.issuance_id AND s.bundle_id=h.bundle_id
          AND s.revision=h.revision AND s.content_hash=h.content_hash
        WHERE h.org_id=%s AND h.project_id=%s AND h.bundle_id=%s
          AND h.revision=%s AND h.content_hash=%s''',
        (*scope.key, ref.resource_id, ref.revision, ref.content_hash)).fetchone()


def read_formal_license_source_facts(*, conn, scope, source_refs, installation_id,
                                    installation_revision, installation_etag, loader, release_policy):
    """Batch original approvals and current signed grants in the native caller.

    Discovery confers no authority. All Proposal/Approval locks precede Owners,
    installation and Source fences. No writes, fake maker Principal, or callback.
    """
    from uuid import UUID
    from pydantic import ValidationError
    from aos_api.aip_binding_evaluator_connection import require_binding_evaluator_transaction
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_agent_registry_store import AipAgentRegistryStore
    from aos_api.aip_license_source_issuer_contracts import (
        ApprovedSourceLicenseProposalRef, _source_issuance_request_hash,
    )
    from aos_api.aip_license_source_issuer import (
        _read_original_approved_source_proposal, _lock_selected_registry, _source_license_authorization,
    )
    from aos_api.aip_license_source_proposal import (
        _read_source_request_content_facts, _verify_formal_source_proposal_contents,
    )
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    require_binding_evaluator_transaction(conn, scope)
    try:
        if (type(source_refs) is not list or not 1 <= len(source_refs) <= 128
                or type(installation_id) is not str or str(UUID(installation_id)) != installation_id
                or type(installation_revision) is not int or installation_revision < 1
                or type(installation_etag) is not int or installation_etag < 1
                or type(loader) is not ManifestLoader or type(release_policy) is not ReleasePolicy):
            raise ValueError('exact private context required')
        refs = [FormalExactRef.model_validate(ref) for ref in source_refs]
        if (any(ref.asset_type != 'EvidenceBundleRevision' for ref in refs)
                or len({ref.asset_id for ref in refs}) != len(refs)):
            raise ValueError('unique exact sources required')
        exact = sorted((ExactRevisionRef(resource_type=ref.asset_type, resource_id=ref.asset_id,
            revision=ref.revision, content_hash=ref.content_hash) for ref in refs),
            key=lambda ref: (ref.resource_id, ref.revision, ref.content_hash))
        discovered = []
        for ref in exact:
            issued = _formal_source_issuance_row(conn, scope, ref)
            if issued is None:
                raise LicenseSourceUnavailable('FORMAL_SOURCE_ISSUANCE_MISSING')
            authorization = issued['owner_authorization_ref']
            if (type(authorization) is not dict or set(authorization) != {
                    'schema', 'approvedProposal', 'maker', 'checker', 'approvalEventId',
                    'grantBindingHash', 'requestedGrant'}
                    or authorization['schema'] != 'aos-source-license-authorization/v1'):
                raise LicenseSourceUnavailable('FORMAL_SOURCE_ORIGINAL_AUTHORIZATION_REQUIRED')
            approved = ApprovedSourceLicenseProposalRef.model_validate(authorization['approvedProposal'])
            maker = authorization['maker']
            if type(maker) is not str or not maker or maker != maker.strip() or any(c.isspace() for c in maker):
                raise ValueError('exact original maker required')
            discovered.append((ref, issued, approved, maker))
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
        raise LicenseSourceUnavailable('FORMAL_SOURCE_EXACT_CONTENT_REQUIRED') from None

    # Prelock every Proposal before taking any Approval lock, including batches.
    for proposal_id in sorted({entry[2].resource_id for entry in discovered}):
        conn.execute('SELECT proposal_id FROM public.aip_action_proposal WHERE org_id=%s AND project_id=%s '
            'AND proposal_id=%s FOR SHARE', (*scope.key, proposal_id)).fetchone()
    approvals = {}
    for _, _, approved, maker in sorted(discovered, key=lambda item: item[2].resource_id):
        row, event = _read_original_approved_source_proposal(conn, scope, approved, maker)
        if conn.execute('SELECT 1 FROM public.aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s '
            'AND proposal_id=%s', (*scope.key, approved.resource_id)).fetchone():
            raise LicenseSourceUnavailable('FORMAL_SOURCE_PROPOSAL_WITHDRAWN')
        approvals[approved.resource_id] = (row, event)
    subjects = sorted({subject for _, _, approved, maker in discovered
        for subject in (maker, approvals[approved.resource_id][1]['actor_id'])})
    owners = conn.execute('SELECT subject,role FROM public.meta_membership WHERE org_id=%s AND project_id=%s '
        'AND subject=ANY(%s) ORDER BY subject FOR SHARE', (*scope.key, subjects)).fetchall()
    if len(owners) != len(subjects) or any(row['role'].lower() != 'owner' for row in owners):
        raise LicenseSourceUnavailable('FORMAL_SOURCE_BOTH_CURRENT_OWNERS_REQUIRED')
    installed = conn.execute('SELECT current_revision,active_revision,etag_version FROM public.bundle_installation '
        'WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR SHARE',
        (*scope.key, installation_id)).fetchone()
    if (installed is None or installed['current_revision'] != installation_revision
            or installed['active_revision'] != installation_revision
            or installed['etag_version'] != installation_etag):
        raise LicenseSourceUnavailable('FORMAL_SOURCE_INSTALLATION_DRIFT')
    for ref, _, _, _ in discovered:
        lock_license_source_head(conn, scope, ref, shared=True)
    results = []
    for ref, issued, approved, maker in discovered:
        if _formal_source_issuance_row(conn, scope, ref) != issued:
            raise LicenseSourceUnavailable('FORMAL_SOURCE_DISCOVERY_DRIFT')
        row, event = approvals[approved.resource_id]
        try:
            request = SourceLicenseProposalRequest.model_validate(row['payload']['requestedGrant'])
        except (ValidationError, ValueError, TypeError, KeyError):
            raise LicenseSourceUnavailable('FORMAL_SOURCE_ORIGINAL_GRANT_INVALID') from None
        if (request.source.model_dump(mode="json", by_alias=True) != ref.model_dump(mode="json", by_alias=True)
                or (request.installation_id, request.installation_revision,
                request.installation_etag) != (installation_id, installation_revision, installation_etag)
                or not {'internal_business_analysis', 'traceable_derivation'} <= set(request.permitted_uses)):
            raise LicenseSourceUnavailable('FORMAL_SOURCE_EXACT_GRANT_SCOPE_REQUIRED')
        authorization = _source_license_authorization(approved, maker, event, row, request)
        if (issued['owner_authorization_ref'] != authorization
                or issued['policy_ref'] != request.policy_ref.model_dump(mode='json', by_alias=True)
                or str(issued['installation_id']) != installation_id
                or issued['installation_etag'] != installation_etag):
            raise LicenseSourceUnavailable('FORMAL_SOURCE_ORIGINAL_ISSUANCE_DRIFT')
        evidence_expiry = _lock_selected_registry(conn, scope, request)
        contents = _read_source_request_content_facts(conn=conn, scope=scope, maker=maker,
            request=request, loader=loader, release_policy=release_policy)
        _verify_formal_source_proposal_contents(conn, scope, maker, row, request, contents)
        draft = conn.execute('SELECT status FROM public.aip_action_draft WHERE org_id=%s AND project_id=%s '
            'AND proposal_id=%s', (*scope.key, approved.resource_id)).fetchone()
        if draft is None or draft['status'] != 'approved':
            raise LicenseSourceUnavailable('FORMAL_SOURCE_APPROVED_ORIGINAL_DRAFT_REQUIRED')
        receipt = conn.execute('SELECT * FROM public.aip_agent_registry_receipt WHERE org_id=%s AND project_id=%s '
            'AND receipt_id=%s', (*scope.key, issued['receipt_id'])).fetchone()
        request_hash = _source_issuance_request_hash(scope, maker, approved)
        if (receipt is None or receipt['operation'] != 'source_license.issue' or receipt['status'] != 'applied'
                or receipt['request_hash'] != request_hash or receipt['created_by'] != maker
                or receipt['created_at'] != issued['issued_at']
                or receipt['resource_ref'] != AipAgentRegistryStore._ref('ActionProposal', approved.resource_id,
                    revision=str(approved.revision)).model_dump(mode='json', by_alias=True)
                or receipt['result_ref'] != AipAgentRegistryStore._ref('SourceLicenseIssuance',
                    issued['issuance_id']).model_dump(mode='json', by_alias=True)):
            raise LicenseSourceUnavailable('FORMAL_SOURCE_ORIGINAL_RECEIPT_DRIFT')
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        fact = read_license_source_fact(conn, scope, ref, checked_at=now)
        valid_until = min(fact.expires_at, row['expires_at'], event['expires_at'],
            request.valid_until, request.proposal_expires_at, *evidence_expiry)
        if not request.valid_from <= now < valid_until:
            raise LicenseSourceUnavailable('FORMAL_SOURCE_CURRENT_GRANT_EXPIRED')
        pair = tuple(dict(owner) for owner in owners if owner['subject'] in {maker, event['actor_id']})
        results.append(FormalLicenseSourceFact(fact, request, contents.policy, contents.source_request_hash,
            request_hash, event['approval_event_id'], pair, now, valid_until))
    final_now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if any(final_now >= result.valid_until for result in results):
        raise LicenseSourceUnavailable('FORMAL_SOURCE_EXPIRED_AFTER_BATCH_READ')
    return tuple(results)
