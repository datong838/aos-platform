"""Existing Registry migrations and Installation Store on the dedicated test DB."""
import importlib.util
import os
from pathlib import Path
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from sqlalchemy import create_engine,text
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest

pytestmark=pytest.mark.skipif(os.getenv("AOS_EXTENSION_PG_TEST")!="1",reason="dedicated DB opt-in")


@pytest.mark.parametrize('commit_case', ['valid', 'rollback', 'wrong_type', 'invalid', 'missing', 'released', 'unregistered', 'expired', 'denied', 'revoked', 'wrong_hash', 'other_generation', 'claims_changed', 'etag_changed', 'late_policy', 'unsupported_runtime', 'extra_resource', 'operation_cas', 'non_boolean_permission', 'late_resource', 'signed', 'signed_revoked', 'signed_owned'])
def test_existing_installation_schema_accepts_subordinate_operation(commit_case,tmp_path):
    if commit_case.startswith('signed') and os.getenv('AOS_EXTENSION_OCI_TEST')!='1':
        pytest.skip('dedicated OCI opt-in required')
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.composition_contracts import CreateInstallationRequest
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
    root=Path(__file__).resolve().parents[2]
    helper_path=root/"tests/asset_registry/test_m2_core_integration.py"
    spec=importlib.util.spec_from_file_location("ar1_baseline_helpers",helper_path)
    helper=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helper;spec.loader.exec_module(helper)
    schema="ar1c_full_"+uuid.uuid4().hex
    @contextmanager
    def scoped_connect():
        with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",row_factory=dict_row) as c:
            c.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield c
    with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as admin:
        created_runtime=admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
        if created_runtime:
            admin.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            engine=create_engine("postgresql+psycopg://postgres@127.0.0.1:18432/postgres")
            try:
                with engine.begin() as c:
                    c.execute(text(f'SET search_path TO "{schema}"'))
                    with Operations.context(MigrationContext.configure(c)):
                        for i,path in enumerate((*helper.MIGRATION_PATHS,root/"alembic/versions/ar1_001_extension_runtime_authority.py")):
                            helper._load_migration(path,i).upgrade()
            finally:
                engine.dispose()
            # Reproduce TI6 adoption for the actual asset-control tables present
            # in this baseline; new extension grants must come from ar1_001 only.
            admin.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
            for table in ("bundle_composition","bundle_composition_lock","bundle_installation",
                          "bundle_installation_command","bundle_installation_decision",
                          "bundle_installation_event","bundle_installation_revision"):
                qualified=sql.Identifier(schema,table)
                admin.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE ON {} TO aos_runtime").format(qualified))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO aos_runtime USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier("tenant_scope_"+table+"_ti6"),qualified))
                admin.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(qualified))
                admin.execute(sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(qualified))
            if commit_case.startswith('signed'):
                # Global immutable template facts are read by the scoped
                # installation control role; grant only these four reads in
                # this temporary schema, not business tables or registry writes.
                for table in ('asset_bundle','asset_bundle_version','asset_bundle_artifact','asset_bundle_evidence'):
                    admin.execute(sql.SQL('GRANT SELECT ON {} TO aos_runtime').format(sql.Identifier(schema,table)))
                from signed_installation_case import run_signed_installation
                run_signed_installation(scoped_connect,helper,tmp_path,revoke=commit_case=='signed_revoked',owned=commit_case=='signed_owned')
                return
            composition_store,_,_,_,lock=helper._persist_lock(scoped_connect)
            draft=PostgresInstallationStore(scoped_connect).create_draft(org_id="org-a",project_id="project-a",
                request=CreateInstallationRequest.model_validate({"compositionId":lock.composition_id,"lockRevision":1,
                  "overlayRevision":"test-overlay","displayName":"隔离安装测试"}),requested_by="test-actor")
            with scoped_connect() as c:
                result=RuntimeOperationStore().accept(c,org_id="org-a",project_id="project-a",installation_id=draft.installation_id,
                    kind="runtime-apply",idempotency_key="schema-integration",requested_by="test-actor",
                    expected_installation_etag=draft.etag_version,deadline=datetime.now(timezone.utc)+timedelta(minutes=1))
                assert result.status=="accepted"
            observed=PostgresInstallationStore(scoped_connect).get_installation(org_id="org-a",project_id="project-a",installation_id=draft.installation_id)
            assert observed.state=="draft" and observed.current_revision==draft.current_revision
            # Real store/receipt transaction integration; release validation is an
            # explicit test seam here, not evidence of a signed runtime deployment.
            from unittest.mock import MagicMock
            from aos_api.asset_registry.composition_contracts import ApproveInstallationRequest
            from aos_api.asset_registry.installation_service import InstallationService
            from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
            from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
            store=PostgresInstallationStore(scoped_connect)
            second=store.create_draft(org_id="org-a",project_id="project-a",
                request=CreateInstallationRequest.model_validate({"compositionId":lock.composition_id,"lockRevision":1,
                  "overlayRevision":"test-overlay","displayName":"独立运行接纳测试"}),requested_by="test-actor")
            with scoped_connect() as c:
                locked=store.lock_for_transition_in_transaction(c,org_id="org-a",project_id="project-a",
                    installation_id=second.installation_id,expected_etag_version=second.etag_version)
                submitted=store.append_submit_in_transaction(c,locked=locked,actor="test-actor")
            with scoped_connect() as c:
                locked=store.lock_for_transition_in_transaction(c,org_id="org-a",project_id="project-a",
                    installation_id=second.installation_id,expected_etag_version=submitted.etag_version)
                approved=store.append_approval_in_transaction(c,locked=locked,actor="test-reviewer",
                    request=ApproveInstallationRequest.model_validate({"lockHash":lock.lock_hash,
                        "permissionDiffHash":lock.permission_diff_hash,"migrationPlanHash":lock.migration_plan_hash,
                        "contributionDiffHash":lock.contribution_diff_hash}))
            validator=MagicMock()
            validator.revalidate_in_transaction.return_value=SimpleNamespace(
                checked_at=datetime.now(timezone.utc),runtime_members=("test-only-runtime",))
            reader=InstallationService(store=store,composition_store=composition_store,revalidator=validator)
            service=RuntimeLifecycleService(installation_store=store,installation_reader=reader,revalidator=validator)
            args=dict(installation_id=second.installation_id,kind="runtime-apply",org_id="org-a",project_id="project-a",
                actor="test-actor",roles=["asset-installer"],markings=lock.payload.permission_diff.target.markings,
                idempotency_key="runtime-receipt",if_match=f'"{approved.etag_version}"')
            accepted=service.request_preparation(**args)
            replay=service.request_preparation(**args)
            assert accepted.status_code==202 and replay.replayed and replay.response_json==accepted.response_json
            validator.revalidate_in_transaction.assert_called_once()
            with pytest.raises(RuntimeConflict):
                service.request_preparation(**{**args,"idempotency_key":"another-key"})
            assert store.get_installation(org_id="org-a",project_id="project-a",installation_id=second.installation_id).state=="approved"
            # Internal transaction compatibility fixture, not signed OCI or
            # production policy evidence: those are independently tested.
            from aos_api.extension_runtime.preparation_commit import commit_prepared
            from aos_api.extension_runtime.reconciler import ResourceJournal
            from aos_api.extension_runtime.contracts import RegistrationDescription
            from aos_api.asset_registry.composition_contracts import InstallationEventEvidence
            from aos_api.asset_registry.installation_store import InstallationStateConflictError
            operation_id=accepted.response_json['operationId']
            generation=uuid.uuid4()
            selected=lock.payload.resolved[0]
            validator.revalidate_in_transaction.return_value=SimpleNamespace(
                checked_at=datetime.now(timezone.utc),runtime_members=(selected.id,))
            scope=dict(org_id='org-a',project_id='project-a')
            journal=ResourceJournal()
            with scoped_connect() as c:
                intent=journal.prepare(c,**scope,operation_id=operation_id,generation=generation,
                    package_id=selected.id,package_hash=selected.content_hash,engine_context='colima-aos-extension',
                    expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
                journal.claim_create(c,**scope,resource_id=intent.resource_id)
                journal.record_created(c,**scope,intent=intent,container_id='a'*64)
                if commit_case=='extra_resource':
                    journal.prepare(c,**scope,operation_id=operation_id,generation=uuid.uuid4(),
                        package_id=selected.id,package_hash=selected.content_hash,engine_context='colima-aos-extension',
                        expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
                if commit_case!='unregistered':
                    journal.record_registered(c,**scope,resource_id=intent.resource_id,
                        declared=RegistrationDescription(contributions=[]))
                current=c.execute('SELECT revision FROM extension_runtime_operation WHERE operation_id=%s',(operation_id,)).fetchone()['revision']
                for phase in ('validating','preparing','registered'):
                    current=RuntimeOperationStore().advance(c,**scope,operation_id=operation_id,
                        expected_revision=current,phase=phase).revision
                from aos_api.extension_runtime.lifecycle_store import _digest
                validator.revalidate_in_transaction.return_value.backend_claims=((selected.id,selected.content_hash,_digest({'contributions':[]})),)
                if commit_case=='released':
                    journal.record_cleanup(c,**scope,intent=intent,removed=True)
                    current+=1
                if commit_case=='expired':
                    c.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()-interval '1 second'")
                if commit_case=='wrong_hash':
                    c.execute("UPDATE extension_runtime_resource_lease SET package_hash=%s",('sha256:'+'0'*64,))
                if commit_case=='etag_changed':
                    from aos_api.asset_registry.installation_evidence import build_event_evidence
                    locked=store.lock_for_transition_in_transaction(c,**scope,installation_id=second.installation_id,
                        expected_etag_version=approved.etag_version)
                    evidence=build_event_evidence(evidence_type='dry_apply',installation_id=second.installation_id,
                        from_revision=approved.current_revision,to_revision=approved.current_revision+1,
                        lock_hash=lock.lock_hash,permission_diff_hash=lock.permission_diff_hash,
                        migration_plan_hash=lock.migration_plan_hash,contribution_diff_hash=lock.contribution_diff_hash,
                        decision_id=approved.decision.decision_id,observed_at=store.read_control_clock_in_transaction(c))
                    store.append_apply_in_transaction(c,locked=locked,actor='test-actor',evidence=evidence)
            if commit_case in ('wrong_type','invalid'):
                with pytest.raises(InstallationStateConflictError):
                    with scoped_connect() as c:
                        locked=store.lock_for_transition_in_transaction(c,**scope,installation_id=second.installation_id,
                            expected_etag_version=approved.etag_version)
                        evidence=InstallationEventEvidence(type='runtime_preparation',evidenceRef='runtime/test',
                            evidenceHash='sha256:'+'a'*64,status='invalid' if commit_case=='invalid' else 'valid',
                            observedAt=datetime.now(timezone.utc))
                        method=store.append_apply_in_transaction if commit_case=='wrong_type' else store.append_runtime_preparation_in_transaction
                        method(c,locked=locked,actor='test-actor',evidence=evidence)
            else:
                if commit_case=='missing':
                    validator.revalidate_in_transaction.return_value.runtime_members=(selected.id,'missing')
                if commit_case=='revoked':
                    validator.revalidate_in_transaction.side_effect=RuntimeConflict('release revoked')
                if commit_case=='claims_changed':
                    validator.revalidate_in_transaction.return_value.backend_claims=((selected.id,selected.content_hash,'sha256:'+'f'*64),)
                if commit_case=='unsupported_runtime':
                    validator.revalidate_in_transaction.return_value.backend_claims=()
                if commit_case=='late_policy':
                    def late_policy(conn,**kwargs):
                        conn.execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second' WHERE operation_id=%s",(operation_id,))
                        return validator.revalidate_in_transaction.return_value
                    validator.revalidate_in_transaction.side_effect=late_policy
                def execute_commit():
                    with scoped_connect() as c:
                        c.execute('SELECT 1')
                        transaction=c
                        if commit_case=='late_resource':
                            c.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()+interval '150 milliseconds'")
                            class DelayedObservation:
                                def __getattr__(self,name):return getattr(c,name)
                                def execute(self,query,params=None):
                                    if isinstance(query,str) and 'SELECT payload,payload_hash' in query:
                                        c.execute('SELECT pg_sleep(0.2)')
                                    return c.execute(query,params)
                            transaction=DelayedObservation()
                        result=commit_prepared(transaction,installation_store=store,revalidator=validator,
                            check_current_permission=lambda **kwargs: 1 if commit_case=='non_boolean_permission' else commit_case!='denied',
                            **scope,operation_id=operation_id,expected_revision=current-1 if commit_case=='operation_cas' else current,
                            generation=uuid.uuid4() if commit_case=='other_generation' else generation)
                        if commit_case=='rollback':raise RuntimeConflict('injected post-append failure')
                        return result
                if commit_case=='valid':
                    result=execute_commit()
                    assert result.state=='applied' and result.active_revision is None
                    assert result.events[-1].evidence.type=='runtime_preparation'
                    assert execute_commit()==result  # Replay must not append a second event.
                else:
                    with pytest.raises(RuntimeConflict):execute_commit()
            observed=store.get_installation(**scope,installation_id=second.installation_id)
            assert observed.state==('applied' if commit_case in ('valid','etag_changed') else 'approved')
            assert observed.active_revision is None
            with scoped_connect() as c:
                row=c.execute('SELECT phase,revision FROM extension_runtime_operation WHERE operation_id=%s',(operation_id,)).fetchone()
                assert row==dict(phase='succeeded' if commit_case=='valid' else 'registered',revision=current+3 if commit_case=='valid' else current)
                assert c.execute('SELECT count(*) AS count FROM extension_runtime_binding').fetchone()['count']==0
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            if created_runtime:
                admin.execute("DROP ROLE aos_runtime")
