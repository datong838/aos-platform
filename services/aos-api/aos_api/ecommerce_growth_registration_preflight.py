"""Current registration target check, without registering or granting dispatch."""

from collections.abc import Mapping

from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest, preview_registration
from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
from aos_api.extension_runtime.configuration_contracts import ConfigurationRef
from aos_api.extension_runtime.configuration_store import read_configuration
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.tenant_scope import TenantScope


def require_registration_runtime(binding, request: FirstDispatchRegistrationRequest) -> None:
    error = 'REGISTRATION_RUNTIME_TARGET_INVALID'
    if not isinstance(binding, Mapping):
        raise ValueError(error)
    expected = dict(revision=request.bindingRevision, execution_epoch=request.executionEpoch,
                    installation_revision=request.installationRef.revision)
    if (any(type(binding.get(key)) is not int or binding[key] != value for key,value in expected.items())
            or str(binding.get('generation')) != request.generation
            or binding.get('enabled') is not True or binding.get('operation_fence') is not False
            or binding.get('desired_state') != 'enabled' or binding.get('observed_state') != 'ready'):
        raise ValueError(error)
    try:
        config = ConfigurationRef.model_validate(binding.get('config_ref'))
    except (ValueError, TypeError):
        raise ValueError(error) from None
    if config != request.configRef:
        raise ValueError(error)


def registration_preflight(conn, *, scope: TenantScope, request: FirstDispatchRegistrationRequest,
                           actor: str, installation_store, configuration_authorize) -> dict:
    if (type(scope) is not TenantScope or type(request) is not FirstDispatchRegistrationRequest
            or type(installation_store) is not PostgresInstallationStore
            or type(configuration_authorize) is not CurrentFourSourceConfigurationAuthorization):
        raise TypeError('current production registration dependencies required')
    request = FirstDispatchRegistrationRequest.model_validate(request.model_dump(mode='python',by_alias=True))
    _require_transaction(conn)
    actual = conn.execute("SELECT current_setting('aos.org_id',true) AS org_id, "
                          "current_setting('aos.project_id',true) AS project_id").fetchone()
    if actual is None or (actual['org_id'], actual['project_id']) != scope.key:
        raise PermissionError('registration transaction scope differs')
    target = request.installationRef
    locked = installation_store.lock_for_transition_in_transaction(conn,org_id=scope.org_id,
        project_id=scope.project_id,installation_id=target.installation_id,expected_etag_version=target.revision)
    if locked.record.state != 'active':
        raise ValueError('REGISTRATION_INSTALLATION_NOT_ACTIVE')
    baseline = installation_store.load_active_baseline_in_transaction(conn,org_id=scope.org_id,
        project_id=scope.project_id,requested_ref=target)
    if len([p for p in baseline.lock.payload.resolved if p.id == 'solution.ecommerce.growth']) != 1:
        raise ValueError('REGISTRATION_GROWTH_PACKAGE_REQUIRED')
    rows = conn.execute('''SELECT generation,revision,execution_epoch,installation_revision,config_ref,
        enabled,operation_fence,desired_state,observed_state FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR SHARE''',
        (*scope.key,target.installation_id)).fetchall()
    if len(rows) != 1:
        raise ValueError('REGISTRATION_RUNTIME_TARGET_INVALID')
    require_registration_runtime(rows[0],request)
    read_configuration(conn,org_id=scope.org_id,project_id=scope.project_id,
        installation_id=target.installation_id,generation=request.generation,actor=actor,
        ref=request.configRef,authorize=configuration_authorize)
    count = conn.execute('''SELECT count(*) AS n FROM extension_operation_dispatch_binding
        WHERE org_id=%s AND project_id=%s AND operation_id=ANY(%s)''',
        (*scope.key,list(ECOMMERCE_GROWTH_OPERATIONS))).fetchone()['n']
    if count:
        raise ValueError('REGISTRATION_DISPATCH_ALREADY_EXISTS')
    result = preview_registration(request)
    result.update(currentConfigurationValidated=True,businessWrites=0,
        checkedAt=installation_store.read_control_clock_in_transaction(conn).isoformat())
    return result
