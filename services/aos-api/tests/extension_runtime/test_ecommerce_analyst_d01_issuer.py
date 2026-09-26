"""Natural D01 issuance must not bypass the canonical AIP Owner."""
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import (
    AgentRunRequest, CreateAgentRunRequest, VersionedAssetRef,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.ecommerce_analyst_d01_issuer import NaturalD01Issuer, d01_agent_run_id
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


def _timeline(*, run_status='running', task_status='executing', approval='approved'):
    assignee = ResourceRef(resourceType='AgentInstance', resourceId='analyst-1',
                           revision='1', authority='aip-assignee-directory')
    steps = [SimpleNamespace(step_key=key, applicability='applicable',
                             assignee_refs=[assignee]) for key in
             ('portrait', 'diagnosis', 'solution-design')]
    return SimpleNamespace(
        run=SimpleNamespace(id='run-1', task_id='task-1', plan_revision_id='plan-1',
                            version=2, status=run_status),
        task=SimpleNamespace(id='task-1', version=3, status=task_status),
        plan=SimpleNamespace(id='plan-1', task_id='task-1', revision=1,
                             approval_status=approval, steps=steps),
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
    def sources(scope, request, actor, now):
        calls.append(('sources', scope, request, actor, now))
        return True
    return NaturalD01Issuer(tasks, owner, require_current_origin=origin,
                            require_current_sources=sources), calls


def test_current_packet_uses_one_stable_owner_key_and_no_provider():
    issuer, calls = _issuer()
    run, receipt = issuer.issue(SCOPE, 'run-1', _request(), actor='analyst-owner', occurred_at=NOW)
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
        issuer.issue(SCOPE, 'run-1', _request(), actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_missing_source_inventory_never_calls_owner():
    issuer, calls = _issuer()
    with pytest.raises(ValueError):
        issuer.issue(SCOPE, 'run-1', _request(input_refs=[_resource('MethodRevision', 'method-1')]),
                     actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_wrong_scope_or_untrusted_origin_never_calls_owner():
    issuer, calls = _issuer()
    with pytest.raises(ValueError):
        issuer.issue(TenantScope('dev-org', 'dev-project'), 'run-1', _request(),
                     actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


@pytest.mark.parametrize('missing', ['origin', 'sources'])
def test_missing_current_authority_never_calls_owner(missing):
    issuer, calls = _issuer()
    if missing == 'origin':
        issuer._origin = lambda *_args: False
    else:
        issuer._sources = lambda *_args: False
    with pytest.raises(ValueError):
        issuer.issue(SCOPE, 'run-1', _request(), actor='analyst-owner', occurred_at=NOW)
    assert not any(len(item) == 3 and item[0] == SCOPE for item in calls)


def test_unknown_owner_result_is_not_retried_with_new_identity():
    issuer, _ = _issuer()
    calls = []
    def unknown(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError('commit outcome unknown')
    issuer._owner.create = unknown
    with pytest.raises(RuntimeError, match='unknown'):
        issuer.issue(SCOPE, 'run-1', _request(), actor='analyst-owner', occurred_at=NOW)
    assert len(calls) == 1
