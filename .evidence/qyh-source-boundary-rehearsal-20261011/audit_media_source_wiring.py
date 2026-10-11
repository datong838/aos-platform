"""No-effect reproduction of incompatible media-profile production source wiring."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path
import real_contract as C
from aos_api.aip_stage_template_authority import resolve_stage_template_source
from aos_api.aip_production_contracts import (ExactRevisionRef, MediaGateDefinition,
    MediaGateKind, RegisterMediaGateProfileRequest)
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked
from aos_api.tenant_scope import TenantScope

paths = {name: C.ROOT / path for name, path in {
    'resolver': 'services/aos-api/aos_api/aip_stage_template_authority.py',
    'model': 'services/aos-api/aos_api/aip_production_contracts.py',
    'store': 'services/aos-api/aos_api/aip_production_contract_store.py',
    'router': 'services/aos-api/aos_api/routers/aip_production_contracts.py',
    'historicalTest': 'services/aos-api/tests/aip/test_w7_06_media_four_gate.py'}.items()}
trees = {name: ast.parse(path.read_text()) for name, path in paths.items()}
resolver = next(x for x in trees['resolver'].body if isinstance(x, ast.FunctionDef) and x.name == 'resolve_stage_template_source')
guard = next(x for x in resolver.body if isinstance(x, ast.If) and isinstance(x.test, ast.Compare)
    and isinstance(x.test.left, ast.Attribute) and x.test.left.attr == 'resource_type'
    and isinstance(x.test.ops[0], ast.NotEq) and x.test.comparators[0].value == 'SolutionPack')
assert len(guard.body) == 1 and isinstance(guard.body[0], ast.Return) and guard.body[0].value.value is False
wired = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'AipProductionContractStore'
    and any(k.arg == 'stage_template_source_resolver' and isinstance(k.value, ast.Name)
            and k.value.id == 'resolve_stage_template_source' for k in n.keywords)
    for n in ast.walk(trees['router']))
assert wired
test_substitution = any(isinstance(n, ast.keyword) and n.arg == 'stage_template_source_resolver'
    and isinstance(n.value, ast.Lambda) and isinstance(n.value.body, ast.Constant)
    and n.value.body.value is True for n in ast.walk(trees['historicalTest']))
assert test_substitution
ref = lambda kind, ident: ExactRevisionRef(resource_type=kind, resource_id=ident, revision=1, content_hash='a'*64)
body = RegisterMediaGateProfileRequest(profile_id='test-only-wiring-not-signed', revision=1,
    source_bundle_ref=ref('BundleManifestRevision', 'test-only-not-an-authoritative-bundle'),
    signature_ref=ref('BundleSignatureVerification', 'test-only-not-a-signature'),
    policy_ref=ref('MediaGatePolicyRevision', 'test-only-not-a-policy'),
    gates=[MediaGateDefinition(gate_id='media.'+kind.value, kind=kind,
        rule_ref=ref('EvalRuleRevision', 'test-only-'+kind.value), return_stage='fix-'+kind.value)
        for kind in MediaGateKind])
opened = []
def never_connect(scope):
    opened.append(scope.key)
    raise AssertionError('No-effect audit must not open a database')
store = AipProductionContractStore(never_connect, plan_connect_factory=never_connect,
    contract_connect_factory=never_connect, stage_template_source_resolver=resolve_stage_template_source)
denials = []
for scope in (C.SCOPE, TenantScope('dev-org', 'dev-project')):
    assert resolve_stage_template_source(scope, body.source_bundle_ref) is False
    try:
        store.register_media_gate_profile(scope, 'test-only:no-authority', 'test-only:no-db-effect', body)
    except ProductionContractDependencyBlocked as error:
        assert str(error) == 'MEDIA_GATE_PROFILE_SIGNED_SOURCE_MISSING_OR_DRIFTED'
        denials.append({'scope': list(scope.key), 'code': str(error)})
    else:
        raise AssertionError('Original source rejection missing')
assert opened == []
result = {'head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=C.ROOT, text=True).strip(),
    'authority': 'AOS-001894', 'task': 'qyh-source-boundary-rehearsal-20261011',
    'formalRouterUsesOriginalResolver': wired,
    'requestModelRequiresBundleManifestRevision': True,
    'originalResolverRejectsAllBundleManifestRevisionBeforeLookup': True,
    'originalMediaProfileEntryRejectsBeforeDatabaseFactory': denials,
    'historicalAcceptanceReplacesSourceResolverWithLambdaTrue': test_substitution,
    'requestIsExplicitTestOnlyNotSignedOrGoverned': True,
    'databaseConnections': len(opened), 'databaseWrites': 0, 'objectReads': 0, 'objectWrites': 0,
    'currentServiceChanged': False, 'formalPublisherConnected': False, 'fullRestorationAccepted': False,
    'sourceHashes': {k: hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},
    'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (C.R / 'media-source-wiring-result.json').open('x') as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'productionWiringIncompatible': True, 'realOriginalEntryDenials': len(denials),
    'databaseConnections': 0, 'testOnlyRequestDoesNotProveSignature': True}))
