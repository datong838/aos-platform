"""Original Content registration negative gate, with real read-only dependencies."""
import ast
import hashlib
import json
from pathlib import Path
import real_contract as C
from aos_api.aip_content_contracts import ContentDraftReadinessRequest, ContentDraftRegisterRequest
from aos_api.aip_content_draft_readiness import AipContentDraftReadinessService
from aos_api.aip_content_draft_store import AipContentDraftStore, UnavailableContentObjectVerifier, ContentDraftRegistrationBlocked

r = C.R
target = r / 'content-registration-gate-result.json'
assert not target.exists(), 'Existing read result: review instead of overwrite'
frozen = json.loads((C.ROOT / '.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
item = json.loads(C.S.run(['inspect', '--format', '{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}', C.TARGET]))
assert item['Id'] == frozen['container']['Id'] and item['Mounts'] == []
assert item['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
sources = {n: C.ROOT / 'services/aos-api/aos_api' / n for n in ('aip_content_draft_readiness.py', 'aip_content_draft_store.py', 'routers/aip_content_drafts.py')}
tree = ast.parse(sources['aip_content_draft_readiness.py'].read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AipContentDraftReadinessService')
budget_method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_budget')
last = budget_method.body[-1]
assert isinstance(last, ast.Expr) and isinstance(last.value, ast.Call)
assert ast.unparse(last.value.func) == 'blockers.append'
assert last.value.args[0].args[0].value == 'CONTENT_DRAFT_BUDGET_BALANCE_AUTHORITY_UNAVAILABLE'
route_tree = ast.parse(sources['routers/aip_content_drafts.py'].read_text())
route_store = next(n for n in route_tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_STORE' for t in n.targets))
assert isinstance(route_store.value, ast.Call) and ast.unparse(route_store.value.func) == 'AipContentDraftStore'
assert not route_store.value.args and not route_store.value.keywords
before, metadata = C.S.P.M.fingerprint(C.TARGET), C.S.D.metadata(C.TARGET)
reader = lambda scope: C.runtime(scope, read_only=True)
def count(conn):
    return {t: conn.execute('SELECT count(*) AS n FROM ' + t).fetchone()['n'] for t in ('aip_artifact', 'aip_production_contract_receipt', 'aip_task_run', 'aip_agent_run')}
with reader(C.SCOPE) as conn:
    initial = count(conn)
    exact = {}
    for label, table, column, kind in (
        ('briefRef', 'aip_task_brief_revision', 'brief_id', 'TaskBriefRevision'),
        ('stageTemplateRef', 'aip_stage_template_revision', 'template_id', 'StageTemplateRevision'),
        ('responsibilityPlanRef', 'aip_responsibility_plan_revision', 'plan_id', 'ResponsibilityPlanRevision'),
        ('evalContractRef', 'aip_eval_contract_revision', 'contract_id', 'EvalContractRevision'),
        ('budgetRef', 'aip_budget_revision', 'budget_id', 'BudgetRevision'),
    ):
        row = conn.execute(f'SELECT {column} AS id,revision,content_hash FROM {table} WHERE org_id=%s AND project_id=%s ORDER BY revision DESC,{column} LIMIT 1', C.SCOPE.key).fetchone()
        assert row
        exact[label] = {'resourceType': kind, 'resourceId': row['id'], 'revision': row['revision'], 'contentHash': row['content_hash']}
    family = json.loads((r / 'artifact-family-business-result.json').read_text())
    run = conn.execute('SELECT run_id,version,status FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*C.SCOPE.key, family['runId'])).fetchone()
    assert run and run['status'] == 'queued'
    agent_id = 'qyh-content-gate-absent-agent'
    assert not conn.execute('SELECT 1 FROM aip_agent_run WHERE org_id=%s AND project_id=%s AND agent_run_id=%s', (*C.SCOPE.key, agent_id)).fetchone()
    bundle = conn.execute('SELECT bundle_id,revision,content_hash FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s ORDER BY bundle_id,revision LIMIT 1', C.SCOPE.key).fetchone()
    assert bundle
request = ContentDraftReadinessRequest.model_validate({
    'briefRef': exact['briefRef'],
    'pipeline': {**exact, 'modelRouteRef': None, 'runtimePolicyRef': None, 'capabilityRefs': [], 'toolBindingRefs': [], 'readiness': 'blocked', 'blockers': [{'code': 'CURRENT_PIPELINE_NOT_BOUND', 'message': 'Explicit isolated negative request; no current runtime binding'}]},
    'taskRunRef': {'resourceType': 'TaskRun', 'resourceId': run['run_id'], 'revision': str(run['version']), 'authority': 'qyh-isolated-negative-probe'},
    'agentRunRef': {'resourceType': 'AgentRun', 'resourceId': agent_id, 'revision': '1', 'authority': 'qyh-isolated-negative-probe'},
    'variantKey': 'qyh-source-negative-only', 'channel': 'weapp',
})
service = AipContentDraftReadinessService(reader)
decision = service.evaluate(C.SCOPE, request)
codes = sorted({x.code for x in decision.blockers})
assert decision.readiness.value == 'blocked'
assert 'CONTENT_DRAFT_BUDGET_BALANCE_AUTHORITY_UNAVAILABLE' in codes
assert 'CONTENT_DRAFT_MODEL_ROUTE_UNAVAILABLE' in codes
content = '栖月汇隔离负门请求；无经营正文、无生成或提交'.encode()
body = ContentDraftRegisterRequest(readiness_request=request,
    content_object={'contentRef': 'memory://qyh-isolated-content-negative', 'contentHash': hashlib.sha256(content).hexdigest(), 'byteSize': len(content), 'mediaType': 'text/plain', 'schemaRef': {'resourceType': 'Schema', 'resourceId': 'content-draft-v1', 'revision': '1', 'authority': 'isolated-negative-only'}},
    prompt_hash=hashlib.sha256(b'qyh-negative-no-provider').hexdigest(),
    evidence_bundle_ref={'resourceType': 'EvidenceBundleRevision', 'resourceId': bundle['bundle_id'], 'revision': bundle['revision'], 'contentHash': bundle['content_hash']})
opened = []
def must_not_write(scope):
    opened.append(scope.key)
    raise AssertionError('Blocked request opened registration writer')
store = AipContentDraftStore(must_not_write, readiness_service=service)
assert isinstance(store._content_verifier, UnavailableContentObjectVerifier)
try:
    store.register(C.SCOPE, 'clone:test', 'qyh-content-negative-no-write', body)
except ContentDraftRegistrationBlocked as error:
    assert str(error).startswith('CONTENT_DRAFT_NOT_READY:')
    register_error = str(error)
else:
    raise AssertionError('Actual blocked dependencies registered a draft')
assert opened == []
try:
    UnavailableContentObjectVerifier().verify(C.SCOPE, body)
except ContentDraftRegistrationBlocked as error:
    assert str(error).startswith('CONTENT_OBJECT_AUTHORITY_UNAVAILABLE:')
    verifier_error = str(error)
else:
    raise AssertionError('Unconfigured object verifier accepted content')
with reader(C.SCOPE) as conn:
    assert count(conn) == initial
assert C.S.P.M.fingerprint(C.TARGET) == before
assert C.S.D.metadata(C.TARGET) == metadata
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
assert C.S.D.metadata('qyh-restored-pg-20261011') == metadata
result = {'task': 'qyh-source-boundary-rehearsal-20261011', 'authority': 'AOS-001889', 'head': '305e15c4115d60d24c3264e703de97f0733a5e8a', 'containerId': item['Id'], 'database': C.DB,
          'exactDependencyRefs': exact, 'actualBlockers': codes, 'registerError': register_error, 'verifierError': verifier_error,
          'budgetBalanceUnconditionalBlocker': True, 'formalRouterVerifierUnconfigured': True, 'writeConnectionOpened': False,
          'businessRowCountsUnchanged': True, 'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True,
          'positiveContentCompatibilityAccepted': False, 'onlyOIDCConfigurationMissing': False, 'fullRestorationAccepted': False,
          'sourceHashes': {n: hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}, 'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with target.open('x') as out:out.write(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'contentRegistrationBlockedBeforeWriter': True, 'actualBlockers': codes, 'structuralGaps': ['budget balance hook', 'governed object verifier'], 'currentDatabaseTouched': False}))
