"""Full-schema original pending -> twelve-source snapshot -> unified resume."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import hashlib
import json

import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from test_analysis_snapshot_native_ingress_pg import (
    private_database, stored as base_stored, native_input_case as base_native_input_case,
)
from test_analysis_snapshot_native_claims_pg import native_claims_case as base_native_claims_case
from test_analysis_snapshot_native_projection_pg import native_projection_case
from test_product_event_consumer_pg import consumer_case as base_consumer_case
from test_analysis_data_preparation_pg import (
    data_case as base_data_case, prepare as prepare_data, _automatic_readers,
    formal_case, preview_case, review_identity,
    compilation_case as base_compilation_case, context_case, startup_case,
    analysis_case, host_case, control_governed, governed, service_case,
    pair, body,
)
from test_analysis_compilation_preparation_pg import (
    publications as base_publications,
    context_publication as base_context_publication,
)
from aos_api.aip_agent_registry_contracts import OperationalBindingDependencies, OperationalBindingReadiness, VersionedAssetRef
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.aip_task_store import AipTaskStore
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_analysis_snapshot_brief import AnalysisSnapshotBrief
from aos_api.ecommerce_analysis_snapshot_bundle import AnalysisSnapshotBundle
from aos_api.ecommerce_analysis_snapshot_business_evidence import AnalysisSnapshotBusinessEvidence
from aos_api.ecommerce_analysis_snapshot_fulfillment import AnalysisSnapshotFulfillment
from aos_api.ecommerce_analysis_snapshot_quality_evidence import AnalysisSnapshotQualityEvidence
from aos_api.ecommerce_analysis_snapshot_readiness import AnalysisSnapshotReadiness
from aos_api.ecommerce_analysis_snapshot_readiness_context import AnalysisSnapshotReadinessContext
from aos_api.ecommerce_analysis_snapshot_resume import _AnalysisSnapshotResumeSession
from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext
from aos_api.ecommerce_analysis_snapshot_source_evidence import AnalysisSnapshotSourceEvidence
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import DataRequirementRequestHostService, TransactionBoundConnectFactory, _HostAnalysisReceiptStore, _analysis_command_hash
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from aos_api.ec_ingress_journal import _digest
from aos_api.db import connect


pytestmark = [
    pytest.mark.parametrize('startup_case', ['defer-host'], indirect=True),
    pytest.mark.parametrize('stored', ['qualified-runtime'], indirect=True),
]


@pytest.fixture
def publications(private_database):
    """Create publication authority inside this test's full-schema database."""
    result = base_publications.__wrapped__()
    with connect() as conn:
        database = conn.info.dbname
        for runtime in result:
            assert conn.execute(
                'SELECT 1 FROM aip_skill_template_revision WHERE skill_id=%s AND revision=%s',
                (runtime.published.skill_id, runtime.published.revision),
            ).fetchone()
    class PublicationSet(list):
        pass
    wrapped = PublicationSet(result)
    wrapped.database = database
    return wrapped


@pytest.fixture
def context_publication(publications):
    return base_context_publication.__wrapped__(publications)


@pytest.fixture
def stored(private_database, pair, request, publications):
    """Open the serializable analysis transaction after publications commit."""
    yield from base_stored.__wrapped__(private_database, pair, request)


@pytest.fixture
def compilation_case(context_case, publications, monkeypatch):
    assert context_case[0].info.dbname == publications.database
    return base_compilation_case.__wrapped__(context_case, publications, monkeypatch)


@pytest.fixture
def native_claims_case(host_case, formal_case, publications):
    """Bind the source event origin to one member before the group is claimed."""
    assert formal_case[0] is host_case[0]
    identity = host_case[0].execute('SELECT session_user AS name').fetchone()['name']
    publications.runtime_identity = identity
    host_case[0].execute('RESET ROLE')
    host_case[0].execute('RESET SESSION AUTHORIZATION')
    conn, owner, args, source_id, revision = base_native_claims_case.__wrapped__(host_case)
    assert conn.info.dbname == publications.database
    old = args['bindings'][0][1]
    conn.execute("UPDATE meta_schedule_run SET id='fixture-original' WHERE id=%s", (old,))
    bindings = ((args['bindings'][0][0], 'fixture-original'),) + args['bindings'][1:]
    return conn, owner, args | {'bindings': bindings}, source_id, revision


@pytest.fixture
def consumer_case(host_case, publications, monkeypatch):
    """Restore the runtime identity after the committed native source setup."""
    conn = host_case[0]
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    result = base_consumer_case.__wrapped__(host_case,monkeypatch)
    row = result[1].reader.run_candidates(execute=lambda rows: rows[0])
    publications.event_cutoff = row['created_at'].replace(microsecond=0)
    return result


@pytest.fixture
def native_input_case(native_claims_case, private_database, publications, monkeypatch):
    """Return the source snapshot observed at the original product-event cutoff."""
    generator = base_native_input_case.__wrapped__(native_claims_case, private_database, monkeypatch)
    value = next(generator)
    import aos_api.pipeline_controlled_snapshot_group_ingress as ingress_module
    original = ingress_module.read_selected_snapshot_group
    def aligned_source(**kwargs):
        result = original(**kwargs)
        cutoff = publications.event_cutoff
        return type(result)(result.rows_by_table, result.source_configuration_ref, cutoff, cutoff)
    monkeypatch.setattr(ingress_module, 'read_selected_snapshot_group', aligned_source)
    try:
        yield value
    finally:
        generator.close()


@pytest.fixture
def data_case(formal_case, publications):
    """Restore the analysis transaction after native input commits its source data."""
    conn = formal_case[0]
    conn.autocommit = False
    conn.execute('RESET ROLE')
    conn.execute('RESET SESSION AUTHORIZATION')
    conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(publications.runtime_identity)))
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    return base_data_case.__wrapped__(formal_case)


def policy_ref(base, kind, path, raw):
    return base.model_copy(update=dict(resource_type=kind, resource_id=path,
        content_hash='sha256:' + hashlib.sha256(raw).hexdigest()))


@pytest.fixture
def chain_case(native_projection_case, data_case, monkeypatch, request):
    objects, conn, args, state = native_projection_case
    data_conn, analysis, claimed, _ = data_case
    assert data_conn is conn and analysis.scope == args['scope']

    first_ref, first_run = args['bindings'][0]
    assert first_run == analysis.source.reader._journal._run_id == 'fixture-original'
    analysis.source.reader._journal = ControlledIngressJournal(
        claims=objects._claims, scope=args['scope'], run_id=first_run,
        control_ref=first_ref, actor=args['actor'], completed_read=True)

    relation_doc = json.loads(state['policy_raw'])
    relation_doc.update(schemaVersion='aos.snapshot-relationships/v2', retirement=dict(
        mode='present-rows-only', requireCompleteReferences=True,
        rejectNewerThanObservation=True, allowMissingRowDeletion=False))
    relation_raw = json.dumps(relation_doc).encode()
    state['policy_raw'] = relation_raw
    relation_ref = args['policy_ref'].model_copy(update={
        'resource_id': 'content/policies/snapshot-relationships.v1.json',
        'content_hash': 'sha256:' + hashlib.sha256(relation_raw).hexdigest()})
    args = args | {'policy_ref': relation_ref}
    natural = getattr(request, 'param', None) == 'natural-worker'
    if natural:
        from contextlib import contextmanager
        from aos_api.ecommerce_product_event_worker import ProductEventConsumptionWorker
        from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
        from aos_api.pipeline_control_service import PipelineControlServiceFactory
        import aos_api.ecommerce_product_event_worker as event_worker_module

        original_installed_reader = analysis.invoker.read_current_in_transaction
        missing_owner = not hasattr(analysis.source.reader, '_owner')
        original_source_owner = getattr(analysis.source.reader, '_owner', None)
        _automatic_readers(data_case, monkeypatch)
        factory = object.__new__(PipelineControlServiceFactory)
        directory = LivePreparedJobDirectory()
        event_worker = ProductEventConsumptionWorker(factory, directory)
        monkeypatch.setattr(event_worker, '_origin', lambda scope, current: {
            'actor': analysis.source.actor, 'runId': first_run,
            'controlRef': first_ref.model_dump(mode='json', by_alias=True),
        })
        monkeypatch.setattr(event_worker, '_markings', lambda scope, actor: ('internal',))
        monkeypatch.setattr(PipelineControlServiceFactory, 'build_event_analysis',
            lambda self, scope, **kwargs: analysis)
        @contextmanager
        def store():
            yield objects._store
        async def dispatch(scope, **kwargs):
            assert kwargs['target'].trigger_source == 'event'
            await kwargs['handler'](claimed)
            return True
        monkeypatch.setattr(event_worker_module, '_authoritative_store', store)
        monkeypatch.setattr(event_worker_module, 'dispatch_one_occurrence_async', dispatch)
        assert asyncio.run(event_worker._dispatch((analysis.scope,
            analysis.invoker.installation_id, analysis.invoker.generation)))
        analysis.invoker.read_current_in_transaction = original_installed_reader
        if missing_owner:
            del analysis.source.reader._owner
        else:
            analysis.source.reader._owner = original_source_owner
        row = conn.execute('''SELECT h.requirement_id,h.current_revision,r.content_hash
            FROM data_requirement_head h JOIN data_requirement_revision r
              ON r.org_id=h.org_id AND r.project_id=h.project_id
             AND r.requirement_id=h.requirement_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s''', analysis.scope.key).fetchone()
        assert row is not None
        requested = {'requirementRef': dict(resourceType='DataRequirementRevision',
            resourceId=row['requirement_id'], revision=row['current_revision'],
            contentHash='sha256:' + row['content_hash'])}
    else:
        requested = prepare_data(data_case)
    tx = HostTransaction(conn)
    root = _HostAnalysisReceiptStore(tx, analysis.scope).read(claimed.target_idempotency_key)
    now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    AutomationOccurrenceStore(TransactionBoundConnectFactory(tx,analysis.scope)).record_target_receipt(
        analysis.scope,occurrence_id=claimed.occurrence_id,owner=claimed.claim_owner,
        receipt_ref=root['receiptRef'],occurred_at=now.replace(microsecond=0))
    _, runs, receipts, binder, requirements, _ = DataRequirementRequestHostService._components(tx, analysis.scope)
    requirement = requirements.get_exact(analysis.scope, InvestigationExactRef.model_validate(requested['requirementRef']))
    run = runs.get_verified(analysis.scope, root['runRef']['resourceId'])
    runtime = binder.bind_receipt(analysis.scope, receipts.get_for_run(
        analysis.scope, InvestigationExactRef.model_validate(root['runRef'])), run)
    assert runtime.task_run_status.value == 'paused' and runtime.checkpoint_ref is not None

    # The accepted analysis and its pending DataRequirement are one committed
    # unit.  Source workers complete afterward on their own connections, so the
    # serializable analysis session must begin a fresh snapshot before reading
    # those completions.
    conn.commit()
    completion = PipelineSnapshotGroupCompletion(
        claims=objects._claims, store=objects._store,
        connect=objects._single._ingress._connect, eng=objects._single._eng)
    completed = completion.complete(**args)
    assert completed['status'] == 'succeeded' and completed['replayed'] is False

    relation = compile_relationship_policy(relation_doc)
    kinds = [item.object_type for item in CANONICAL_QYH_SOURCES]
    quality_doc = dict(schemaVersion='aos.snapshot-relationship-quality/v1',
        relationshipPolicyHash=relation.content_hash,
        purposes=[dict(purposeCode='initial_store_analysis',
            rules=[dict(linkType='Shop.hasWeapp',requirement='required')])])
    cohort_doc = dict(schemaVersion='aos.snapshot-business-cohort/v1',
        relationshipPolicyHash=relation.content_hash,purposeCode='initial_store_analysis',
        windowBoundary='start-inclusive-end-exclusive',
        rules=[dict(objectType=kind,basis='snapshot',statusFilter=None) for kind in kinds])
    quality_raw, cohort_raw = json.dumps(quality_doc).encode(), json.dumps(cohort_doc).encode()
    quality_ref = policy_ref(relation_ref,'SnapshotRelationshipQualityPolicy','content/policies/relationship-quality.v1.json',quality_raw)
    cohort_ref = policy_ref(relation_ref,'SnapshotBusinessCohortPolicy','content/policies/business-cohort.v1.json',cohort_raw)
    field_doc = dict(schemaVersion='aos.snapshot-fact-quality/v1',
        cohortPolicyHash=compile_business_cohort_policy(cohort_doc,relationship_policy=relation).content_hash,
        relationshipQualityPolicyHash=compile_relationship_quality_policy(quality_doc,relationship_policy=relation).content_hash,
        purposeCode='initial_store_analysis',
        facts=[dict(objectType=kind,fields=[dict(property='name',kind='nonblank-string')]) for kind in kinds])
    field_raw = json.dumps(field_doc).encode()
    field_ref = policy_ref(relation_ref,'SnapshotFactQualityPolicy','content/policies/fact-quality.v1.json',field_raw)
    business_doc = dict(schemaVersion='aos.snapshot-business-facts/v1',
        fieldPolicyHash='sha256:'+_digest(field_doc),purposeCode='initial_store_analysis',
        facts=[dict(objectType=kind,mode='records',fields=['name']) for kind in kinds])
    business_raw = json.dumps(business_doc).encode()
    business_policy_ref = policy_ref(relation_ref,'SnapshotBusinessFactPolicy','content/policies/business-facts.v1.json',business_raw)
    readiness_doc = dict(schemaVersion='aos.snapshot-readiness-policy/v1',
        fieldPolicyHash='sha256:'+_digest(field_doc),
        relationshipQualityPolicyHash=field_doc['relationshipQualityPolicyHash'],purposeCode='initial_store_analysis',
        freshnessMode='requirement-oldest-observation',reconciliationMode='current-original-base-and-derived',
        queryBindingId='query-twelve',sources=[dict(pipelineId=item.pipeline_id,objectType=item.object_type)
            for item in CANONICAL_QYH_SOURCES])
    readiness_raw = json.dumps(readiness_doc).encode()
    readiness_policy_ref = policy_ref(relation_ref,'SnapshotReadinessPolicy','content/policies/snapshot-readiness.v1.json',readiness_raw)
    documents = {ref.resource_id:raw for ref,raw in ((relation_ref,relation_raw),(quality_ref,quality_raw),
        (cohort_ref,cohort_raw),(field_ref,field_raw),(business_policy_ref,business_raw),
        (readiness_policy_ref,readiness_raw))}
    objects._claims._controls._selections._artifacts.read_artifact = lambda selected,path,limit: documents[path]
    state['policy_documents'] = documents

    cap = VersionedAssetRef(asset_type='CapabilityRevision',asset_id='strategy.plan',revision=1,content_hash='1'*64)
    deps = OperationalBindingDependencies(); digest = AipBindingReadinessService.snapshot_hash(cap,deps)
    with connect() as admin:
        assert admin.info.dbname == conn.info.dbname
        admin.execute('''INSERT INTO aip_capability_binding(org_id,project_id,binding_id,capability_ref,secret_ref,health,
            network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,status,version,observed_at,
            operational_readiness,readiness_reasons,dependency_snapshot_hash,last_evaluated_at,readiness_expires_at,created_at)
            VALUES(%s,%s,'query-twelve',%s,'vault://named-fixture','healthy','network','quota',1000,1,'active',2,%s,
            'available','[]',%s,%s,%s,%s)''',(*analysis.scope.key,Jsonb(cap.model_dump(mode='json',by_alias=True)),
            now,digest,now,now+timedelta(minutes=15),now-timedelta(seconds=1)))
    import aos_api.ecommerce_analysis_query_binding as binding
    monkeypatch.setattr(binding.PostgresBindingDependencyAuthority,'capability',lambda self,ref:
        dict(lifecycle='published',content_hash=ref.content_hash,required_data_refs=[],required_tool_refs=[]))
    monkeypatch.setattr(binding.AipBindingReadinessService,'evaluate_capability',lambda self,scope,ref,dependencies,*,evaluated_at:
        OperationalBindingReadiness(readiness='available',reasons=[],dependencies=dependencies,
            dependency_snapshot_hash=self.snapshot_hash(ref,dependencies),evaluated_at=evaluated_at,
            expires_at=evaluated_at+timedelta(minutes=15)))
    monkeypatch.setattr(binding.ContentGenerateHostService,'_binding_dependency_authority',lambda *a,**k:None)

    state['completion'] = completion
    if natural:
        return conn,state,analysis,None,root,requirement

    source = AnalysisSnapshotSourceEvidence(analysis,store=objects._store)
    source_call = dict(receipt_ref=root['receiptRef'],policy_ref=relation_ref,quality_ref=quality_ref,
        cohort_ref=cohort_ref,field_ref=field_ref)
    source_ref = source.capture_current(conn,**source_call)
    quality = AnalysisSnapshotQualityEvidence(source)
    query_ref = quality.query.execute_current(conn,evidence_ref=source_ref)
    quality_evidence_ref = quality.put_current(conn,evidence_ref=source_ref,query_ref=query_ref)
    business = AnalysisSnapshotBusinessEvidence(source)
    business_ref = business.put_current(conn,evidence_ref=source_ref,query_ref=query_ref,
        quality_ref=quality_evidence_ref,policy_ref=business_policy_ref)

    readiness = AnalysisSnapshotReadiness(AnalysisSnapshotReadinessContext(business))
    ready = readiness.put_current(conn,business_ref=business_ref,policy_ref=readiness_policy_ref)
    brief = AnalysisSnapshotBrief(business); bundle = AnalysisSnapshotBundle(brief)
    bundle_ref = bundle.prepare_current(conn,business_ref=business_ref)
    fulfillment = AnalysisSnapshotFulfillment(bundle,readiness)
    fulfilled = fulfillment.put_current(conn,business_ref=business_ref,bundle_ref=bundle_ref,
        readiness_ref=ready.receipt_ref,policy_ref=readiness_policy_ref)

    command = dict(operation='runtime.analysis.resume_snapshot',
        idempotencyKey='snapshot-chain-'+claimed.target_idempotency_key,
        occurrenceRef=root['occurrenceRef'],caseRef=root['caseRef'],profileRef=root['profileRef'],
        cutoffAt=root['cutoffAt'],priorReceiptRef=root['receiptRef'],priorPlanRef=root['planRef'],
        requirementRef=fulfilled.requirement_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        fulfillmentRef=fulfillment.reference(fulfilled).model_dump(mode='json',by_alias=True,exclude_none=True),
        checkpointRef=requirement.checkpoint_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        sourceReadinessRef=fulfilled.source_readiness_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        evidenceRefs=[bundle_ref.model_dump(mode='json',by_alias=True,exclude_none=True)],
        observedAt=fulfilled.fulfilled_at.isoformat(),businessEvidenceRef=business_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        readinessPolicyRef=readiness_policy_ref.model_dump(mode='json',by_alias=True,exclude_none=True))
    command['requestHash'] = _analysis_command_hash(command)
    context = AnalysisSnapshotResumeContext(fulfillment,AnalysisContinuationOrigin(AnalysisContinuationContext(analysis)))
    return conn,state,analysis,_AnalysisSnapshotResumeSession(context,conn,command),root,requirement


def test_original_pending_twelve_sources_and_unified_resume_are_one_lineage(chain_case):
    conn,state,analysis,session,root,requirement = chain_case
    tx=HostTransaction(conn); _,runs,_,_,_,_=DataRequirementRequestHostService._components(tx,analysis.scope)
    tasks=AipTaskStore(TransactionBoundConnectFactory(tx,analysis.scope))
    before=runs.get_verified(analysis.scope,root['runRef']['resourceId']); task_before=tasks.get_run(analysis.scope,root['taskRunRef']['resourceId'])
    assert before.state.lifecycle.value=='WAITING_DATA' and task_before.status.value=='paused'
    receipt=session.resume()
    assert receipt['phase']=='RUNNING' and receipt['requirementRef']==session.command['requirementRef']
    assert receipt['fulfillmentRef']==session.command['fulfillmentRef'] and receipt['sourceReadinessRef']==session.command['sourceReadinessRef']
    assert receipt['evidenceRefs']==session.command['evidenceRefs']
    assert tasks.get_run(analysis.scope,root['taskRunRef']['resourceId']).version==task_before.version+1
    after=runs.get_verified(analysis.scope,root['runRef']['resourceId'])
    assert after.state.version==before.state.version+1 and after.state.lifecycle.value=='PREPARING'
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='succeeded'").fetchone()['n']==12
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==13 and state['calls']==1
    recreated=_AnalysisSnapshotResumeSession(session.context,conn,deepcopy(session.command))
    assert recreated.resume()==receipt and runs.get_verified(analysis.scope,root['runRef']['resourceId'])==after


def test_revoked_business_evidence_keeps_original_run_waiting(chain_case):
    conn,_,analysis,session,root,_ = chain_case
    tx=HostTransaction(conn); _,runs,_,_,_,_=DataRequirementRequestHostService._components(tx,analysis.scope)
    tasks=AipTaskStore(TransactionBoundConnectFactory(tx,analysis.scope))
    before=runs.get_verified(analysis.scope,root['runRef']['resourceId'])
    task_before=tasks.get_run(analysis.scope,root['taskRunRef']['resourceId'])
    evidence=InvestigationExactRef.model_validate(session.command['businessEvidenceRef'])
    conn.execute('''INSERT INTO aip_evidence_revoke_event
        (org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor)
        VALUES(%s,%s,'snapshot-chain-revoke',%s,1,%s,'current business evidence revoked','fixture')''',
        (*analysis.scope.key,evidence.resource_id,evidence.content_hash[7:]))
    with pytest.raises(ValueError,match='revoked'):
        session.resume()
    assert runs.get_verified(analysis.scope,root['runRef']['resourceId']) == before
    assert tasks.get_run(analysis.scope,root['taskRunRef']['resourceId']) == task_before
    assert before.state.lifecycle.value == 'WAITING_DATA' and task_before.status.value == 'paused'
    assert conn.execute('''SELECT count(*) AS n FROM ecommerce_growth_runtime_command_receipt
        WHERE org_id=%s AND project_id=%s AND idempotency_key=%s''',
        (*analysis.scope.key,session.command['idempotencyKey'])).fetchone()['n'] == 0
