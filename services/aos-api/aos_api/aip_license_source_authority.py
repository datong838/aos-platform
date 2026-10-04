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
