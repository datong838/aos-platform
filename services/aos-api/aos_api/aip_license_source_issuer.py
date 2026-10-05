"""Consume original independent approval; caller owns the sole transaction commit."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4
import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.auth import Principal
from aos_api.aip_action_store import AipActionStore, canonical_hash
from aos_api.aip_agent_registry_contracts import RegistryReceipt
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_license_source_approval import (
    SourceApprovalDatabaseConfig, SourceLicenseDatabaseBlocked, authenticate_source_license_command,
)
from aos_api.aip_license_source_authority import LicenseSourceFact, read_license_source_fact
from aos_api.aip_license_source_issuer_contracts import (
    SourceLicenseIssuanceCommand, source_license_issuance_binding,
)
from aos_api.aip_license_source_proposal import (
    SourceLicenseProposalGuard, require_source_issuer_identity,
)
from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy, REQUIRED_RELEASE_EVIDENCE
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

OPERATION = 'source_license.issue'
ISSUER = 'aos_source_license_issuer'


class SourceLicenseIssuanceBlocked(ValueError):
    pass


class SourceLicenseIssuanceConflict(SourceLicenseIssuanceBlocked):
    pass


@dataclass(frozen=True, slots=True)
class SourceLicenseIssuanceResult:
    receipt: RegistryReceipt
    source: LicenseSourceFact
    authorization: Literal['RESTRICTED_SOURCE_LICENSE_ONLY_NO_START'] = field(
        default='RESTRICTED_SOURCE_LICENSE_ONLY_NO_START', init=False)


def _now(conn) -> datetime:
    return conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']


def _lock_selected_registry(conn, scope, request):
    # This is the original writer lock, acquired before registry tuple locks.
    # Tuple locks detect relevant post-snapshot changes under SERIALIZABLE.
    conn.execute('SELECT pg_advisory_xact_lock(228,1)')
    lock = conn.execute('''SELECT l.lock_payload FROM public.bundle_installation i
        JOIN public.bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id
          AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
        JOIN public.bundle_composition_lock l ON l.org_id=r.org_id AND l.project_id=r.project_id
          AND l.composition_pk=r.composition_pk AND l.revision=r.lock_revision
        WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',
        (*scope.key, request.installation_id)).fetchone()
    if not lock:
        raise SourceLicenseIssuanceBlocked('SOURCE_ISSUER_INSTALLATION_LOCK_MISSING')
    resolved = lock['lock_payload'].get('resolved')
    if not isinstance(resolved, list) or not resolved:
        raise SourceLicenseIssuanceBlocked('SOURCE_ISSUER_RELEASE_LOCK_INVALID')
    expiry = []
    for selected in sorted(resolved, key=lambda item: (item['publisher'], item['id'], item['version'])):
        version = conn.execute('''SELECT v.version_pk FROM public.asset_bundle_version v
            JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk
            WHERE b.publisher=%s AND b.bundle_id=%s AND v.version=%s AND v.content_hash=%s
            FOR SHARE OF v''',
            (selected['publisher'], selected['id'], selected['version'], selected['contentHash'])).fetchall()
        if len(version) != 1:
            raise SourceLicenseIssuanceBlocked('SOURCE_ISSUER_SELECTED_RELEASE_DRIFT')
        rows = conn.execute('SELECT evidence_type,status,revoked_at,expires_at FROM public.asset_bundle_evidence '
            'WHERE version_pk=%s ORDER BY evidence_type,artifact_ref FOR SHARE',
            (version[0]['version_pk'],)).fetchall()
        required = {kind.value for kind in REQUIRED_RELEASE_EVIDENCE}
        expiry.extend(row['expires_at'] for row in rows if row['expires_at'] is not None
            and row['status'] == 'valid' and row['revoked_at'] is None and row['evidence_type'] in required)
    return tuple(expiry)


def issue_source_license_in_transaction(*, conn, principal, command, loader, release_policy):
    if (type(conn) is not psycopg.Connection or type(principal) is not Principal
        or principal.token_kind != 'oidc' or type(command) is not SourceLicenseIssuanceCommand
        or type(loader) is not ManifestLoader or type(release_policy) is not ReleasePolicy):
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_PRIVATE_ISSUER_CONTEXT_REQUIRED')
    command = SourceLicenseIssuanceCommand.model_validate(command.model_dump(mode='python', by_alias=True))
    scope = TenantScope(principal.org_id, principal.project_id)
    binding = source_license_issuance_binding(scope, principal.subject, command)
    require_source_issuer_identity(conn, scope)
    factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
    AipActionStore._idempotency_lock(conn, scope, OPERATION, command.idempotency_key)
    registry = AipAgentRegistryStore(factory)
    existing = registry._receipt_row(conn, scope, OPERATION, command.idempotency_key)
    if existing and existing['request_hash'] != binding.content_hash:
        raise SourceLicenseIssuanceConflict('SOURCE_LICENSE_IDEMPOTENCY_CONFLICT')
    ref = command.approved_proposal
    row = conn.execute('SELECT * FROM public.aip_action_proposal WHERE org_id=%s AND project_id=%s '
        'AND proposal_id=%s FOR SHARE', (*scope.key, ref.resource_id)).fetchone()
    if (not row or row['status'] != 'approved' or row['version'] != ref.revision
        or row['proposal_hash'] != ref.content_hash or row['created_by'] != principal.subject
        or row['action_type_id'] != 'aip_issue_source_license'
        or row['action_type_snapshot'].get('id') != 'aip_issue_source_license'):
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_EXACT_APPROVED_MAKER_REQUIRED')
    events = conn.execute("SELECT * FROM public.aip_action_approval_event WHERE org_id=%s AND project_id=%s "
        "AND proposal_id=%s AND decision='approved' FOR SHARE", (*scope.key, ref.resource_id)).fetchall()
    if len(events) != 1:
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_UNIQUE_ORIGINAL_APPROVAL_REQUIRED')
    event = events[0]
    eligibility = canonical_hash({'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
        'actorId': event['actor_id'], 'roles': ['owner'], 'slotId': 'checker.1',
        'approvalPolicyHash': row['approval_policy_hash']})
    if (event['actor_id'] == principal.subject or event['slot_id'] != 'checker.1'
        or event['proposal_version'] != row['version'] - 1 or event['proposal_hash'] != ref.content_hash
        or event['action_binding_hash'] != row['action_binding_hash']
        or event['approval_policy_hash'] != row['approval_policy_hash']
        or event['eligibility_snapshot_hash'] != eligibility or event['expires_at'] is None):
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_ORIGINAL_APPROVAL_BINDING_DRIFT')
    members = conn.execute('SELECT subject,role FROM public.meta_membership WHERE org_id=%s AND project_id=%s '
        'AND subject=ANY(%s) ORDER BY subject FOR SHARE',
        (*scope.key, [principal.subject, event['actor_id']])).fetchall()
    if len(members) != 2 or any(item['role'].lower() != 'owner' for item in members):
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_BOTH_CURRENT_OWNERS_REQUIRED')
    if conn.execute('SELECT 1 FROM public.aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s '
        'AND proposal_id=%s', (*scope.key, ref.resource_id)).fetchone():
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_PROPOSAL_WITHDRAWN')
    try:
        request = SourceLicenseProposalRequest.model_validate(row['payload']['requestedGrant'])
    except (ValidationError, KeyError, TypeError):
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_ORIGINAL_GRANT_INVALID') from None
    # Installation is locked before initialization and Registry, matching b88.
    conn.execute('SELECT installation_id FROM public.bundle_installation WHERE org_id=%s AND project_id=%s '
        'AND installation_id=%s FOR SHARE', (*scope.key, request.installation_id)).fetchone()
    from aos_api.aip_license_source_authority import lock_license_source_initialization
    source_ref = ExactRevisionRef.model_validate(request.source.model_dump(mode='python', by_alias=True))
    epoch = lock_license_source_initialization(conn, scope, source_ref, shared=False)
    evidence_expiry = _lock_selected_registry(conn, scope, request)
    guard = SourceLicenseProposalGuard(conn=conn, factory=factory, principal=principal,
        request=request, loader=loader, release_policy=release_policy)
    guard.check_replay(factory._connection, scope, principal.subject, row)
    draft = conn.execute('SELECT status FROM public.aip_action_draft WHERE org_id=%s AND project_id=%s '
        'AND proposal_id=%s', (*scope.key, ref.resource_id)).fetchone()
    if not draft or draft['status'] != 'approved':
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_APPROVED_ORIGINAL_DRAFT_REQUIRED')
    checked_at = _now(conn)
    expires_at = min(row['expires_at'], event['expires_at'], request.valid_until, *evidence_expiry)
    if not request.valid_from <= checked_at < expires_at:
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_APPROVAL_OR_EVIDENCE_EXPIRED')
    authorization = {'schema': 'aos-source-license-authorization/v1',
        'approvedProposal': ref.model_dump(mode='json', by_alias=True),
        'maker': principal.subject, 'checker': event['actor_id'], 'approvalEventId': event['approval_event_id'],
        'grantBindingHash': row['action_binding_hash'], 'requestedGrant': request.model_dump(mode='json', by_alias=True)}
    policy = request.policy_ref.model_dump(mode='json', by_alias=True)
    head = conn.execute('SELECT * FROM public.aip_license_source_head WHERE org_id=%s AND project_id=%s '
        'AND bundle_id=%s AND revision=%s AND content_hash=%s',
        (*scope.key, source_ref.resource_id, source_ref.revision, source_ref.content_hash)).fetchone()
    if existing:
        result_ref = existing['result_ref']
        issued = conn.execute('SELECT * FROM public.aip_license_source_issuance WHERE org_id=%s AND project_id=%s '
            'AND issuance_id=%s', (*scope.key, result_ref.get('resourceId'))).fetchone()
        if (not issued or not head or head['issuance_id'] != issued['issuance_id']
            or issued['receipt_id'] != existing['receipt_id'] or issued['owner_authorization_ref'] != authorization
            or issued['policy_ref'] != policy or issued['installation_etag'] != request.installation_etag
            or str(issued['installation_id']) != request.installation_id or head['epoch'] != epoch
            or (issued['bundle_id'], issued['revision'], issued['content_hash']) != (
                source_ref.resource_id, source_ref.revision, source_ref.content_hash)
            or existing['created_by'] != principal.subject or existing['status'] != 'applied'
            or existing['resource_ref'] != registry._ref('ActionProposal', ref.resource_id,
                revision=str(ref.revision)).model_dump(mode='json', by_alias=True)
            or result_ref != registry._ref('SourceLicenseIssuance', issued['issuance_id']).model_dump(mode='json', by_alias=True)):
            raise SourceLicenseIssuanceConflict('SOURCE_LICENSE_RECEIPT_RECONCILIATION_DRIFT')
        receipt = registry._receipt_from_row(scope, existing)
    else:
        if head:
            raise SourceLicenseIssuanceConflict('SOURCE_LICENSE_ALREADY_ISSUED')
        issuance_id = 'source-license-' + uuid4().hex
        receipt = registry._insert_receipt(conn, scope, OPERATION, command.idempotency_key,
            binding.content_hash, 'ActionProposal', ref.resource_id, 'SourceLicenseIssuance', issuance_id,
            principal.subject, checked_at, source_revision=str(ref.revision))
        conn.execute('''INSERT INTO public.aip_license_source_issuance
            (org_id,project_id,issuance_id,bundle_id,revision,content_hash,installation_id,installation_etag,
             receipt_id,owner_authorization_ref,policy_ref,issued_at,expires_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (*scope.key, issuance_id, source_ref.resource_id, source_ref.revision, source_ref.content_hash,
             request.installation_id, request.installation_etag, receipt.receipt_id,
             Jsonb(authorization), Jsonb(policy), checked_at, expires_at))
        conn.execute('''INSERT INTO public.aip_license_source_head
            (org_id,project_id,bundle_id,revision,content_hash,issuance_id,epoch) VALUES(%s,%s,%s,%s,%s,%s,%s)''',
            (*scope.key, source_ref.resource_id, source_ref.revision, source_ref.content_hash, issuance_id, epoch))
    # Reuse the original source reader and signed-policy validator after result
    # construction. Any failure leaves receipt/issuance/head in the same rollback.
    fact = read_license_source_fact(conn, scope, source_ref, checked_at=_now(conn))
    result = SourceLicenseIssuanceResult(receipt, fact)
    guard.check_replay(factory._connection, scope, principal.subject, row)
    if _now(conn) >= min(expires_at, fact.expires_at):
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_EXPIRED_BEFORE_COMMIT')
    return result


@dataclass(frozen=True)
class SourceIssuerDatabaseConfig(SourceApprovalDatabaseConfig):
    """Reuse private credential validation; fixed issuer login is separate."""


@contextmanager
def connect_source_issuer(config, scope):
    if (type(config) is not SourceIssuerDatabaseConfig or type(scope) is not TenantScope
        or any(os.environ.get(name) for name in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'))):
        raise SourceLicenseDatabaseBlocked('SOURCE_ISSUER_EXACT_CONNECTION_REQUIRED')
    config.__post_init__()
    try:
        conn = psycopg.connect(host=config.host, port=config.port, dbname=config.database, user=ISSUER,
            passfile=str(config.passfile), require_auth='scram-sha-256', connect_timeout=5, row_factory=dict_row,
            options='-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000')
    except Exception:
        raise SourceLicenseDatabaseBlocked('SOURCE_ISSUER_CONNECTION_FAILED') from None
    with conn:
        conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
        conn.read_only = False
        conn.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
        apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
        require_source_issuer_identity(conn, scope)
        observed = conn.execute("""SELECT current_database() AS db,
            (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms,
            (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms,
            (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_timeout_ms""").fetchone()
        if (observed != {'db': config.database, 'statement_timeout_ms': 10000,
                        'lock_timeout_ms': 5000, 'idle_timeout_ms': 10000} or not conn.pgconn.used_password):
            raise SourceLicenseDatabaseBlocked('SOURCE_ISSUER_CONNECTION_IDENTITY_DRIFT')
        yield conn


def execute_source_license_issuance(command, *, database, loader, release_policy):
    if type(command) is not SourceLicenseIssuanceCommand:
        raise SourceLicenseIssuanceBlocked('SOURCE_LICENSE_EXACT_ISSUANCE_COMMAND_REQUIRED')
    command = SourceLicenseIssuanceCommand.model_validate(command.model_dump(mode='python', by_alias=True))
    principal = authenticate_source_license_command(command)
    with connect_source_issuer(database, TenantScope(principal.org_id, principal.project_id)) as conn:
        result = issue_source_license_in_transaction(conn=conn, principal=principal, command=command,
            loader=loader, release_policy=release_policy)
    return result
