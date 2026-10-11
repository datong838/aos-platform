"""Read-only reconciliation of the retained Plan and actual recovery gates."""
import hashlib
import json
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_responsibility_template_authority import InstalledProductionProfileResolver, ApprovedBIPreparationResolver
from aos_api.asset_registry.signature import FileTrustRootProvider

r = C.R
b = json.loads((r / 'plan-guards-business-result.json').read_text())
reader = lambda scope: C.runtime(scope, read_only=True)
store = AipProductionContractStore(reader)
with reader(C.SCOPE) as conn:
    plan = store.get_responsibility_plan(C.SCOPE, b['historicalPlanId'], conn=conn)
    assert (plan.revision, plan.content_hash, plan.version) == (b['historicalRevision'], b['historicalHash'], b['historicalVersion'])
    assert plan.lifecycle.value == 'frozen' and len(plan.slots) == 6 and plan.readiness.value == 'blocked'
    assert [x.code for x in plan.blockers] == b['originalBlockers']
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', ('aos_bi_plan_issuer',)).fetchone()
    assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key LIKE 'qyh-plan-%%'").fetchone()['n'] == 0
    assert conn.execute("SELECT count(*) AS n FROM aip_responsibility_successor WHERE idempotency_key='qyh-plan-successor-denied'").fetchone()['n'] == 0
root = C.ROOT / '.evidence/qyh-full-system-restoration-20261011/selected-public-bundles'
trust = FileTrustRootProvider(C.ROOT / '.evidence/qyh-full-system-restoration-20261011/restoration-public-trust-roots.json')
assert not InstalledProductionProfileResolver(reader, release_root=root).resolve(C.SCOPE, plan.template_ref)
preparer = ApprovedBIPreparationResolver(reader, registry_connect_factory=lambda: reader(C.SCOPE), release_root=root, trust_roots=trust, source_alias='a0v-canonical', registry_prepared_transaction=True)
assert len(preparer._approved_rows(C.SCOPE)) == 0 and preparer.select(C.SCOPE) is None
source = 'qyh-restored-pg-20261011'
assert C.S.P.M.fingerprint(source) == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata(source) == C.S.D.metadata(C.TARGET)
readback = {'historicalExactFrozenPlanAndSixSlotsPreserved': True, 'originalCurrentBlockers': b['originalBlockers'], 'originalSignedInstalledResolverRejectedHistoricalRef': True, 'signedApprovedCandidateCount': 0, 'noNewPlanOrSuccessorReceipt': True, 'temporaryRoleRemoved': True, 'sourceAndOriginalClone647DataExact': True, 'allOriginalMetadataExact': True, 'genericBISuccessorPositiveAccepted': False, 'fullRestorationAccepted': False, 'scriptHash': hashlib.sha256((r / 'real_plan_guards.py').read_bytes()).hexdigest()}
with (r / 'plan-guards-independent-readback.json').open('x') as out:
    out.write(json.dumps(readback, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'signedInstallationRecoveryGapVerified': True, 'historicalPlanPreserved': True}))
