"""Native formal evaluator facts; complete command remains under construction.

Health uses the original provider-ID shared epoch fence. It blocks concurrent
writers while held and preserves PostgreSQL 40001 on snapshot conflicts. Latest
exact observations and database time are required; this reader grants no start
permission and performs no provider call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import ValidationError

from aos_api.aip_binding_evaluator_connection import (
    BindingEvaluatorConnectionBlocked, require_binding_evaluator_transaction,
)
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.tenant_scope import TenantScope


class FormalBindingEvaluationBlocked(RuntimeError):
    """Current original authorities cannot establish formal readiness."""


def _exact(ref):
    return FormalExactRef.model_validate(ref.model_dump(mode='json', by_alias=True))


def _versioned(ref):
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    return VersionedAssetRef.model_validate(_exact(ref).model_dump(by_alias=True))


def _json_fact(value):
    def encode(item):
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError('unsupported formal fact value')
    return json.loads(json.dumps(value, default=encode))


def _source_proof_fact(ref, fact):
    """Serialize the original formal authority, including its generation fence."""
    source = fact.source
    return _json_fact({
        'ref': ref.model_dump(by_alias=True), 'issuanceId': source.issuance_id,
        'epoch': source.epoch, 'installationId': source.installation_id,
        'installationEtag': source.installation_etag,
        'ownerAuthorizationRef': source.owner_authorization_ref,
        'policyRef': source.policy_ref, 'sourceRequestHash': fact.source_request_hash,
        'receiptId': source.receipt_id, 'approvalEventId': fact.approval_event_id,
        'requestHash': fact.receipt_request_hash, 'validUntil': fact.valid_until,
    })


def _read_formal_eval_contract(conn, scope, ref, *, return_fact=False):
    """Reuse original dynamic blockers under the original current-head lock."""
    from aos_api.aip_production_contract_store import AipProductionContractStore
    require_binding_evaluator_transaction(conn, scope)
    exact = _exact(ref)
    if exact.asset_type != 'EvalContractRevision':
        raise FormalBindingEvaluationBlocked('CURRENT_READY_FROZEN_EVAL_CONTRACT_REQUIRED')
    head = conn.execute('SELECT current_revision FROM public.aip_eval_contract_head '
        'WHERE org_id=%s AND project_id=%s AND contract_id=%s FOR SHARE',
        (*scope.key, exact.asset_id)).fetchone()
    contract = AipProductionContractStore().get_eval_contract(scope,
        exact.asset_id, exact.revision, conn=conn)
    if (head is None or head['current_revision'] != exact.revision
            or contract.content_hash != exact.content_hash or contract.lifecycle.value != 'frozen'
            or contract.readiness.value != 'ready' or contract.blockers):
        raise FormalBindingEvaluationBlocked('CURRENT_READY_FROZEN_EVAL_CONTRACT_REQUIRED')
    publication = conn.execute('SELECT publication_id FROM public.aip_publication_event '
        'WHERE org_id=%s AND project_id=%s AND event_id=%s',
        (*scope.key, contract.publication_ref.resource_id)).fetchone()
    if publication is None:
        raise FormalBindingEvaluationBlocked('CURRENT_READY_FROZEN_EVAL_CONTRACT_REQUIRED')
    epoch = conn.execute('SELECT public.aos_publication_epoch_lock(%s,%s,%s) AS epoch',
        (*scope.key, publication['publication_id'])).fetchone()['epoch']
    # Protection must precede the authoritative read; discovery granted nothing.
    contract = AipProductionContractStore().get_eval_contract(scope,
        exact.asset_id, exact.revision, conn=conn)
    if contract.readiness.value != 'ready' or contract.blockers:
        raise FormalBindingEvaluationBlocked('CURRENT_READY_FROZEN_EVAL_CONTRACT_REQUIRED')
    fact = {'publicationId': publication['publication_id'], 'epoch': epoch,
            'eventRef': contract.publication_ref.model_dump(mode='json', by_alias=True),
            'gateRef': contract.release_gate_ref.model_dump(mode='json', by_alias=True)}
    return (contract, fact) if return_fact else contract


def _protect_runtime_graph(conn, scope, request, store, bound, now):
    """Protect all original route candidates, then reuse the original resolver.

    Discovery grants nothing. The native transaction retains the original head
    and epoch locks; every discovered revision is reread after protection.
    """
    from aos_api.aip_model_runtime_store import canonical_hash
    from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
    from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
    from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
    from aos_api.aip_network_policy_store import AipNetworkPolicyStore
    from aos_api.aip_provider_plugin_authority import ProviderPluginAuthority
    graph = {}
    def discover(kind, ref):
        exact = _exact(ref)
        identity = kind, exact.asset_id
        if identity in graph:
            if graph[identity][0] != exact:
                raise FormalBindingEvaluationBlocked('RUNTIME_GRAPH_REFERENCE_CONFLICT')
            return graph[identity][1]
        item = store._get(kind, scope, exact.asset_id, exact.revision)
        graph[identity] = exact, item
        return item
    route = discover('model_route', request.route_ref)
    discover('runtime_policy', request.policy_ref)
    for candidate in route.candidates:
        model = discover('registered_model', candidate.model)
        discover('provider_instance', model.provider)
        discover('model_price_snapshot', model.price_snapshot_ref)
    for kind, ref in (('registered_model', request.model_ref),
                      ('provider_instance', request.provider_ref),
                      ('model_price_snapshot', request.price_ref)):
        discover(kind, ref)
    if _exact(route.runtime_policy_ref) != request.policy_ref:
        raise FormalBindingEvaluationBlocked('ROUTE_POLICY_EXACT_REF_DRIFT')
    protected = {}
    for (kind, identity), (ref, discovered) in sorted(graph.items()):
        column = kind + '_id'
        head = conn.execute(f'SELECT current_revision FROM public.aip_{kind}_head '
            f'WHERE org_id=%s AND project_id=%s AND {column}=%s FOR SHARE',
            (*scope.key, identity)).fetchone()
        item = store._get(kind, scope, identity, ref.revision)
        row = conn.execute(f'SELECT content_hash,lifecycle FROM public.aip_{kind}_revision '
            f'WHERE org_id=%s AND project_id=%s AND {column}=%s AND revision=%s',
            (*scope.key, identity, ref.revision)).fetchone()
        body = item.model_dump(mode='json', by_alias=True)
        content = {k: v for k, v in body.items() if k not in store._META_FIELDS}
        if (head is None or head['current_revision'] != ref.revision or item != discovered
                or row is None or row['content_hash'] != ref.content_hash or row['lifecycle'] != 'active'
                or item.content_hash != ref.content_hash or item.lifecycle.value != 'active'
                or item.revision != ref.revision or body[store._SPECS[kind][0]] != identity
                or (item.tenant.org_id, item.tenant.project_id) != scope.key
                or canonical_hash(content) != ref.content_hash):
            raise FormalBindingEvaluationBlocked('RUNTIME_CURRENT_EXACT_REVISION_REQUIRED')
        protected[kind, identity] = item

    dependencies = {}
    def dependency(ref):
        exact = _exact(ref)
        key = exact.asset_type, exact.asset_id
        if key in dependencies and dependencies[key] != exact:
            raise FormalBindingEvaluationBlocked('RUNTIME_POLICY_REFERENCE_CONFLICT')
        dependencies[key] = exact
    for (kind, _), item in protected.items():
        if kind in {'registered_model', 'runtime_policy'}:
            dependency(item.quota_policy_ref)
            dependency(item.budget_policy_ref)
        if kind in {'provider_instance', 'runtime_policy'}:
            dependency(item.egress_policy_ref)
            dependency(item.data_classification_policy_ref)
        if kind == 'runtime_policy':
            dependency(item.network_policy_ref)
    policies, deadlines = {}, []
    governance = AipModelGovernancePolicyStore(bound)
    guards = AipRuntimeGuardPolicyStore(bound)
    network = AipNetworkPolicyStore(bound, guard_policy_store=guards)
    for key, ref in sorted(dependencies.items()):
        kind = {'QuotaPolicyRevision': 'quota', 'BudgetPolicyRevision': 'budget',
                'EgressPolicyRevision': 'egress', 'DataClassificationPolicyRevision': 'data_classification'}.get(ref.asset_type)
        if ref.asset_type == 'NetworkPolicyRevision':
            table, extra = 'aip_network_policy_head', ()
            reader = network
        elif ref.asset_type in {'QuotaPolicyRevision', 'BudgetPolicyRevision'}:
            table, extra, reader = 'aip_model_governance_policy_head', (kind,), governance
        elif kind is not None:
            table, extra, reader = 'aip_runtime_guard_policy_head', (kind,), guards
        else:
            raise FormalBindingEvaluationBlocked('RUNTIME_POLICY_AUTHORITY_KIND_REQUIRED')
        where = ' AND policy_kind=%s' if extra else ''
        head = conn.execute(f'SELECT current_revision FROM public.{table} '
            f'WHERE org_id=%s AND project_id=%s{where} AND policy_id=%s FOR SHARE',
            (*scope.key, *extra, ref.asset_id)).fetchone()
        item = reader.require_exact_active(scope, _versioned(ref), now=now)
        if (head is None or head['current_revision'] != ref.revision
                or item.policy_id != ref.asset_id or item.revision != ref.revision
                or (item.tenant.org_id, item.tenant.project_id) != scope.key):
            raise FormalBindingEvaluationBlocked('RUNTIME_POLICY_CURRENT_HEAD_REQUIRED')
        policies[key] = item
        deadlines.append(item.effective_until)
    for (kind, identity), item in sorted(protected.items()):
        if kind == 'provider_instance':
            ProviderPluginAuthority().validate_ref(scope, item.plugin_ref)
            # Retain each original Provider-ID epoch through the caller commit.
            ref = graph[kind, identity][0]
            conn.execute('SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true)',
                (*scope.key, json.dumps(ref.model_dump(by_alias=True)))).fetchone()
        elif kind == 'runtime_policy':
            network.require_runtime_policy_dependency(scope, item)
    resolution = AipModelRuntimeResolver(store).resolve(scope, request.route_ref.asset_id, now=now)
    if (resolution.readiness.value != 'ready'
            or _exact(resolution.route) != request.route_ref or _exact(resolution.policy) != request.policy_ref
            or _exact(resolution.selected_model) != request.model_ref
            or _exact(resolution.selected_provider) != request.provider_ref
            or _exact(resolution.selected_price_snapshot) != request.price_ref):
        raise FormalBindingEvaluationBlocked('ORIGINAL_ROUTE_RESOLUTION_REQUIRED')
    selected = read_current_provider_health_fact(conn, scope, request.provider_ref.model_dump(by_alias=True))
    if selected.status != 'healthy':
        raise FormalBindingEvaluationBlocked('CURRENT_HEALTHY_PROVIDER_REQUIRED')
    return protected, policies, selected, deadlines


def evaluate_binding_in_transaction(conn, scope, binding_id, request, principal, *,
                                    idempotency_key, loader, release_policy):
    """Evaluate all original facts and write CAS/Receipt/proof in the caller txn.

    No commit, savepoint, retry, reservation, installation change or provider
    invocation. The caller must propagate errors and perform the real commit.
    Product routing awaits full signed positive and commit acceptance.
    """
    from dataclasses import asdict
    from datetime import timedelta
    from uuid import uuid4
    from aos_api.auth import Principal
    from aos_api.aip_binding_formal_evaluator_contracts import FormalBindingEvaluationRequest
    from aos_api.aip_agent_registry_contracts import OperationalBindingDependencies, OperationalBindingReadiness
    from aos_api.aip_contracts import ResourceRef
    from aos_api.aip_agent_registry_store import AipAgentRegistryStore, AipAgentRegistryNotFound, AipAgentRegistryConflict
    from aos_api.aip_capability_binding_service import AipCapabilityBindingService
    from aos_api.aip_capability_registry import AipCapabilityRegistry
    from aos_api.aip_binding_readiness_service import AipBindingReadinessService, PostgresBindingDependencyAuthority
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore, evaluation_candidate_ref
    from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
    from aos_api.aip_model_capacity_authority import (
        AipModelCapacityAuthorityStore, CapacityPoolRevisionCreate, materialize_capacity_pool,
    )
    from aos_api.aip_license_source_authority import _prepare_formal_source_approvals, read_formal_license_source_facts
    from aos_api.aip_budget_cost_runtime import _prepare_formal_budget_approval, read_formal_budget_fact
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory

    if type(request) is not FormalBindingEvaluationRequest:
        raise FormalBindingEvaluationBlocked('STRICT_FORMAL_REQUEST_REQUIRED')
    request = FormalBindingEvaluationRequest.model_validate(request.model_dump(mode='python', by_alias=True))
    require_binding_evaluator_transaction(conn, scope)
    if (type(principal) is not Principal or principal.token_kind != 'oidc'
            or (principal.org_id, principal.project_id) != scope.key
            or type(principal.subject) is not str or not principal.subject
            or principal.subject != principal.subject.strip()
            or type(binding_id) is not str or not 1 <= len(binding_id) <= 200 or binding_id != binding_id.strip()
            or type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 200
            or idempotency_key != idempotency_key.strip()
            or type(loader) is not ManifestLoader or type(release_policy) is not ReleasePolicy):
        raise FormalBindingEvaluationBlocked('FORMAL_PRINCIPAL_PRIVATE_CONTEXT_REQUIRED')
    actor = principal.subject
    registry = AipAgentRegistryStore()
    operation = 'capability_binding.evaluate'
    request_hash = registry._hash({'domain': 'aos.binding-formal-evaluate/v1', 'bindingId': binding_id,
        'actor': actor, 'request': request.model_dump(mode='json', by_alias=True)})
    registry._lock(conn, scope, operation, idempotency_key)
    replay = registry._receipt_row(conn, scope, operation, idempotency_key)
    if replay:
        registry._require_replay_hash(replay, request_hash)
    binding = conn.execute('SELECT * FROM public.aip_capability_binding '
        'WHERE org_id=%s AND project_id=%s AND binding_id=%s FOR UPDATE',
        (*scope.key, binding_id)).fetchone()
    if binding is None:
        raise AipAgentRegistryNotFound('capability binding not found')
    expected = request.expected_version + (1 if replay else 0)
    if binding['version'] != expected or binding['status'] not in {'provisioning', 'active', 'suspended'}:
        raise AipAgentRegistryConflict('formal binding version or lifecycle changed')
    bound = TransactionBoundConnectFactory(HostTransaction(conn), scope)
    capability_ref = FormalExactRef.model_validate(binding['capability_ref'])
    if capability_ref.asset_type != 'CapabilityRevision':
        raise FormalBindingEvaluationBlocked('CAPABILITY_EXACT_REVISION_REQUIRED')
    capability = AipCapabilityRegistry(bound).get(capability_ref.asset_id, capability_ref.revision)
    if capability.lifecycle.value != 'published' or capability.content_hash != capability_ref.content_hash:
        raise FormalBindingEvaluationBlocked('PUBLISHED_CAPABILITY_REQUIRED')

    governance = AipModelGovernancePolicyStore(bound)
    discovered_budget = governance.get_budget(scope, request.budget_policy_ref.asset_id,
                                               request.budget_policy_ref.revision)
    budget_ref = _exact(discovered_budget.budget_revision_ref)
    discovered, approvals = _prepare_formal_source_approvals(conn, scope, request.source_refs)
    _, _, original_budget = _prepare_formal_budget_approval(conn, scope, budget_ref)
    source_members = {subject for _, _, approved, maker in discovered
        for subject in (maker, approvals[approved.resource_id][1]['actor_id'])}
    budget_members = {original_budget.maker_subject, original_budget.checker_subject}
    subjects = sorted(source_members | budget_members | {actor})
    members = conn.execute('SELECT subject,role FROM public.meta_membership '
        'WHERE org_id=%s AND project_id=%s AND subject=ANY(%s) ORDER BY subject FOR SHARE',
        (*scope.key, subjects)).fetchall()
    if ([row['subject'] for row in members] != subjects
            or any(row['role'].lower() != 'owner' for row in members if row['subject'] in source_members)
            or any(row['role'].lower() not in {'owner', 'admin'} for row in members
                   if row['subject'] in budget_members | {actor})):
        raise FormalBindingEvaluationBlocked('CURRENT_ORIGINAL_MEMBERS_REQUIRED')
    sources = read_formal_license_source_facts(conn=conn, scope=scope, source_refs=request.source_refs,
        installation_id=request.installation_id, installation_revision=request.installation_revision,
        installation_etag=request.installation_etag, loader=loader, release_policy=release_policy)
    _prepare_formal_capacity_head(conn, scope, request.capacity_ref)
    budget = read_formal_budget_fact(conn=conn, scope=scope, budget_ref=budget_ref,
        price_ref=request.price_ref, provider_ref=request.provider_ref)
    now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    store = AipModelRuntimeStore(bound)
    graph, policies, health, deadlines = _protect_runtime_graph(conn, scope, request, store, bound, now)
    model = graph['registered_model', request.model_ref.asset_id]
    route = graph['model_route', request.route_ref.asset_id]
    runtime_policy = graph['runtime_policy', request.policy_ref.asset_id]
    if (_exact(model.budget_policy_ref) != request.budget_policy_ref
            or _exact(runtime_policy.budget_policy_ref) != request.budget_policy_ref
            or model.quota_policy_ref != runtime_policy.quota_policy_ref
            or _exact(model.eval_gate_ref) != request.model_eval_gate_ref
            or _exact(route.eval_gate_ref) != request.route_eval_gate_ref):
        raise FormalBindingEvaluationBlocked('SELECTED_ORIGINAL_POLICY_OR_GATE_DRIFT')
    current_budget = policies['BudgetPolicyRevision', request.budget_policy_ref.asset_id]
    if current_budget != discovered_budget or _exact(current_budget.budget_revision_ref) != budget_ref:
        raise FormalBindingEvaluationBlocked('BUDGET_DISCOVERY_DRIFT')
    evals = AipEvalAuthorityStore(bound)
    model_gate = evals.require_exact_passed(scope, _versioned(request.model_eval_gate_ref),
        expected_target=evaluation_candidate_ref(model), now=now)
    route_gate = evals.require_exact_passed(scope, _versioned(request.route_eval_gate_ref),
        expected_target=evaluation_candidate_ref(route), now=now)
    contract, publication_fact = _read_formal_eval_contract(conn, scope, request.eval_contract_ref, return_fact=True)
    pool = AipModelCapacityAuthorityStore(bound, model_store=store).get(scope,
        request.capacity_ref.asset_id, request.capacity_ref.revision, conn=conn)
    pool_body = CapacityPoolRevisionCreate.model_validate(pool.model_dump(mode='python', by_alias=True,
        exclude={'tenant', 'content_hash', 'created_by', 'created_at'}))
    if (pool.lifecycle != 'active' or pool.content_hash != request.capacity_ref.content_hash
            or materialize_capacity_pool(scope, pool.created_by, pool_body, created_at=pool.created_at).content_hash != pool.content_hash
            or _exact(pool.route_ref) != request.route_ref or _exact(pool.model_ref) != request.model_ref
            or _exact(pool.provider_ref) != request.provider_ref):
        raise FormalCapacityUnavailable('CURRENT_EXACT_CAPACITY_CONTENT_REQUIRED')
    quota = policies['QuotaPolicyRevision', model.quota_policy_ref.asset_id]
    if pool.token_unit_per_reservation < quota.max_input_tokens + quota.max_output_tokens:
        raise FormalCapacityUnavailable('CAPACITY_QUANTUM_CANNOT_COVER_QUOTA')
    used = conn.execute('SELECT count(*) AS requests,coalesce(sum(token_units),0) AS tokens '
        'FROM public.aip_model_capacity_reservation WHERE org_id=%s AND project_id=%s '
        "AND pool_id=%s AND pool_revision=%s AND status IN ('reserved','consumed') AND expires_at>%s",
        (*scope.key, pool.pool_id, pool.revision, now)).fetchone()
    used = {key: int(value) for key, value in used.items()}
    if used['requests'] + 1 > pool.max_concurrency or used['tokens'] + pool.token_unit_per_reservation > pool.max_token_units:
        raise FormalCapacityUnavailable('CAPACITY_ORIGINAL_QUANTUM_UNAVAILABLE')

    authority = PostgresBindingDependencyAuthority(bound)
    for required, provided in ((capability.required_data_refs, request.data_dependency_refs),
                               (capability.required_tool_refs, request.tool_dependency_refs)):
        provided_keys = {tuple(ref.model_dump(by_alias=True).values()) for ref in provided}
        if any(tuple(_exact(ref).model_dump(by_alias=True).values()) not in provided_keys for ref in required):
            raise FormalBindingEvaluationBlocked('CAPABILITY_REQUIRED_DEPENDENCY_MISSING')
        if not authority.exact_assets_available(scope, [_versioned(ref) for ref in provided]):
            raise FormalBindingEvaluationBlocked('CAPABILITY_EXACT_DEPENDENCY_UNAVAILABLE')
    source_keys = {(ref.asset_type, ref.asset_id, ref.revision, ref.content_hash) for ref in request.source_refs}
    for ref in request.data_dependency_refs + request.tool_dependency_refs:
        if ref.asset_type == 'EvidenceBundleRevision' and (ref.asset_type, ref.asset_id, ref.revision, ref.content_hash) not in source_keys:
            raise FormalBindingEvaluationBlocked('DEPENDENCY_FORMAL_SOURCE_GRANT_REQUIRED')
    deps = OperationalBindingDependencies(providerRef=_versioned(request.provider_ref),
        modelRouteRef=_versioned(request.route_ref), runtimePolicyRef=_versioned(request.policy_ref),
        evalGateRef=_versioned(request.route_eval_gate_ref), evalContractRef=_versioned(request.eval_contract_ref),
        licenseEvidenceRefs=[ResourceRef(resourceType=ref.asset_type, resourceId=ref.asset_id,
            revision=str(ref.revision), authority='postgresql') for ref in request.source_refs],
        dataDependencyRefs=[_versioned(ref) for ref in request.data_dependency_refs],
        toolDependencyRefs=[_versioned(ref) for ref in request.tool_dependency_refs],
        budgetPolicyRef=_versioned(request.budget_policy_ref), allowDegraded=False)
    legacy_hash = AipBindingReadinessService.snapshot_hash(_versioned(capability_ref), deps)
    budget_fact = asdict(budget)
    budget_fact.pop('checked_at')
    health_fact = asdict(health)
    health_fact.pop('checked_at')
    facts = _json_fact({
        'Provider': {'ref': request.provider_ref.model_dump(by_alias=True)},
        'Model': {'ref': request.model_ref.model_dump(by_alias=True)},
        'Policy': {'ref': request.policy_ref.model_dump(by_alias=True),
                   'dependencies': [ref.model_dump(mode='json', by_alias=True) for ref in
                       (runtime_policy.quota_policy_ref, runtime_policy.budget_policy_ref, runtime_policy.network_policy_ref,
                        runtime_policy.egress_policy_ref, runtime_policy.data_classification_policy_ref)]},
        'Route': {'ref': request.route_ref.model_dump(by_alias=True)},
        'Eval': {'model': request.model_eval_gate_ref.model_dump(by_alias=True),
                 'route': request.route_eval_gate_ref.model_dump(by_alias=True),
                 'contract': request.eval_contract_ref.model_dump(by_alias=True),
                 'publication': publication_fact},
        'Health': health_fact,
        'Capacity': {'ref': request.capacity_ref.model_dump(by_alias=True), 'usedRequests': used['requests'],
            'usedTokens': used['tokens'], 'quantum': pool.token_unit_per_reservation},
        'Price': {'ref': request.price_ref.model_dump(by_alias=True)},
        'Source': [_source_proof_fact(ref, fact)
            for ref, fact in zip(sorted(request.source_refs, key=lambda ref: (ref.asset_id, ref.revision, ref.content_hash)), sources)],
        'Budget': budget_fact, 'Installation': {'installationId': request.installation_id,
            'revision': request.installation_revision, 'etag': request.installation_etag}, 'Owners': members})
    facts_hash = conn.execute("SELECT encode(public.digest(convert_to("
        "public.canonical_asset_registry_jsonb(%s::jsonb),'UTF8'),'sha256'),'hex') AS hash",
        (json.dumps(facts),)).fetchone()['hash']
    checked_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    valid_until = min(checked_at + timedelta(minutes=15), health.expires_at, budget.valid_until,
        model_gate.expires_at, route_gate.expires_at, *deadlines, *(fact.valid_until for fact in sources))
    if checked_at >= valid_until:
        raise FormalBindingEvaluationBlocked('FORMAL_FACT_EXPIRED_BEFORE_WRITE')
    if replay:
        proof = conn.execute('SELECT * FROM public.aip_binding_evaluation_proof '
            'WHERE org_id=%s AND project_id=%s AND receipt_id=%s',
            (*scope.key, replay['receipt_id'])).fetchone()
        if (proof is None or proof['binding_id'] != binding_id or proof['binding_version'] != binding['version']
                or proof['facts_hash'] != facts_hash or proof['legacy_dependency_hash'] != legacy_hash
                or not proof['checked_at'] <= checked_at < proof['valid_until']
                or binding['dependency_snapshot_hash'] != legacy_hash
                or binding['operational_readiness'] != 'available'
                or binding['readiness_expires_at'] != proof['valid_until']
                or replay['result_ref'] != registry._ref('CapabilityBindingReadiness', binding_id,
                    revision=str(binding['version'])).model_dump(mode='json', by_alias=True)):
            raise AipAgentRegistryConflict('formal evaluation replay proof or current facts changed')
        return (AipCapabilityBindingService._from_row(scope, binding),
                AipCapabilityBindingService._readiness_from_row(binding), registry._receipt_from_row(scope, replay))
    row = conn.execute('UPDATE public.aip_capability_binding SET provider_ref=%s::jsonb,model_route_ref=%s::jsonb,'
        'runtime_policy_ref=%s::jsonb,eval_gate_ref=%s::jsonb,eval_contract_ref=%s::jsonb,'
        'license_evidence_refs=%s::jsonb,data_dependency_refs=%s::jsonb,tool_dependency_refs=%s::jsonb,'
        'budget_policy_ref=%s::jsonb,allow_degraded=false,dependency_snapshot_hash=%s,'
        "operational_readiness='available',readiness_reasons='[]'::jsonb,last_evaluated_at=%s,"
        'readiness_expires_at=%s,version=version+1,updated_at=%s '
        'WHERE org_id=%s AND project_id=%s AND binding_id=%s AND version=%s RETURNING *',
        (*(registry._json(ref) for ref in (deps.provider_ref, deps.model_route_ref, deps.runtime_policy_ref,
            deps.eval_gate_ref, deps.eval_contract_ref, deps.license_evidence_refs, deps.data_dependency_refs,
            deps.tool_dependency_refs, deps.budget_policy_ref)), legacy_hash, checked_at, valid_until, checked_at,
            *scope.key, binding_id, request.expected_version)).fetchone()
    if row is None:
        raise AipAgentRegistryConflict('formal binding CAS failed')
    receipt = registry._insert_receipt(conn, scope, operation, idempotency_key, request_hash,
        'CapabilityBinding', binding_id, 'CapabilityBindingReadiness', binding_id, actor,
        checked_at, result_revision=str(row['version']))
    conn.execute('INSERT INTO public.aip_binding_evaluation_proof '
        '(org_id,project_id,proof_id,binding_id,binding_version,installation_id,installation_etag,'
        'receipt_id,legacy_dependency_hash,facts_hash,facts,checked_at,valid_until) '
        'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)',
        (*scope.key, 'b90-proof-' + uuid4().hex, binding_id, row['version'], request.installation_id,
            request.installation_etag, receipt.receipt_id, legacy_hash, facts_hash, json.dumps(facts), checked_at, valid_until))
    readiness = OperationalBindingReadiness(readiness='available', reasons=[], dependencies=deps,
        dependencySnapshotHash=legacy_hash, evaluatedAt=checked_at, expiresAt=valid_until)
    return AipCapabilityBindingService._from_row(scope, row), readiness, receipt


class ProviderHealthFactUnavailable(RuntimeError):
    """Raised when current health cannot be established fail-closed."""


class FormalCapacityUnavailable(RuntimeError):
    """The original pool cannot be protected for formal evaluation."""


def _prepare_formal_capacity_head(conn: Any, scope: TenantScope,
                                 capacity_ref: FormalExactRef) -> None:
    """Prelock the original pool before the Budget fence, without granting rights.

    Original content commands hold this head before require_cost_risk. Reversing
    their order creates a real two-transaction deadlock. Revision content and
    occupancy still require the full command's original authority verification.
    This function neither creates a pool nor reserves or expires capacity.
    """
    require_binding_evaluator_transaction(conn, scope)
    try:
        if type(capacity_ref) is not FormalExactRef:
            raise ValueError('exact capacity reference required')
        exact = FormalExactRef.model_validate(capacity_ref.model_dump(by_alias=True))
        if exact.asset_type != 'ModelCapacityPoolRevision':
            raise ValueError('exact capacity kind required')
    except (ValidationError, TypeError, ValueError):
        raise FormalCapacityUnavailable('CAPACITY_EXACT_REF_REQUIRED') from None
    head = conn.execute(
        'SELECT current_revision,version FROM public.aip_model_capacity_pool_head '
        'WHERE org_id=%s AND project_id=%s AND pool_id=%s FOR UPDATE',
        (*scope.key, exact.asset_id),
    ).fetchone()
    if (head is None or head['current_revision'] != exact.revision
            or type(head['version']) is not int or head['version'] < 1):
        raise FormalCapacityUnavailable('CAPACITY_CURRENT_HEAD_REQUIRED')


@dataclass(frozen=True)
class ProviderHealthFact:
    epoch: int
    observation_id: str
    provider_ref: Dict[str, Any]
    status: str
    availability_pct: Optional[float]
    p50_latency_ms: Optional[int]
    observed_at: datetime
    expires_at: datetime
    checked_at: datetime


def _require_health_consumer_transaction(conn: Any, scope: TenantScope) -> None:
    try:
        require_binding_evaluator_transaction(conn, scope)
    except BindingEvaluatorConnectionBlocked as exc:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_NATIVE_EVALUATOR_TRANSACTION_REQUIRED') from exc


def read_current_provider_health_fact(
    conn: Any,
    scope: Any,
    provider_ref: Dict[str, Any],
) -> ProviderHealthFact:
    """Read the current Provider Health fact for an exact provider.

    Must run inside a transaction whose tenant scope is already set. Acquires a
    shared health epoch fence lock first, then reads the latest observation with
    fail-closed guards. Raises :class:`ProviderHealthFactUnavailable` on any
    condition that would otherwise let a stale or ambiguous observation through.
    """
    _require_health_consumer_transaction(conn, scope)
    try:
        exact = FormalExactRef.model_validate(provider_ref)
    except (ValidationError, TypeError, ValueError):
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EXACT_REF_REQUIRED') from None
    if exact.asset_type != 'ProviderInstanceRevision':
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EXACT_REF_REQUIRED')
    provider_ref = exact.model_dump(mode='json', by_alias=True)
    org, project = scope.key
    asset_id = exact.asset_id

    epoch_row = conn.execute(
        "SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true) AS epoch",
        (org, project, json.dumps(provider_ref, sort_keys=True)),
    ).fetchone()
    if epoch_row is None:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_EPOCH_LOCK_FAILED")
    epoch = int(epoch_row["epoch"])

    rows = conn.execute(
        """SELECT observation_id, provider_ref, status, availability_pct, p50_latency_ms,
                  observed_at, expires_at
           FROM public.aip_provider_health_observation
           WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s
           ORDER BY observed_at DESC, observation_id DESC LIMIT 2""",
        (org, project, asset_id),
    ).fetchall()
    if not rows:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_MISSING")

    latest = rows[0]
    # Two observations sharing the newest observed_at make "latest" ambiguous.
    if len(rows) > 1 and rows[1]["observed_at"] == latest["observed_at"]:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_AMBIGUOUS_LATEST")

    if latest['provider_ref'] != provider_ref:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_LATEST_EXACT_REF_MISMATCH')
    now = conn.execute('SELECT clock_timestamp() AS checked_at').fetchone()['checked_at']
    observed_at, expires_at = latest['observed_at'], latest['expires_at']
    if any(not isinstance(value, datetime) or value.utcoffset() is None
           for value in (now, observed_at, expires_at)):
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_AWARE_TIME_REQUIRED')
    if observed_at > now:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_FUTURE_OBSERVATION')
    if not observed_at <= now < expires_at:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EXPIRED')
    if latest['status'] not in {'healthy', 'degraded', 'unavailable', 'unknown'}:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_STATUS_INVALID')

    return ProviderHealthFact(
        epoch=epoch,
        observation_id=latest["observation_id"],
        provider_ref=provider_ref,
        status=latest["status"],
        availability_pct=latest["availability_pct"],
        p50_latency_ms=latest["p50_latency_ms"],
        observed_at=observed_at,
        expires_at=expires_at,
        checked_at=now,
    )
