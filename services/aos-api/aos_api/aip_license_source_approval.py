"""Independent original Owner approval; no source license issuance or start."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import os
import re
import stat

import psycopg
from pydantic import ValidationError

from aos_api.auth import Principal
from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_license_source_proposal import (
    SourceLicenseProposalBlocked, SourceLicenseProposalGuard, require_source_approval_identity,
)
from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


class SourceLicenseApprovalGuard:
    def __init__(self, *, conn, factory, principal, loader, release_policy):
        if (type(conn) is not psycopg.Connection or type(factory) is not TransactionBoundConnectFactory
            or type(principal) is not Principal or principal.token_kind!='oidc'
            or type(loader) is not ManifestLoader or type(release_policy) is not ReleasePolicy):
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PRIVATE_CHECKER_CONTEXT_REQUIRED')
        self.scope=TenantScope(principal.org_id,principal.project_id)
        self.actor=principal.subject
        if not self.actor or self.actor=='unknown' or self.actor!=self.actor.strip() or not self.actor.isprintable():
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CHECKER_SUBJECT_REQUIRED')
        require_source_approval_identity(conn,self.scope)
        self.native,self.factory,self.bound=conn,factory,factory._connection
        if self.bound.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']!=conn.info.backend_pid:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CALLER_TRANSACTION_DRIFT')
        self.loader,self.release_policy=loader,release_policy

    def check_proposal(self,conn,scope,actor,row):
        if conn is not self.bound or scope!=self.scope or actor!=self.actor:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CHECKER_TRANSACTION_DRIFT')
        require_source_approval_identity(self.native,scope)
        if row['created_by']==actor:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_INDEPENDENT_OWNER_CHECKER_REQUIRED')
        members=self.native.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s '
            'AND subject=%s FOR SHARE',(*scope.key,actor)).fetchall()
        if len(members)!=1 or members[0]['role'].lower()!='owner':
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CURRENT_CHECKER_OWNER_REQUIRED')
        if row['status']=='approved':
            from aos_api.aip_action_store import canonical_hash
            events=self.native.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s "
                "AND proposal_id=%s AND decision='approved'",(*scope.key,row['proposal_id'])).fetchall()
            expected_eligibility=canonical_hash({'tenant':{'orgId':scope.org_id,'projectId':scope.project_id},
                'actorId':actor,'roles':['owner'],'slotId':'checker.1','approvalPolicyHash':row['approval_policy_hash']})
            now=self.native.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if (len(events)!=1 or events[0]['actor_id']!=actor or events[0]['slot_id']!='checker.1'
                or events[0]['proposal_version']!=row['version']-1
                or events[0]['proposal_hash']!=row['proposal_hash']
                or events[0]['action_binding_hash']!=row['action_binding_hash']
                or events[0]['approval_policy_hash']!=row['approval_policy_hash']
                or events[0]['eligibility_snapshot_hash']!=expected_eligibility
                or events[0]['expires_at'] is None or not now<events[0]['expires_at']<=row['expires_at']):
                raise SourceLicenseProposalBlocked('SOURCE_LICENSE_APPROVAL_REPLAY_ACTOR_OR_BINDING_DRIFT')
        if self.native.execute('SELECT 1 FROM aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s '
            'AND proposal_id=%s',(*scope.key,row['proposal_id'])).fetchone():
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PROPOSAL_WITHDRAWN')
        try:
            request=SourceLicenseProposalRequest.model_validate(row['payload']['requestedGrant'])
        except (ValidationError,KeyError,TypeError):
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_ORIGINAL_GRANT_INVALID') from None
        # Stored maker context only recomputes the original request binding.
        # It does not authenticate a caller or confer issuer authority.
        maker=Principal(subject=row['created_by'],org_id=scope.org_id,project_id=scope.project_id,token_kind='oidc')
        original=SourceLicenseProposalGuard(conn=self.native,factory=self.factory,principal=maker,
            request=request,loader=self.loader,release_policy=self.release_policy)
        original.check_replay(conn,scope,row['created_by'],row)
        now=self.native.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if row['expires_at']<=now:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PROPOSAL_EXPIRED')
        return ('owner',)


def approve_source_license_in_transaction(*,conn,principal,proposal_id,idempotency_key,decision,loader,release_policy):
    """Caller owns commit; exact issuer and independent current Owner required."""
    from aos_api.aip_action_store import AipActionStore
    if (type(principal) is not Principal or type(decision) is not DecideActionProposalRequest
        or type(proposal_id) is not str or not proposal_id or proposal_id!=proposal_id.strip()
        or not proposal_id.isprintable() or type(idempotency_key) is not str
        or not 1<=len(idempotency_key)<=120 or idempotency_key!=idempotency_key.strip()
        or not idempotency_key.isprintable()):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CHECKER_COMMAND_INVALID')
    decision=DecideActionProposalRequest.model_validate(decision.model_dump(mode='python',by_alias=True))
    scope=TenantScope(principal.org_id,principal.project_id)
    factory=TransactionBoundConnectFactory(HostTransaction(conn),scope)
    guard=SourceLicenseApprovalGuard(conn=conn,factory=factory,principal=principal,
        loader=loader,release_policy=release_policy)
    result=AipActionStore(factory,source_license_approval_guard=guard).decide(
        scope,principal.subject,proposal_id,idempotency_key,decision)
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if result.proposal.expires_at<=now or any(event.expires_at<=now for event in result.approvals):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_APPROVAL_EXPIRED_BEFORE_COMMIT')
    return result


class SourceLicenseAuthBlocked(ValueError):
    pass


class SourceLicenseDatabaseBlocked(RuntimeError):
    pass


def authenticate_source_license_command(command):
    """Reverify an external signed JWT for every exact source command."""
    from aos_api.auth import resolve_principal
    from aos_api.aip_network_issuer_auth import _require_external_oidc_config
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseMakerCommand,SourceLicenseApprovalCommand
    from aos_api.aip_license_source_issuer_contracts import SourceLicenseIssuanceCommand
    if type(command) not in (SourceLicenseMakerCommand,SourceLicenseApprovalCommand,SourceLicenseIssuanceCommand):
        raise SourceLicenseAuthBlocked('SOURCE_LICENSE_AUTH_COMMAND_REQUIRED')
    try:
        command=type(command).model_validate(command.model_dump(mode='python',by_alias=True))
        _require_external_oidc_config()
        principal=resolve_principal(token=command.bearer_token.get_secret_value(),
            header_org=command.org_id,header_project=command.project_id)
    except Exception:
        raise SourceLicenseAuthBlocked('SOURCE_LICENSE_EXTERNAL_JWT_REQUIRED') from None
    if (type(principal) is not Principal or principal.token_kind!='oidc'
        or (principal.org_id,principal.project_id)!=(command.org_id,command.project_id)
        or not principal.subject or principal.subject=='unknown'
        or principal.subject!=principal.subject.strip() or not principal.subject.isprintable()):
        raise SourceLicenseAuthBlocked('SOURCE_LICENSE_AUTH_PRINCIPAL_INVALID')
    return principal


@dataclass(frozen=True)
class SourceApprovalDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self):
        if (self.host not in {'127.0.0.1','::1'} or type(self.port) is not int or not 1<=self.port<=65535
            or type(self.database) is not str or not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',self.database)):
            raise SourceLicenseDatabaseBlocked('SOURCE_APPROVAL_EXACT_DATABASE_REQUIRED')
        try:
            path=Path(self.passfile)
            parent,secret=path.parent.lstat(),path.lstat()
            if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(secret.st_mode)
                or parent.st_uid!=os.geteuid() or secret.st_uid!=os.geteuid()
                or stat.S_IMODE(parent.st_mode)!=0o700 or stat.S_IMODE(secret.st_mode)!=0o600
                or secret.st_nlink!=1):
                raise ValueError('private credential')
        except (OSError,ValueError,TypeError):
            raise SourceLicenseDatabaseBlocked('SOURCE_APPROVAL_PRIVATE_CREDENTIAL_REQUIRED') from None
        object.__setattr__(self,'passfile',path)


@contextmanager
def connect_source_approval(config,scope):
    """One native SERIAL transaction, exact login, actual SCRAM authentication."""
    from psycopg.rows import dict_row
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    if (type(config) is not SourceApprovalDatabaseConfig or type(scope) is not TenantScope
        or any(os.environ.get(name) for name in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'))):
        raise SourceLicenseDatabaseBlocked('SOURCE_APPROVAL_EXACT_CONNECTION_REQUIRED')
    config.__post_init__()
    try:
        conn=psycopg.connect(host=config.host,port=config.port,dbname=config.database,
            user='aos_source_license_approval_issuer',passfile=str(config.passfile),
            require_auth='scram-sha-256',connect_timeout=5,row_factory=dict_row,
            options='-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000')
    except Exception:
        raise SourceLicenseDatabaseBlocked('SOURCE_APPROVAL_CONNECTION_FAILED') from None
    with conn:
        conn.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
        conn.read_only=False
        conn.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
        apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
        require_source_approval_identity(conn,scope)
        observed=conn.execute("""SELECT current_database() AS db,
            (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms,
            (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms,
            (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_timeout_ms""").fetchone()
        if (observed!={'db':config.database,'statement_timeout_ms':10000,'lock_timeout_ms':5000,'idle_timeout_ms':10000}
            or not conn.pgconn.used_password):
            raise SourceLicenseDatabaseBlocked('SOURCE_APPROVAL_CONNECTION_IDENTITY_DRIFT')
        yield conn


def execute_source_license_approval(command,*,database,loader,release_policy):
    """Private adapter: authenticated actor, independent login, original approval."""
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseApprovalCommand
    if type(command) is not SourceLicenseApprovalCommand:
        raise SourceLicenseAuthBlocked('SOURCE_LICENSE_AUTH_COMMAND_REQUIRED')
    command=SourceLicenseApprovalCommand.model_validate(command.model_dump(mode='python',by_alias=True))
    principal=authenticate_source_license_command(command)
    with connect_source_approval(database,TenantScope(principal.org_id,principal.project_id)) as conn:
        result=approve_source_license_in_transaction(conn=conn,principal=principal,
            proposal_id=command.proposal_id,idempotency_key=command.idempotency_key,
            decision=command.decision,loader=loader,release_policy=release_policy)
    return result


def propose_authenticated_source_license_in_transaction(command,*,conn,loader,release_policy):
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseMakerCommand
    from aos_api.aip_license_source_proposal import propose_source_license_in_transaction
    if type(command) is not SourceLicenseMakerCommand:
        raise SourceLicenseAuthBlocked('SOURCE_LICENSE_AUTH_COMMAND_REQUIRED')
    command=SourceLicenseMakerCommand.model_validate(command.model_dump(mode='python',by_alias=True))
    principal=authenticate_source_license_command(command)
    return propose_source_license_in_transaction(conn=conn,principal=principal,request=command.request,
        idempotency_key=command.idempotency_key,loader=loader,release_policy=release_policy)
