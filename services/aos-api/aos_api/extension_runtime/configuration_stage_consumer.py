"""Host-owned atomic staging primitive, without commit, IPC or activation."""
import json
from uuid import UUID

from psycopg.types.json import Jsonb

from aos_api.aip_runtime_configuration_sources import _current_scope, assemble_current_configuration
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import AssetRegistryError
from .configuration_authorization import ConfigurationAuthorization
from .configuration_stage_contracts import ConfigurationStageRequest
from .configuration_store import append_configuration
from .lifecycle_store import _values


_TABLE = 'extension_runtime_configuration_stage_request'


def process_one_configuration_stage(conn, *, org_id, project_id, authorize):
    """Caller must own the complete short transaction and trusted authorization.

    A known rejection rolls back staging in a savepoint, then records rejection.
    Unexpected database errors escape so the caller rolls back the entire unit.
    Production Host composition must additionally verify connection isolation.
    """
    scope = _current_scope(conn, org_id, project_id)
    if not isinstance(authorize, ConfigurationAuthorization):
        raise TypeError('trusted current configuration authorization required')
    candidate = conn.execute(f'''SELECT request_id,installation_id FROM {_TABLE}
        WHERE org_id=%s AND project_id=%s AND state='requested'
        ORDER BY created_at,request_id LIMIT 1''', scope).fetchone()
    if candidate is None:
        return None
    identity, installation = _values(candidate, ('request_id', 'installation_id'))
    # Follow the installation-first control lock order before claiming this row.
    conn.execute('''SELECT installation_id FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
        (*scope, installation)).fetchone()
    row = conn.execute(f'''SELECT subject,request_json,request_hash,deadline<=clock_timestamp() AS expired
        FROM {_TABLE} WHERE org_id=%s AND project_id=%s AND request_id=%s AND state='requested'
        FOR UPDATE SKIP LOCKED''', (*scope, identity)).fetchone()
    if row is None:
        return None
    subject, payload, digest, expired = _values(row, ('subject', 'request_json', 'request_hash', 'expired'))
    result = None
    state, failure = ('expired', 'REQUEST_EXPIRED') if expired else ('succeeded', None)
    if not expired:
        try:
            # The successful record and result must commit together, including
            # failures raised by the database's exact result association guard.
            with conn.transaction():
                request = ConfigurationStageRequest.model_validate_json(json.dumps(payload, allow_nan=False))
                if digest != canonical_sha256(dict(tenant=dict(orgId=org_id, projectId=project_id),
                                                    subject=subject, request=payload)):
                    raise ValueError('configuration staging digest differs')
                if UUID(request.target.installationId) != installation:
                    raise ValueError('configuration staging installation differs')
                document = assemble_current_configuration(conn, org_id=org_id, project_id=project_id,
                    policy_ref=request.policyRef, role_refs=request.roleRefs)
                result = append_configuration(conn, org_id=org_id, project_id=project_id,
                    installation_id=request.target.installationId, generation=request.target.generation,
                    expected_installation_etag=request.target.installationEtag,
                    expected_binding_revision=request.target.bindingRevision, actor=subject,
                    idempotency_key='configuration-stage:'+str(identity), configuration=document,
                    previous_ref=request.previousRef, authorize=authorize).model_dump(mode='json')
                _complete(conn, scope, identity, state='succeeded', result=result, failure=None)
        except (ValueError, LookupError, PermissionError, AssetRegistryError):
            state, failure, result = 'rejected', 'CONFIGURATION_ADMISSION_REJECTED', None
    if state != 'succeeded':
        _complete(conn, scope, identity, state=state, result=None, failure=failure)
    return dict(requestId=str(identity), state=state, result=result, failureCode=failure)


def _complete(conn, scope, identity, *, state, result, failure):
    row = conn.execute(f'''UPDATE {_TABLE} SET state=%s,revision=revision+1,
        completed_at=clock_timestamp(),result_json=%s,failure_code=%s
        WHERE org_id=%s AND project_id=%s AND request_id=%s AND state='requested'
        RETURNING request_id''', (state, Jsonb(result) if result is not None else None,
                                 failure, *scope, identity)).fetchone()
    if row is None:
        raise RuntimeError('configuration staging completion lost its request')


class ConfigurationStageConsumer:
    """Production entry point with the original closed AIP authority composition."""

    def __init__(self, *, connect, authorize, host_lease=None):
        from .configuration_authorization import CurrentFourSourceConfigurationAuthorization
        from .host_lease import OptInHostLease
        if (not callable(connect) or type(authorize) is not CurrentFourSourceConfigurationAuthorization
                or (host_lease is not None and type(host_lease) is not OptInHostLease)):
            raise TypeError('concrete current four-source Host authorization required')
        self.connect, self.authorize = connect, authorize
        self.host_lease = host_lease

    def run_once(self, *, org_id, project_id):
        from aos_api.tenant_scope import TenantScope
        from .consumer_connection import consumer_connection
        from .configuration_stage_preflight import configuration_source_acl_ready
        from .storage_ports import require_runtime_role
        TenantScope(org_id, project_id)
        scope = dict(org_id=org_id, project_id=project_id)
        fence = self.host_lease.fence_in_transaction if self.host_lease is not None else None
        with consumer_connection(self.connect, scope, fence=fence) as conn:
            require_runtime_role(conn, **scope, protected_tables=(
                _TABLE, 'extension_runtime_configuration',
            ))
            if not configuration_source_acl_ready(conn):
                raise PermissionError('configuration source issuer ACL drifted')
            return process_one_configuration_stage(conn, **scope, authorize=self.authorize)
