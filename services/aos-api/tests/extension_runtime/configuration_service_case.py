"""Signed live-owner service integration, only the caller's isolated schema."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest


def exercise_configuration_service(connect,store,reader,validator,scope,action,verified,generation):
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.asset_registry.control_policy import CONFIGURE_RUNTIME_OPERATION
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.configuration_authorization import ConfigurationAuthorization
    from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.extension_runtime.configuration_commit import commit_configuration
    from aos_api.extension_runtime.binding_store import RuntimeBindingStore
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
    path=Path(__file__).resolve().parents[2]/'alembic/versions/ar1_002_runtime_configuration.py'
    spec=importlib.util.spec_from_file_location('signed_configuration_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with connect() as c:
        migration.op=SimpleNamespace(execute=c.execute);migration.upgrade()
        c.execute('CREATE TABLE test_signed_config_refs(purpose text,ref_id text,revision bigint,hash text)')
        c.execute('GRANT SELECT,UPDATE ON test_signed_config_refs TO aos_runtime')
        def ref(purpose):
            value=dict(authority='test.signed.configuration',id=purpose,revision=1,hash='sha256:'+'a'*64)
            c.execute('INSERT INTO test_signed_config_refs VALUES(%s,%s,1,%s)',(purpose,purpose,value['hash']))
            return value
        document=dict(roleRefs=(ref('role'),),dataRefs=(ref('data'),),budgetRef=ref('budget'),policyRef=ref('policy'))

    def permission(c,*,installation_id,actor,**_):
        etag=c.execute('SELECT etag_version FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s',
            (scope['org_id'],scope['project_id'],installation_id)).fetchone()['etag_version']
        locked=store.lock_for_transition_in_transaction(c,**scope,installation_id=installation_id,expected_etag_version=etag)
        return CurrentControlPermission(operation=CONFIGURE_RUNTIME_OPERATION)(conn=c,locked=locked,actor=actor)
    def reference(c,*,purpose,ref,**_):
        return c.execute('SELECT ref_id FROM test_signed_config_refs WHERE purpose=%s AND ref_id=%s AND revision=%s AND hash=%s FOR SHARE',
            (purpose,ref.id,ref.revision,ref.hash)).fetchone() is not None
    authorize=ConfigurationAuthorization(permission=permission,readers={
        (purpose,'test.signed.configuration'):reference for purpose in ('role','data','budget','policy')})
    write=dict(**scope,installation_id=verified.installation_id,generation=str(generation),actor=action['actor'],
        expected_installation_etag=verified.etag_version,expected_binding_revision=1,
        idempotency_key='signed-config-version',configuration=document,authorize=authorize)
    with connect() as c:
        apply_asset_transaction_scope(c,**scope)
        first=append_configuration(c,**write)
    service=RuntimeConfigurationService(installation_store=store,installation_reader=reader,revalidator=validator,authorize=authorize)
    target=dict(generation=str(generation),bindingRevision=1,configRef=first.model_dump(mode='json'))
    request=dict(**action,kind='configure',idempotency_key='signed-configure',if_match=f'"{verified.etag_version}"',target=target)
    accepted=service.request(**request)
    assert accepted.status_code==202
    assert service.request(**request).replayed
    with pytest.raises(ValueError):service.request(**{**request,'idempotency_key':'competing-configure'})
    with connect() as c:c.execute("UPDATE meta_membership SET role='viewer'")
    with pytest.raises(AssetRegistryError):service.request(**request)
    with connect() as c:c.execute("UPDATE meta_membership SET role='admin'")
    with connect() as c:
        apply_asset_transaction_scope(c,**scope)
        operations=RuntimeOperationStore()
        operation_id=accepted.response_json['operationId']
        validated=operations.advance(c,**scope,operation_id=operation_id,expected_revision=1,phase='validating')
        fenced=RuntimeBindingStore().fence(c,**scope,installation_id=verified.installation_id,generation=generation,
            operation_id=operation_id,expected_operation_revision=validated.revision,expected_binding_revision=1)
        # No application job was admitted in this isolated lifecycle fixture.
        # This seam does NOT attest the production async broker's drain state.
        commit_configuration(c,**scope,operation_id=operation_id,expected_revision=fenced.revision,
            authorize=authorize,check_drained=lambda *a,**k:True)
    with connect() as c:
        apply_asset_transaction_scope(c,**scope)
        second=append_configuration(c,**{**write,'expected_binding_revision':3,'idempotency_key':'second-signed-config'},previous_ref=first)
        assert c.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
            'enabled':False,'operation_fence':True,'observed_state':'unknown'}
    target.update(bindingRevision=3)
    enable={**request,'kind':'enable','idempotency_key':'signed-enable','target':target}
    with pytest.raises(ValueError):service.request(**{**enable,'target':{**target,'configRef':second.model_dump(mode='json')}})
    enabled=service.request(**enable)
    assert enabled.status_code==202
    assert service.request(**enable).replayed
    return dict(authorize=authorize,operation_id=enabled.response_json['operationId'],expected_revision=enabled.response_json['revision'])
