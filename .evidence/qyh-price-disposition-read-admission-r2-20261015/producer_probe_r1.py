"""Original producer compatibility experiment; synthetic memory only, no database."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / 'services/aos-api'))
spec = importlib.util.spec_from_file_location('original_fixture', R / 'services/aos-api/tests/aip/test_w6_06_price_disposition.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from aos_api.ecommerce_workshop_price_disposition import (
    CreatePriceDispositionContractRequest, FreezePriceDispositionRequest,
    PreparePriceDispositionRequest, PriceDispositionKind,
    RecordPriceDispositionObservationRequest, REQUIRED_GATE_TYPES, canonical_hash,
)
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef

def exact(item, kind, identity):
    return PriceExactRef(resourceType=kind, resourceId=getattr(item, identity),
                         revision=item.revision, contentHash='sha256:' + item.content_hash,
                         receiptId='receipt-' + getattr(item, identity))

store, service, case, sku = fixture.authority_fixture()
scope, at = fixture.SCOPE, fixture.NOW
records = []
prepared_rows = []
frozen_rows = []
for kind in PriceDispositionKind:
    contract_request = CreatePriceDispositionContractRequest(
        contractId='probe-contract-' + kind.value, revision=1, kind=kind,
        payloadSchemaRef=fixture.ref('SchemaRevision', 'probe-schema'),
        riskPolicyRef=fixture.ref('RiskPolicyRevision', 'probe-risk'))
    contract = service.create_contract(scope, contract_request, 'synthetic-operator', now=at)
    assert contract.content_hash == canonical_hash({**contract_request.model_dump(mode='json', by_alias=True),
        'requiredGateTypes': REQUIRED_GATE_TYPES[kind], 'externalEffectCapable': kind.value in ('external_notice', 'repricing')})
    request = PreparePriceDispositionRequest(dispositionId='probe-' + kind.value,
        caseRef=exact(case, 'PriceCaseRevision', 'case_id'),
        contractRef=exact(contract, 'PriceDispositionContractRevision', 'contract_id'),
        targetRefs=[sku], gateRefs={k: fixture.ref(t, 'probe-' + k) for k, t in REQUIRED_GATE_TYPES[kind].items()},
        purpose='synthetic producer hash compatibility', requestedOutcome='review only')
    prepared = service.prepare(scope, request, 'synthetic-operator', now=at)
    binding = {'case': request.case_ref, 'contract': request.contract_ref, 'targets': request.target_refs,
        'gates': request.gate_refs, 'purpose': request.purpose, 'requestedOutcome': request.requested_outcome}
    assert prepared.binding_hash == canonical_hash(binding)
    wire = request.model_dump(mode='json', by_alias=True)
    json_binding = {'case': wire['caseRef'], 'contract': wire['contractRef'], 'targets': wire['targetRefs'],
        'gates': wire['gateRefs'], 'purpose': wire['purpose'], 'requestedOutcome': wire['requestedOutcome']}
    assert canonical_hash(json_binding) != prepared.binding_hash
    assert prepared.content_hash == canonical_hash({**wire, 'kind': kind, 'bindingHash': prepared.binding_hash,
                                                   'operationalBlockers': prepared.operational_blockers})
    frozen = service.freeze(scope, prepared.disposition_id, FreezePriceDispositionRequest(
        expectedVersion=1, expectedContentHash=prepared.content_hash,
        exactRefs={'case': prepared.case_ref, 'contract': prepared.contract_ref, **prepared.gate_refs}),
        'synthetic-reviewer', now=at)
    inherited = prepared.model_dump(mode='json', by_alias=True,
        exclude={'revision', 'version', 'lifecycle', 'prior_content_hash', 'content_hash', 'created_by', 'created_at'})
    assert frozen.content_hash == canonical_hash({**inherited, 'revision': 2, 'version': 2,
        'lifecycle': 'frozen', 'priorContentHash': prepared.content_hash})
    assert frozen.model_dump(mode='json', by_alias=True,
        exclude={'revision', 'version', 'lifecycle', 'prior_content_hash', 'content_hash', 'created_by', 'created_at'}) == inherited
    for row in (prepared, frozen):
        assert row.execution_allowed is False
        assert (row.provider_call_count, row.notification_send_count, row.repricing_count, row.external_effect_count) == (0, 0, 0, 0)
    prepared_rows.append(prepared); frozen_rows.append(frozen)
    records.append({'kind': kind.value, 'typedBindingDiffersFromJson': True,
        'preparedHashVerified': True, 'frozenFullPayloadHashVerified': True, 'inheritedFieldsEqual': True})

# The original SQL Store counts every stored revision, unlike the old memory test helper.
store.list_dispositions = lambda _scope: [r for revisions in store.dispositions.values() for r in revisions]
view = service.contribution_view(scope, now=at)
assert sum(view.disposition_counts.values()) == 8
assert all(v == 2 for v in view.disposition_counts.values())
# Deliberately record the earlier internal-advice disposition after the global latest repricing row.
frozen = frozen_rows[0]
receipt = fixture.ref('AdoptionReceipt', 'synthetic-adoption')
store.receipts[(*scope.key, receipt.resource_id)] = (receipt.content_hash, frozen.binding_hash)
observation_request = RecordPriceDispositionObservationRequest(
    dispositionRef=exact(frozen, 'PriceDispositionRevision', 'disposition_id'),
    receiptRef=receipt, outcome='adopted', observedAt=at)
observation = service.record_observation(scope, observation_request)
observation_hash = canonical_hash(observation_request.model_dump(mode='json', by_alias=True))
assert observation.content_hash == observation_hash
assert observation.observation_id == 'price-disposition-observation-' + observation_hash[:24]
assert 'createdAt' not in observation.model_dump(mode='json', by_alias=True)
view = service.contribution_view(scope, now=at)
assert view.latest_observation.disposition_ref.resource_id != view.latest_disposition.disposition_id
files = ['services/aos-api/aos_api/ecommerce_workshop_price_disposition.py',
         'services/aos-api/tests/aip/test_w6_06_price_disposition.py']
result = {'syntheticMemoryOnly': True, 'databaseOrHttpCalls': 0, 'productionAuthorization': False,
    'records': records, 'savedRevisionCount': 8, 'perKindSavedRevisions': 2,
    'observationHashAndDerivedIdVerified': True, 'latestObservationMayReferenceEarlierDisposition': True,
    'sourceHashes': {p: hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}, 'wholeGoalComplete': False}
target = Path(__file__).with_name('producer-probe-result-r1.json')
with target.open('x') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2); stream.flush(); os.fsync(stream.fileno())
print(json.dumps(result))
