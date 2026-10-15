"""Original contact producer only in memory; no real consent, contact or DB."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
spec=importlib.util.spec_from_file_location('contact_probe_fixture',R/'services/aos-api/tests/aip/test_w6_08_customer_contact.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
f.SCOPE=f.TenantScope('dev-org','fixture-project')
service,store,batch=f.service_fixture();request=f.start_request(batch)
started=service.start_batch(f.SCOPE,batch.batch_id,request,'synthetic-operator',now=f.NOW)
typed={'batchRef':started.batch_ref,'startSequence':started.start_sequence,'exactRefs':started.exact_refs,'items':started.items,'reason':request.reason}
without_reason={k:v for k,v in typed.items() if k!='reason'}
raw=started.model_dump(mode='json',by_alias=True)
assert f.canonical_hash(typed)==started.content_hash
assert f.canonical_hash(without_reason)!=started.content_hash and 'reason' not in raw
binding=started.items[0]
base={'batchRef':started.batch_ref,'item':request.items[0],'exactRefs':started.exact_refs,'startSequence':started.start_sequence}
assert binding.binding_hash==f.canonical_hash(base)
receipt=f.ref('ActionReceipt','synthetic-receipt','f')
store.receipts[(*f.SCOPE.key,receipt.resource_id)]=(receipt.content_hash,binding.binding_hash)
observation=service.record_dispatch_observation(f.SCOPE,f.RecordCustomerDispatchObservationRequest(
 startDecisionRef=f.full_ref('CustomerBatchStartDecisionRevision',started.decision_id,started.content_hash),
 itemKey=binding.item_key,actionReceiptRef=receipt,state='unknown',observedAt=f.NOW))
view=service.contribution_view(f.SCOPE,now=f.NOW)
assert view.latest_start.content_hash==started.content_hash
assert view.latest_start.items[0].state.value=='unknown' and started.items[0].state.value=='reserved'
assert view.latest_start.ledger.unknown==1 and view.latest_start.items[0].reservation.status=='held'
result=dict(syntheticMemoryOnly=True,databaseOrHttpCalls=0,originalProducerUsed=True,actualConsentOrReceiptAuthority=False,
 originalStartSignatureWithTypedItemsAndReasonVerified=True,storedModelOmitsReason=True,withoutReasonHashDifferent=True,
 bindingHashVerified=True,contributionProjectionChangesItemsWithoutChangingOriginalHash=True,originalStoredStartUnchanged=True,
 unknownPreserved=True,reservationRemainsHeld=True,originalFourEffectsZero=all(getattr(started,k)==0 for k in ['contact_resolution_count','provider_call_count','send_count','external_effect_count']),
 sourceSha=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_workshop_customer_contact.py').read_bytes()).hexdigest(),wholeGoalComplete=False)
with (E/'producer-probe-result-r1.json').open('x') as stream:
 json.dump(result,stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(result))
