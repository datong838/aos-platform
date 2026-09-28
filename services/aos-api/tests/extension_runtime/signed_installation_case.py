"""Real isolated Registry/OCI/Installation join; no business ports or activation."""
import asyncio
from datetime import datetime, timezone, timedelta
import json
import subprocess
import uuid
import hashlib
from contextlib import contextmanager

import pytest

from aos_api.asset_registry.composition_contracts import (
    CompositionRequest, CreateInstallationRequest, EmptyInstallationActionRequest,
    ApproveInstallationRequest,
)
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.contracts import LoadedBundle
from aos_api.asset_registry.errors import RuntimeOperationRequiredError, AssetRegistryError
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.resolver import resolve
from aos_api.asset_registry.signature import FrozenTrustRootProvider
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
from aos_api.extension_runtime.reconciler import ResourceJournal
from aos_api.extension_runtime.preparation_commit import commit_prepared
from aos_api.extension_runtime.signed_session import open_signed_session
from aos_api.extension_runtime.oci_driver import OciDriver


SCHEMA_PROBE_SQL='CREATE TABLE runtime_schema_probe (id bigint)'


def run_signed_installation(connect,helper,tmp_path,*,revoke=False,owned=False,planned=False,
                            worker_mode=None,schema_setup=None,lifecycle_probe=None,
                            package_probe=None):
    from test_admission import fixture
    from test_persistent_supervisor import build_session_image,CONTEXT
    from offline_registry import cached_registry_image
    from test_journaled_session_pg import assert_container_absent

    build=tmp_path/'image';build.mkdir()
    image,claims=build_session_image(build)
    with cached_registry_image(tmp_path/'registry',image,CONTEXT) as (manifest_digest,config_digest):
        def patch_index(files):
            path='artifacts/backend-image.json'
            index=json.loads(files[path])
            index['images'][0].update(imageDigest=manifest_digest,configDigest=config_digest)
            files[path]=json.dumps(index).encode()
            files['artifacts/schema-requirements.json']=json.dumps({'schemaVersion':1,'requirements':[
                {'version':'1','migrationHash':'sha256:'+hashlib.sha256(SCHEMA_PROBE_SQL.encode()).hexdigest()}]}).encode()
        now=datetime.now(timezone.utc)
        def manifest(value):
            value['spec']['contributions']=claims['contributions']
            value['metadata']['displayName']='隔离运行联合测试'
        args,_=fixture(patch_index,now=now,
            transform_manifest=manifest)
        record=args['record']
        test_roots=args['policy']._trust_roots
        class LocalRoots:
            def get_trust_root(self,**kwargs):return test_roots.get_trust_root(**kwargs)
            def snapshot(self):return FrozenTrustRootProvider({(record.publisher,test_roots.root.key_id):test_roots.root})
        roots=LocalRoots()
        policy=ReleasePolicy(trust_roots=roots)
        loaded=LoadedBundle(sourceRef='bundle://fixture/signed-runtime',manifest=record.manifest,
            artifacts=[{**item,'artifactRef':'bundle://fixture/signed-runtime/'+item['relativePath']} for item in record.artifacts],
            evidence=record.evidence,contentHash=record.content_hash,
            signature=record.signature,loadedAt=now)
        registry=RegistryService(store=PostgresRegistryStore(connect),loader=helper.FixedLoader(loaded,roots),
            trust_roots=roots)
        package=dict(publisher=record.publisher,bundle_id=record.manifest.metadata.id)
        access=dict(publisher_scopes={record.publisher})
        registry.create_bundle(**package,kind=record.manifest.kind,display_name='隔离运行联合测试',
            actor='test-author',roles={'developer'},**access)
        registry.create_version(**package,source_ref=loaded.source_ref,actor='test-author',roles={'developer'},**access)
        registry.validate(**package,version=record.manifest.metadata.version,actor='test-validator',roles={'developer'},**access)
        registry.publish(**package,version=record.manifest.metadata.version,actor='test-publisher',roles={'asset-publisher'},**access)
        snapshot=RegistrySnapshotReader(connect_factory=connect,release_policy=policy).read()
        assert len(snapshot.candidates)==1
        request=CompositionRequest.model_validate({'requested':[{'publisher':record.publisher,
            'id':record.manifest.metadata.id,'version':record.manifest.metadata.version}],
            'platformApiVersion':'1.7.0','platformRelease':'aos-platform/1.7.0','environment':'dev',
            'registrySnapshotHash':snapshot.snapshot_hash,'currentInstallationRef':None})
        payload=resolve(request,snapshot,None)
        scope=dict(org_id='org-org',project_id='dev-project')
        composition_store=PostgresCompositionStore(connect)
        lock=composition_store.create_or_get(**scope,request=request,snapshot=snapshot,payload=payload,created_by='test-author')
        store=PostgresInstallationStore(connect)
        fresh=RuntimeReleaseRevalidator(release_policy=policy)
        legacy=InstallationService(store=store,composition_store=composition_store,
            revalidator=InstallationRevalidator(release_policy=policy),planning_revalidator=fresh)
        service=RuntimeLifecycleService(installation_store=store,installation_reader=legacy,revalidator=fresh)
        if package_probe is not None:
            return package_probe(connect=connect,record=record,read_artifact=args['read_artifact'],
                platform=args['platform'],policy=policy,lock=lock,store=store,legacy=legacy,
                composition_store=composition_store,revalidator=fresh,lifecycle=service,
                scope=scope,selected=lock.payload.resolved[0],
                manifest_digest=manifest_digest,config_digest=config_digest)
        draft=store.create_draft(**scope,request=CreateInstallationRequest(compositionId=lock.composition_id,
            lockRevision=lock.revision,overlayRevision='isolated-test',displayName='签名运行准备联合测试'),requested_by='test-author')
        action=dict(**scope,installation_id=draft.installation_id,markings=[],roles=['asset-installer'],actor='test-author')
        legacy.submit(**action,request=EmptyInstallationActionRequest(),idempotency_key='signed-submit',if_match=f'"{draft.etag_version}"')
        submitted=store.get_installation(**scope,installation_id=draft.installation_id)
        legacy.approve(**{**action,'actor':'test-reviewer','roles':['asset-install-approver']},
            request=ApproveInstallationRequest(lockHash=lock.lock_hash,permissionDiffHash=lock.permission_diff_hash,
                migrationPlanHash=lock.migration_plan_hash,contributionDiffHash=lock.contribution_diff_hash),
            idempotency_key='signed-approve',if_match=f'"{submitted.etag_version}"')
        approved=store.get_installation(**scope,installation_id=draft.installation_id)
        accepted=service.request_preparation(**action,kind='runtime-apply',idempotency_key='signed-prepare',
            preparation_admission=lambda: True,
            if_match=f'"{approved.etag_version}"')
        operation=accepted.response_json['operationId']
        generation=uuid.uuid4()
        selected=lock.payload.resolved[0]
        operations=RuntimeOperationStore()
        if worker_mode:
            from aos_api.extension_runtime.preparation_worker import PreparationWorker
            permission_calls=[]
            def permission(*,verification=False,**kwargs):
                permission_calls.append(kwargs['actor'])
                if worker_mode=='verify':
                    assert kwargs['conn'].execute('SELECT current_user AS role').fetchone()['role']=='aos_runtime'
                    from aos_api.extension_runtime.current_permission import CurrentControlPermission
                    from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION,VERIFY_INSTALLATION_OPERATION
                    return CurrentControlPermission(operation=VERIFY_INSTALLATION_OPERATION if verification else APPLY_INSTALLATION_OPERATION)(**kwargs)
                return worker_mode!='permission_error' or len(permission_calls)==1
            def load_record(member):
                assert member==selected
                if worker_mode=='artifact_error':raise ValueError('artifact unavailable')
                return record
            if worker_mode=='verify':
                from aos_api.extension_runtime.schema_conditions import CurrentSchemaConditions,schema_package_id
                assert schema_setup is not None
                schema_setup(schema_package_id(selected.publisher,selected.id))
                conditions=CurrentSchemaConditions(load_record=load_record,
                    read_artifact=lambda member,path,limit:args['read_artifact'](path,limit),policy=policy)
            else:conditions=None
            configuration_authority={}
            def authorize_configuration(*a,**k):
                return configuration_authority['authorize'](*a,**k)
            from aos_api.extension_runtime.current_permission import CurrentControlPermission
            from aos_api.asset_registry.control_policy import ENABLE_RUNTIME_OPERATION
            worker=PreparationWorker(connect=connect,driver=OciDriver(context=CONTEXT),
                installation_store=store,revalidator=fresh,check_current_permission=permission,
                load_record=load_record,read_artifact=args['read_artifact'],policy=policy,platform=args['platform'],
                check_current_conditions=conditions,
                check_verification_permission=lambda **kwargs:permission(verification=True,**kwargs),
                configuration_authorize=authorize_configuration if lifecycle_probe else None,
                check_enable_permission=CurrentControlPermission(operation=ENABLE_RUNTIME_OPERATION) if lifecycle_probe else None)
            async def run_worker():
                from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer
                @contextmanager
                def consumer_connect():
                    with connect() as c:
                        c.commit()
                        c.execute('SET SESSION AUTHORIZATION aos_runtime')
                        c.commit()
                        yield c
                host=None
                if lifecycle_probe is not None:
                    from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
                    host=PreparationConsumer(connect=consumer_connect,worker=worker,
                        installation_id=draft.installation_id,**scope)
                    from preparation_case import prepare_with_ack_recovery
                    delivery=await prepare_with_ack_recovery(host,connect,operation)
                    assert str(delivery.operation_id)==str(operation) and delivery.operation_status=='succeeded'
                    job=host.job
                    assert job is not None
                else:
                    job=await worker.start(**scope,operation_id=operation,expected_revision=accepted.response_json['revision'])
                if worker_mode not in {'normal','verify'}:
                    with pytest.raises(ValueError,match='artifact unavailable' if worker_mode=='artifact_error' else 'current preparation permission'):
                        await job.prepared()
                else:
                    applied=await job.prepared()
                    assert applied.state=='applied' and applied.active_revision is None
                    assert await job.check_health() is None
                    running=await asyncio.to_thread(subprocess.check_output,
                        ['docker','--context',CONTEXT,'inspect','--format','{{.State.Running}}',job.plan.members[0].intent.identity.name],
                        text=True,timeout=10)
                    assert running.strip()=='true'
                    if worker_mode=='verify':
                        from aos_api.ecommerce_workshop_catalog import PostgresWorkshopCatalogSource
                        requested=await asyncio.to_thread(service.request_preparation,**action,kind='runtime-verify',
                            idempotency_key='signed-verify',if_match=f'"{applied.etag_version}"')
                        if lifecycle_probe is None:
                            verified=await job.verify(operation_id=requested.response_json['operationId'],
                                expected_revision=requested.response_json['revision'])
                        else:
                            from owned_control_case import deliver_with_ack_recovery
                            verifier=OwnedControlConsumer(connect=consumer_connect,job=job,kind='runtime-verify',**scope)
                            delivered=await deliver_with_ack_recovery(verifier,connect,requested.response_json['operationId'])
                            assert str(delivered.operation_id)==requested.response_json['operationId']
                            assert delivered.operation_status=='succeeded'
                            verified=await asyncio.to_thread(store.get_installation,**scope,installation_id=draft.installation_id)
                        assert verified.state=='active'
                        with connect() as conn:
                            assert conn.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
                                'enabled':False,'operation_fence':True,'observed_state':'ready'}
                        # Actual current catalog must not turn active into legacy capability.
                        assert await asyncio.to_thread(PostgresWorkshopCatalogSource(connect).read_active_bundles,
                            **scope,markings=[])==()
                        if lifecycle_probe is not None:
                            try:
                                enable=await asyncio.to_thread(lifecycle_probe,connect,store,legacy,fresh,scope,action,verified,job.plan.generation)
                                configuration_authority['authorize']=enable['authorize']
                                from enable_commit_case import exercise_enable_rejections
                                await asyncio.to_thread(exercise_enable_rejections,worker,scope,job.plan,enable)
                                enabler=OwnedControlConsumer(connect=consumer_connect,job=job,kind='enable',**scope)
                                result=await deliver_with_ack_recovery(enabler,connect,enable['operation_id'])
                                assert str(result.operation_id)==str(enable['operation_id'])
                                assert result.operation_status=='succeeded'
                                with connect() as conn:
                                    assert conn.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
                                        'enabled':True,'operation_fence':False,'observed_state':'ready'}
                                from disable_case import exercise_disable
                                await asyncio.to_thread(exercise_disable,worker,legacy,scope,action,verified,job.plan.generation)
                            finally:
                                await host.stop()
                    await job.stop()
                return job.plan
            plan=asyncio.run(run_worker())
            observed=store.get_installation(**scope,installation_id=draft.installation_id)
            assert observed.state==('active' if worker_mode=='verify' else 'applied' if worker_mode=='normal' else 'approved')
            assert (observed.active_revision is not None)==(worker_mode=='verify')
            with connect() as conn:
                assert conn.execute('SELECT status FROM extension_runtime_operation WHERE operation_id=%s',(operation,)).fetchone()=={'status':'succeeded' if worker_mode in {'normal','verify'} else 'failed'}
                assert conn.execute('SELECT observed_release,cleanup_state FROM extension_runtime_resource_lease').fetchall()==[{'observed_release':True,'cleanup_state':'released'}]
                assert conn.execute('SELECT count(*) AS n FROM extension_runtime_binding').fetchone()['n']==(1 if worker_mode=='verify' else 0)
                if worker_mode=='verify':
                    assert conn.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
                        'enabled':False,'operation_fence':True,'observed_state':'unknown'}
            assert_container_absent(CONTEXT,plan.members[0].intent)
            assert len(permission_calls)==(1 if worker_mode=='artifact_error' else 3 if worker_mode=='verify' else 2)
            return
        if planned:
            from aos_api.extension_runtime.preparation_plan import claim_preparation
            from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
            claim_args=dict(installation_store=store,revalidator=fresh,check_current_permission=lambda **kwargs:True,
                **scope,operation_id=operation,expected_revision=accepted.response_json['revision'],engine_context=CONTEXT)
            for permission in (False,None,'allowed'):
                with pytest.raises(RuntimeConflict):
                    with connect() as conn:
                        claim_preparation(conn,**{**claim_args,'check_current_permission':lambda **kwargs:permission})
            for failure in ('cas','expired','existing','context','rollback'):
                with pytest.raises((RuntimeConflict,ValueError,RuntimeError)):
                    with connect() as conn:
                        if failure=='expired':
                            conn.execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second' WHERE operation_id=%s",(operation,))
                        if failure=='existing':
                            ResourceJournal().prepare(conn,**scope,operation_id=operation,generation=generation,
                                package_id=selected.id,package_hash=selected.content_hash,engine_context=CONTEXT,
                                expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
                        altered={**claim_args}
                        if failure=='cas':altered['expected_revision']=0
                        if failure=='context':altered['engine_context']='invalid context'
                        claim_preparation(conn,**altered)
                        if failure=='rollback':raise RuntimeError('rollback accepted plan')
            with connect() as conn:
                assert conn.execute('SELECT count(*) AS n FROM extension_runtime_resource_lease').fetchone()['n']==0
                assert conn.execute('SELECT phase,revision FROM extension_runtime_operation WHERE operation_id=%s',(operation,)).fetchone()=={'phase':'accepted','revision':accepted.response_json['revision']}
                plan=claim_preparation(conn,**claim_args)
                assert len(plan.members)==1 and plan.members[0].selected==selected
            generation=plan.generation
            intent=plan.members[0].intent
            with pytest.raises(RuntimeConflict):
                with connect() as conn:
                    claim_preparation(conn,**claim_args)
        else:
            with connect() as conn:
                intent=ResourceJournal().prepare(conn,**scope,operation_id=operation,generation=generation,
                    package_id=selected.id,package_hash=selected.content_hash,engine_context=CONTEXT,
                    expires_at=datetime.now(timezone.utc)+timedelta(minutes=2))
                revision=accepted.response_json['revision']
                for phase in ('validating','preparing'):
                    revision=operations.advance(conn,**scope,operation_id=operation,expected_revision=revision,phase=phase).revision
        args.update(driver=OciDriver(context=CONTEXT),selected=selected,policy=policy)
        reached={'revoked':False,'commit':False}
        def commit_registered():
            with connect() as conn:
                revision=conn.execute('SELECT revision FROM extension_runtime_operation WHERE operation_id=%s',(operation,)).fetchone()['revision']
                registered=operations.advance(conn,**scope,operation_id=operation,expected_revision=revision,phase='registered')
                # Explicit test-host permission seam, never a production grant.
                reached['commit']=True
                applied=commit_prepared(conn,installation_store=store,revalidator=fresh,
                    check_current_permission=lambda **kwargs:True,**scope,operation_id=operation,
                    expected_revision=registered.revision,generation=generation)
                assert applied.state=='applied' and applied.active_revision is None
                return applied

        def assert_legacy_rejects(applied):
            with pytest.raises(RuntimeOperationRequiredError) as rejected:
                legacy.verify(**action,request=EmptyInstallationActionRequest(),
                    idempotency_key='legacy-must-reject',if_match=f'"{applied.etag_version}"')
            assert 'runtime bundles require the isolated installation lifecycle' in str(rejected.value)

        async def run():
            if owned:
                from aos_api.extension_runtime.preparation_owner import PreparationOwner
                from aos_api.extension_runtime.journaled_session import _settle
                async def commit():
                    result,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(commit_registered)))
                    if cancelled:raise asyncio.CancelledError
                    return result
                owner=PreparationOwner([lambda:open_signed_session(**args,connect=connect,**scope,
                    resource_id=intent.resource_id)],commit,lease_seconds=60)
                try:
                    applied=await owner.prepared()
                    # Prepared result returned, owner still keeps the actual OCI
                    # process alive without handing a session to the requester.
                    running=await asyncio.to_thread(subprocess.check_output,
                        ['docker','--context',CONTEXT,'inspect','--format','{{.State.Running}}',intent.identity.name],
                        text=True,timeout=10)
                    assert running.strip()=='true'
                    with connect() as conn:
                        assert conn.execute('SELECT observed_release FROM extension_runtime_resource_lease WHERE resource_id=%s',
                            (intent.resource_id,)).fetchone()=={'observed_release':False}
                    assert_legacy_rejects(applied)
                finally:
                    await owner.stop()
                return
            async with open_signed_session(**args,connect=connect,**scope,resource_id=intent.resource_id) as session:
                assert await session.invoke('example_read',{'value':'隔离安装联合实测'})=={'value':'隔离安装联合实测'}
                if revoke:
                    registry.revoke(**package,version=record.manifest.metadata.version,actor='test-publisher',
                        roles={'asset-publisher'},reason='隔离测试撤销发布资格',**access)
                    reached['revoked']=True
                applied=commit_registered()
                # The actual legacy service and actual fresh Registry reader must
                # reject this exact signed runtime, even after preparation.
                assert_legacy_rejects(applied)
        if revoke:
            with pytest.raises(AssetRegistryError):asyncio.run(run())
            assert reached=={'revoked':True,'commit':True}
        else:
            asyncio.run(run())
        observed=store.get_installation(**scope,installation_id=draft.installation_id)
        assert observed.state==('approved' if revoke else 'applied') and observed.active_revision is None
        if not revoke:assert observed.events[-1].evidence.type=='runtime_preparation'
        with connect() as conn:
            assert conn.execute('SELECT phase,status FROM extension_runtime_operation WHERE operation_id=%s',(operation,)).fetchone()==({'phase':'preparing','status':'running'} if revoke else {'phase':'succeeded','status':'succeeded'})
            assert conn.execute('SELECT cleanup_state,observed_release FROM extension_runtime_resource_lease WHERE resource_id=%s',(intent.resource_id,)).fetchone()=={'cleanup_state':'released','observed_release':True}
            assert conn.execute('SELECT count(*) AS n FROM extension_runtime_binding').fetchone()['n']==0
        assert_container_absent(CONTEXT,intent)
