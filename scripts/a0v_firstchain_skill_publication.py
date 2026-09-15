"""Explicit clone-only contract preparation, never real business analysis."""
from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'aip'))
from bootstrap_r06_data_advisor_authority import _isolated_registry, exact_model_alias
from bootstrap_r06_data_advisor_skill_authority import _skill_eval
from bootstrap_r2_d03_pilot import _isolated_registry as _d03_registry
from bootstrap_r2_d03_skill_authority import _skill_eval as _d03_skill_eval
from aos_api.aip_d03_pilot import build_d03_graph_request, evaluate_d03_contract
from aos_api.aip_agent_registry_contracts import PublishEvaluatedSkillRevisionRequest
from aos_api.aip_data_advisor_logic import build_data_advisor_graph_request, evaluate_data_advisor_contract
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_store import EvalEvidenceStore, EvalNotFound, LogicEvalEvidenceReader
from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_dry_run_models import LogicDryRunRequest
from aos_api.aip_logic_graph_models import logic_graph_content_payload
from aos_api.aip_logic_graph_store import LogicGraphStore, LogicGraphNotFound
from aos_api.aip_logic_publication_models import PublishLogicGraphRequest
from aos_api.aip_logic_publication_store import LogicPublicationStore
from aos_api.aip_logic_run_store import LogicRunStore
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest, PublishReleaseRequest
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_skill_publication_service import AipSkillPublicationService, PostgresSkillPublicationRouteAuthority
from aos_api.aip_skill_registry import AipSkillRegistry
from a0v_formal_text_model import SCOPE, MODEL_ID, ROUTE_ID, exact, canonical_hash

ALLOWED_CLONE = 'aos_upgrade_check_f1dc452abade'
ACTOR = 'a0v-firstchain-contract-preparation'


ROLE_COMPONENTS = {
    'S01': ('customer_service', 'r09_customer_service'),
    'P01': ('private_domain_manager', 'r07_private_domain_manager'),
    'C06': ('content_officer', 'r11_content_officer'),
    'A02': ('campaign_planner', 'r10_campaign_planner'),
    'G06': ('shopping_advisor', 'r08_shopping_advisor'),
}


def role_components(logic_id):
    import importlib
    if logic_id == 'A02':
        from aos_api.aip_a02_pilot import build_a02_graph_request, evaluate_a02_contract
        from bootstrap_r2_a02_pilot import _isolated_registry as adapters
        from bootstrap_r2_a02_skill_authority import _skill_eval as evaluate_skill
        return (lambda _id, **kw: build_a02_graph_request(**kw),
            lambda _id, graph, registry, **kw: evaluate_a02_contract(graph, registry, **kw),
            adapters, lambda _id, *args, **kw: evaluate_skill(*args, **kw))
    family, script = ROLE_COMPONENTS[logic_id]
    logic = importlib.import_module('aos_api.aip_'+family+'_logic')
    adapter = importlib.import_module('bootstrap_'+script+'_authority')
    skill = importlib.import_module('bootstrap_'+script+'_skill_authority')
    return getattr(logic,'build_'+family+'_graph_request'), getattr(logic,'evaluate_'+family+'_contract'), adapter._isolated_registry, skill._skill_eval


def contract_components(logic_id):
    if logic_id == 'D03':
        return (lambda alias: build_d03_graph_request(model_id=alias),
            lambda graph, registry, now: evaluate_d03_contract(graph, registry, now=now),
            _d03_registry)
    if logic_id in ('D01', 'D02'):
        return (lambda alias: build_data_advisor_graph_request(logic_id, model_id=alias),
            lambda graph, registry, now: evaluate_data_advisor_contract(logic_id, graph, registry, now=now),
            _isolated_registry)
    if logic_id in ROLE_COMPONENTS:
        build, evaluate, registry, _ = role_components(logic_id)
        return (lambda alias: build(logic_id, model_id=alias),
            lambda graph, adapters, now: evaluate(logic_id, graph, adapters, now=now), registry)
    raise ValueError('FIRSTCHAIN_SKILL_UNSUPPORTED')


def require_clone(connect):
    if not callable(connect):
        raise ValueError('EXPLICIT_CLONE_CONNECTION_REQUIRED')
    with connect(SCOPE) as conn:
        row = conn.execute('SELECT current_database() AS database').fetchone()
        if row is None or row['database'] != ALLOWED_CLONE:
            raise ValueError('FIRSTCHAIN_CONTRACT_CLONE_ONLY')


def versioned_logic_evidence(evaluated, graph, key):
    report = evaluated.report
    if (report.target_id, report.target_revision, report.target_hash) != (graph.id, graph.revision, graph.graph_hash):
        raise ValueError('FIRSTCHAIN_LOGIC_EVAL_TARGET_DRIFT')
    suite = evaluated.suite.model_copy(update={'id': key+'-suite'})
    return suite, report.model_copy(update={'suite_id': suite.id})


def _logic(connect, logic_id, model):
    store = LogicGraphStore(connect)
    build, evaluate, adapters = contract_components(logic_id)
    request = build(exact_model_alias(model))
    try:
        graph = store.get(*SCOPE.key, request.id)
    except LogicGraphNotFound:
        graph = store.create(*SCOPE.key, ACTOR, request)
    expected = logic_graph_content_payload(request)
    actual = graph.model_dump(mode='json', include=set(expected))
    if actual != expected:
        raise ValueError('FIRSTCHAIN_LOGIC_DRIFT')
    key = 'a0v-contract-'+logic_id.lower()+'-'+graph.graph_hash[:24]
    registry = adapters(exact_model_alias(model))
    evidence = EvalEvidenceStore(connect)
    try:
        report = evidence.get_report(*SCOPE.key, key+'-report')
        suite = evidence.get_suite(*SCOPE.key, report.suite_id)
    except EvalNotFound:
        evaluated = evaluate(graph, registry, datetime.now(UTC))
        expected_suite, expected_report = versioned_logic_evidence(evaluated, graph, key)
        suite = evidence.create_suite(*SCOPE.key, ACTOR, expected_suite)
        if suite.model_dump(mode='json') != expected_suite.model_dump(mode='json'):
            raise ValueError('FIRSTCHAIN_LOGIC_SUITE_DRIFT')
        report = expected_report.model_copy(update={'report_id': key+'-report'})
        report = evidence.save_report(*SCOPE.key, ACTOR, report)
    if (report.target_id, report.target_revision, report.target_hash) != (graph.id, graph.revision, graph.graph_hash) or not report.gate_passed:
        raise ValueError('FIRSTCHAIN_LOGIC_REPORT_DRIFT')
    positive = next(case.inputs for case in suite.cases if case.id == logic_id.lower()+'-positive')
    runs = LogicRunStore(connect)
    command = LogicDryRunRequest(expected_revision=graph.revision, expected_graph_hash=graph.graph_hash,
        dry_run=True, inputs=positive, idempotency_key=key+'-dry-run')
    start = runs.start_run(*SCOPE.key, ACTOR, graph, command, key+'-run')
    if start.replay is None:
        run = LogicDryRunExecutor(registry).execute_guarded(graph, positive,
            run_id=start.run_id, started_at=start.started_at)
        runs.finalize_run(*SCOPE.key, run)
    else:
        run = start.replay
    if run.status != 'succeeded' or run.production_written is not False:
        raise ValueError('FIRSTCHAIN_LOGIC_DRY_RUN_NOT_PASSED')
    publication = LogicPublicationStore(connect).publish(*SCOPE.key, ACTOR, graph.id,
        PublishLogicGraphRequest(expected_revision=graph.revision, expected_graph_hash=graph.graph_hash,
            eval_suite_id=report.suite_id, eval_report_id=report.report_id, idempotency_key=key+'-publish'),
        LogicEvalEvidenceReader())
    return graph, publication


def prepare_contracts(connect):
    return materialize_contracts(connect, require_target=require_clone,
        database=ALLOWED_CLONE, authority_scope='clone-only-contract-preparation')


def materialize_contracts(connect, *, require_target, database, authority_scope, logic_ids=('D01','D02','D03')):
    if not logic_ids or len(set(logic_ids))!=len(logic_ids) or not set(logic_ids)<={'D01','D02','D03',*ROLE_COMPONENTS}:
        raise ValueError('FIRSTCHAIN_SKILL_SET_UNSUPPORTED')
    require_target(connect)
    runtime = AipModelRuntimeStore(connect)
    model = runtime.get_model(SCOPE, MODEL_ID)
    route = runtime.get_route(SCOPE, ROUTE_ID)
    policy = runtime.get_policy(SCOPE, route.runtime_policy_ref.asset_id, route.runtime_policy_ref.revision)
    route_ref = exact('ModelRouteRevision', route, 'route_id')
    policy_ref = exact('RuntimePolicyRevision', policy, 'policy_id')
    route_authority = PostgresSkillPublicationRouteAuthority(store=runtime, eval_authority=AipEvalAuthorityStore(connect))
    route_authority.require_ready(SCOPE, route_ref, policy_ref, evaluated_at=datetime.now(UTC))
    runtime.require_model_governance(SCOPE, model, runtime.get_price_snapshot(SCOPE, model.price_snapshot_ref.asset_id, model.price_snapshot_ref.revision))
    if not any(candidate.model == exact('RegisteredModelRevision', model, 'registered_model_id') for candidate in route.candidates):
        raise ValueError('FIRSTCHAIN_MODEL_ROUTE_DRIFT')
    result = []
    for logic_id in logic_ids:
        require_target(connect)
        graph, logic_publication = _logic(connect, logic_id, model)
        source = AipSkillRegistry(connect).get_skill('ecommerce.skill.'+logic_id, 1)
        if source.lifecycle.value != 'evaluated':
            raise ValueError('FIRSTCHAIN_SOURCE_SKILL_NOT_EVALUATED')
        if logic_id == 'D03':
            suite, report = _d03_skill_eval(source, graph, model, connect_factory=connect, actor=ACTOR)
        elif logic_id in ROLE_COMPONENTS:
            suite, report = role_components(logic_id)[3](logic_id, source, graph, model, connect_factory=connect, actor=ACTOR)
        else:
            suite, report = _skill_eval(logic_id, source, graph, model, connect_factory=connect, actor=ACTOR)
        release = AipReleasePublicationService(connect)
        key = 'a0v-firstchain-'+logic_id.lower()+'-'+suite.content_hash[:24]
        if graph.revision > 1:
            key = 'a0v-successor-'+logic_id.lower()+'-'+canonical_hash({
                'graph': graph.graph_hash, 'revision': graph.revision,
                'route': route_ref.model_dump(mode='json'),
                'policy': policy_ref.model_dump(mode='json'),
                'authority': authority_scope})[:32]
        gate = release.derive_gate(SCOPE, actor=ACTOR, request=DeriveReleaseGateRequest(
            reportId=report.report_id, reportRevision=report.revision, reportHash=report.content_hash,
            idempotencyKey=key+'-gate'))
        event = release.publish(SCOPE, actor=ACTOR, request=PublishReleaseRequest(
            releaseGateDecisionId=gate.decision_id,
            reasonHash=canonical_hash({'authority': 'AOS-000573', 'scope': authority_scope}),
            idempotencyKey=key+'-publication'))
        from aos_api.aip_agent_registry_contracts import VersionedAssetRef
        skill, _ = AipSkillPublicationService(connect, route_authority=route_authority).publish_evaluated_revision(SCOPE,
            PublishEvaluatedSkillRevisionRequest(
                sourceSkill=exact('SkillTemplate', source, 'skill_id'), publicationId=event.publication_id,
                releaseGateDecisionId=gate.decision_id, modelRouteRef=route_ref, runtimePolicyRef=policy_ref,
                logicRevisionRef=VersionedAssetRef(assetType='LogicRevision', assetId=graph.id,
                    revision=graph.revision, contentHash=graph.graph_hash), idempotencyKey=key+'-skill'), actor=ACTOR)
        result.append({'skill': exact('SkillTemplateRevision', skill, 'skill_id').model_dump(mode='json'),
            'logicPublicationId': logic_publication.publication_id, 'contractCasesPassed': report.passed})
    return {'database': database, 'skills': result, 'providerCalls': 0, 'businessPlansGenerated': 0,
        'readiness': 'CONTRACT_PREPARATION_ONLY', 'bindingsActivated': 0}
