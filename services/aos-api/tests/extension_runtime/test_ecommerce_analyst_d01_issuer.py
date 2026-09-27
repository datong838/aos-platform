"""Natural D01 issuance must not bypass the canonical AIP Owner."""
from datetime import UTC, datetime
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import (
    AgentRunRequest, CreateAgentRunRequest, VersionedAssetRef,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_task_store import _canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_analyst_d01_issuer import (
    D01SourcePacket, NaturalD01Issuer, d01_agent_run_id,
    require_current_d01_sources, require_current_d01_sources_in_transaction,
)
import aos_api.ecommerce_analyst_d01_issuer as issuer_module
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope('org-org', 'dev-project')
NOW = datetime(2026, 9, 26, 6, tzinfo=UTC)
HASH = 'a' * 64


def _resource(kind, identity, version='1'):
    return ResourceRef(resourceType=kind, resourceId=identity,
                       revision=version, authority='postgresql')


def _asset(kind, identity):
    return VersionedAssetRef(assetType=kind, assetId=identity,
                             revision=1, contentHash=HASH)


def _request(*, input_refs=None):
    return CreateAgentRunRequest(
        agentRunId=d01_agent_run_id(SCOPE, 'run-1', 'plan-1'),
        taskRunRef=_resource('TaskRun', 'run-1', '2'),
        skillBindingId='binding-d01',
        run=AgentRunRequest(
            taskRef=_resource('Task', 'task-1', '3'),
            planRef=_resource('PlanRevision', 'plan-1', '1'),
            agentInstance=_asset('AgentInstance', 'analyst-1'),
            skill=_asset('SkillTemplate', 'ecommerce.skill.D01'),
            logic=_asset('LogicRevision', 'ecommerce.logic.D01'),
            modelRoute=_asset('ModelRouteRevision', 'route-1'),
            policy=_asset('RuntimePolicyRevision', 'policy-1'),
            inputRefs=input_refs or [
                _resource('MethodRevision', 'method-1'),
                _resource('EvalContractRevision', 'eval-1'),
                _resource('MetricDefinitionRevision', 'metric-1'),
                _resource('QueryResultRevision', 'query-1'),
                _resource('EvidenceBundleRevision', 'bundle-1'),
            ],
        ),
    )


def _packet():
    return D01SourcePacket.model_validate(dict(
        methodRef=dict(resourceType='MethodRevision', resourceId='method-1',
                       revision=1, contentHash=HASH),
        evalRef=dict(resourceType='EvalContractRevision', resourceId='eval-1',
                     revision=1, contentHash=HASH),
        metricSources=[dict(
            metricRef=dict(resourceType='MetricDefinitionRevision', resourceId='metric-1',
                           revision=1, contentHash=HASH),
            resultRef=dict(resourceType='QueryResultRevision', resourceId='query-1',
                           revision=1, contentHash='sha256:' + HASH),
            sourceRequest=dict(
                bundleRef=dict(resourceType='EvidenceBundleRevision', resourceId='bundle-1',
                               revision=1, contentHash=HASH),
                grants=[dict(decisionId='decision-1', request=dict(
                    evidenceRef=dict(resourceType='Evidence', resourceId='evidence-1',
                                     revision=1, contentHash=HASH),
                    purpose='source', requestedLevel='l3', taskId='task-1'))],
            ),
            windowStart=datetime(2026, 9, 25, tzinfo=UTC), windowEnd=NOW,
        )],
        cutoffAt=NOW, markings=['internal'], maxSourceAgeSeconds=86400,
        maxBytes=10000,
    ))


def _timeline(*, run_status='running', task_status='executing', approval='approved'):
    assignee = ResourceRef(resourceType='AgentInstance', resourceId='analyst-1',
                           revision='1', authority='aip-assignee-directory')
    steps = [SimpleNamespace(step_key=key, applicability='applicable',
                             assignee_refs=[assignee],
                             input_schema_ref=_resource('Schema', key + '-input'),
                             model_dump=lambda **_kwargs: {'stepKey': key}) for key in
             ('portrait', 'diagnosis', 'solution-design')]
    # Preserve each step's key when serializing the approved plan.
    for step in steps:
        step.input_refs = [step.input_schema_ref]
        step.model_dump = lambda _step=step, **_kwargs: {
            'stepKey': _step.step_key,
            'inputRefs': [ref.model_dump(mode='json', by_alias=True)
                          for ref in _step.input_refs],
            'inputSchemaRef': _step.input_schema_ref.model_dump(mode='json', by_alias=True),
        }
    content_hash = _canonical_hash({'steps': [step.model_dump() for step in steps],
                                    'dependencies': [], 'risk': {}})
    return SimpleNamespace(
        run=SimpleNamespace(id='run-1', task_id='task-1', plan_revision_id='plan-1',
                            version=2, status=run_status),
        task=SimpleNamespace(id='task-1', version=3, status=task_status,
            selection_ref=_resource('SourceSelectionRevision','source-selection-1')),
        plan=SimpleNamespace(id='plan-1', task_id='task-1', revision=1,
                             approval_status=approval, steps=steps,
                             dependencies=[], risk={}, content_hash=content_hash),
        steps=[],
    )


def _issuer(timeline=None):
    calls = []
    tasks = SimpleNamespace(timeline=lambda scope, run_id: timeline or _timeline())
    owner = SimpleNamespace(create=lambda scope, request, **kwargs: (
        calls.append((scope, request, kwargs)) or
        (SimpleNamespace(agent_run_id=request.agent_run_id, status='queued'),
         SimpleNamespace(operation='agent_run.create',
                         idempotency_key=kwargs['idempotency_key'],
                         result_ref=_resource('AgentRun', request.agent_run_id)))))
    def origin(scope, run_id):
        calls.append(('origin', scope, run_id))
        return True
    def selection(scope, run_id, request, packet, actor, now):
        calls.append(('selection', scope, run_id))
        return True
    def sources(scope, request, packet, actor, now):
        calls.append(('sources', scope, request, packet, actor, now))
        return True
    return NaturalD01Issuer(tasks, owner, require_current_origin=origin,
                            require_current_selection=selection,
                            require_current_sources=sources), calls


def test_current_packet_uses_one_stable_owner_key_and_no_provider():
    issuer, calls = _issuer()
    run, receipt = issuer.issue(SCOPE, 'run-1', _request(), _packet(), actor='analyst-owner', occurred_at=NOW)
    assert run.status == 'queued' and receipt.operation == 'agent_run.create'
    owner_calls = [item for item in calls if len(item) == 3 and item[0] == SCOPE]
    assert len(owner_calls) == 1
    assert owner_calls[0][2]['idempotency_key'] == 'natural-d01:' + d01_agent_run_id(SCOPE, 'run-1', 'plan-1')


@pytest.mark.parametrize('run_status,task_status,approval', [
    ('paused', 'executing', 'approved'), ('succeeded', 'executing', 'approved'),
    ('running', 'paused', 'approved'), ('running', 'executing', 'pending'),
])
def test_nonrunning_or_unapproved_never_calls_owner(run_status, task_status, approval):
    issuer, calls = _issuer(_timeline(run_status=run_status,
                                      task_status=task_status, approval=approval))
    with pytest.raises(ValueError):
        issuer.issue(SCOPE, 'run-1', _request(), _packet(), actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_missing_source_inventory_never_calls_owner():
    issuer, calls = _issuer()
    with pytest.raises(ValueError):
        issuer.issue(SCOPE, 'run-1', _request(input_refs=[_resource('MethodRevision', 'method-1')]), _packet(),
                     actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


@pytest.mark.parametrize('plan_inputs', [
    [],
    [_resource('Schema', 'other-schema')],
    [_resource('Schema', 'portrait-input'), _resource('Schema', 'extra-schema')],
    [_resource('Schema', 'portrait-input'), _resource('Schema', 'portrait-input')],
])
def test_approved_plan_portrait_schema_must_match_compiler(plan_inputs):
    timeline = _timeline()
    timeline.plan.steps[0].input_refs = plan_inputs
    timeline.plan.content_hash = _canonical_hash({
        'steps': [step.model_dump() for step in timeline.plan.steps],
        'dependencies': [], 'risk': {},
    })
    issuer, calls = _issuer(timeline)
    with pytest.raises(ValueError, match='approved portrait input Schema'):
        issuer.issue(SCOPE, 'run-1', _request(), _packet(),
                     actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_formal_compiler_schema_plan_can_use_later_independently_approved_packet():
    timeline = _timeline()
    schema = _resource('SchemaRevision', 'portrait-input-schema')
    timeline.plan.steps[0].input_schema_ref = schema
    timeline.plan.steps[0].input_refs = [schema]
    timeline.plan.content_hash = _canonical_hash({
        'steps': [step.model_dump() for step in timeline.plan.steps],
        'dependencies': [], 'risk': {},
    })
    issuer, calls = _issuer(timeline)
    result = issuer.issue(SCOPE, 'run-1', _request(), _packet(),
                          actor='analyst-owner', occurred_at=NOW)
    assert result[0].agent_run_id == _request().agent_run_id
    assert any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_issuer_without_current_selection_checker_is_not_constructible():
    with pytest.raises(TypeError, match='selection'):
        NaturalD01Issuer(SimpleNamespace(timeline=lambda *_: _timeline()),
                         SimpleNamespace(create=lambda *_args, **_kwargs: None),
                         require_current_origin=lambda *_: True,
                         require_current_sources=lambda *_: True)


def test_drifted_approved_plan_hash_never_calls_owner():
    timeline = _timeline()
    timeline.plan.content_hash = '0' * 64
    issuer, calls = _issuer(timeline)
    with pytest.raises(ValueError, match='approved D01 task lineage'):
        issuer.issue(SCOPE, 'run-1', _request(), _packet(),
                     actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_missing_or_drifted_exact_packet_never_calls_owner():
    issuer, calls = _issuer()
    for packet in (None, _packet().model_copy(update={
        'method_ref': _packet().method_ref.model_copy(update={'resource_id': 'other-method'})
    })):
        with pytest.raises(ValueError):
            issuer.issue(SCOPE, 'run-1', _request(), packet,
                         actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_wrong_scope_or_untrusted_origin_never_calls_owner():
    issuer, calls = _issuer()
    with pytest.raises(ValueError):
        issuer.issue(TenantScope('dev-org', 'dev-project'), 'run-1', _request(), _packet(),
                     actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


@pytest.mark.parametrize('missing', ['origin', 'selection', 'sources'])
def test_missing_current_authority_never_calls_owner(missing):
    issuer, calls = _issuer()
    if missing == 'origin':
        issuer._origin = lambda *_args: False
    elif missing == 'selection':
        issuer._selection = lambda *_args: False
    else:
        issuer._sources = lambda *_args: False
    with pytest.raises(ValueError):
        issuer.issue(SCOPE, 'run-1', _request(), _packet(), actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_unknown_owner_result_is_not_retried_with_new_identity():
    issuer, _ = _issuer()
    calls = []
    def unknown(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError('commit outcome unknown')
    issuer._owner.create = unknown
    with pytest.raises(RuntimeError, match='unknown'):
        issuer.issue(SCOPE, 'run-1', _request(), _packet(), actor='analyst-owner', occurred_at=NOW)
    assert len(calls) == 1


def test_production_reader_requires_current_actor_markings_before_source_material(monkeypatch):
    seen = []
    class Connection:
        def execute(self, query, params=None):
            if 'current_setting' in query:
                return SimpleNamespace(fetchone=lambda: {'org_id': SCOPE.org_id,
                                                         'project_id': SCOPE.project_id})
            if 'clock_timestamp()' in query:
                return SimpleNamespace(fetchone=lambda: {'now': NOW})
            assert params[:2] == SCOPE.key
            if 'meta_membership' in query:
                rows = [{'role': 'analyst'}]
            elif 'authz_tuple' in query:
                rows = [{'object_key': 'marking:internal'}]
            else:
                raise AssertionError('unexpected authority query')
            return SimpleNamespace(fetchall=lambda: rows)
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    monkeypatch.setattr(issuer_module, 'connect_serializable', connect)
    monkeypatch.setattr(issuer_module, 'openfga_api_url', lambda: None)
    monkeypatch.setattr(issuer_module, 'read_portrait_input_packet',
                        lambda **kwargs: seen.append(kwargs))
    with pytest.raises(PermissionError):
        require_current_d01_sources(SCOPE, _request(),
            _packet().model_copy(update={'markings': ['secret']}), 'analyst-owner', NOW)
    assert seen == []
    assert require_current_d01_sources(SCOPE, _request(), _packet(),
                                       'analyst-owner', NOW) is True
    assert len(seen) == 1 and seen[0]['task_id'] == 'task-1'
    monkeypatch.setattr(issuer_module, 'openfga_api_url', lambda: 'https://remote.example')
    with pytest.raises(PermissionError, match='remote'):
        require_current_d01_sources(SCOPE, _request(), _packet(), 'analyst-owner', NOW)
    assert len(seen) == 1


def test_owner_borrowed_transaction_does_not_commit_and_rejects_wrong_scope():
    request = _request()
    calls = []
    class Connection:
        def execute(self, query, params=()):
            calls.append(query)
            if 'current_setting' in query:
                return SimpleNamespace(fetchone=lambda: {'org_id': SCOPE.org_id,
                                                         'project_id': SCOPE.project_id})
            if 'FROM aip_skill_binding' in query:
                return SimpleNamespace(fetchone=lambda: {
                    'status': 'active', 'instance_id': 'analyst-1',
                    'skill_id': 'ecommerce.skill.D01',
                    'skill_revision': 1, 'content_hash': HASH,
                    'canonical_logic_id': 'ecommerce.logic.D01',
                    'logic_revision_ref': request.run.logic.model_dump(mode='json', by_alias=True),
                    'capability_refs': [],
                })
            if 'INSERT INTO aip_agent_run' in query:
                return SimpleNamespace(fetchone=lambda: {'agent_run_id': request.agent_run_id})
            raise AssertionError(query)
        def commit(self):
            raise AssertionError('borrowed Owner transaction must not commit')
    service = AipAgentRunService()
    service._lock = lambda *_args: None
    service._receipt_row = lambda *_args: None
    service._row = lambda *_args: None
    service._require_task_run = lambda *_args: ('task-1', 'run-1')
    service._instance_row = lambda *_args: {'status': 'active', 'instance_id': 'analyst-1', 'version': 1}
    service._instance_snapshot = lambda *_args: {}
    service._instance_from_row = lambda *_args: SimpleNamespace(instance_ref=request.run.agent_instance)
    service._require_healthy_capabilities = lambda *_args: None
    service._require_logic = lambda *_args: None
    receipt = SimpleNamespace(operation='agent_run.create')
    service._insert_receipt = lambda *_args: receipt
    service._from_row = lambda *_args: SimpleNamespace(agent_run_id=request.agent_run_id)
    tx = HostTransaction(Connection())
    result = service._create_in_transaction(tx, SCOPE, request,
        idempotency_key='natural-d01:test', actor='analyst-owner', occurred_at=NOW)
    assert result[0].agent_run_id == request.agent_run_id and result[1] is receipt
    assert any('INSERT INTO aip_agent_run' in query for query in calls)
    with pytest.raises(PermissionError, match='tenant'):
        service._create_in_transaction(tx, TenantScope('dev-org', 'dev-project'), request,
            idempotency_key='natural-d01:test', actor='analyst-owner', occurred_at=NOW)


def test_source_reader_uses_borrowed_transaction_only(monkeypatch):
    seen = []
    class Connection:
        def execute(self, query, params=()):
            if 'current_setting' in query:
                return SimpleNamespace(fetchone=lambda: {'org_id': SCOPE.org_id,
                                                         'project_id': SCOPE.project_id})
            if 'clock_timestamp()' in query:
                return SimpleNamespace(fetchone=lambda: {'now': NOW})
            if 'meta_membership' in query:
                return SimpleNamespace(fetchall=lambda: [{'role': 'analyst'}])
            if 'authz_tuple' in query:
                return SimpleNamespace(fetchall=lambda: [{'object_key': 'marking:internal'}])
            raise AssertionError(query)
    monkeypatch.setattr(issuer_module, 'connect_serializable',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('new connection')))
    monkeypatch.setattr(issuer_module, 'openfga_api_url', lambda: None)
    monkeypatch.setattr(issuer_module, 'read_portrait_input_packet',
                        lambda **kwargs: seen.append(kwargs))
    tx = HostTransaction(Connection())
    assert require_current_d01_sources_in_transaction(
        tx, SCOPE, _request(), _packet(), 'analyst-owner', NOW) is True
    assert len(seen) == 1 and seen[0]['conn'] is tx
    with pytest.raises(PermissionError, match='tenant'):
        require_current_d01_sources_in_transaction(
            tx, TenantScope('dev-org', 'dev-project'), _request(),
            _packet(), 'analyst-owner', NOW)
