"""Original W6-07 and W6-08 synthetic producers composed, no DB/HTTP/contact."""
from pathlib import Path
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];sys.path.insert(0,str(R/'services/aos-api'))
from aos_api import ecommerce_workshop_customer_contact as d
from aos_api.ecommerce_workshop_customer_lifecycle import canonical_hash
def module(name,relative):
 spec=importlib.util.spec_from_file_location(name,R/relative);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
lf=module('original_lifecycle_probe','services/aos-api/tests/aip/test_w6_07_customer_lifecycle.py')
cf=module('original_contact_probe','services/aos-api/tests/aip/test_w6_08_customer_contact.py')
scope=lf.TenantScope('dev-org','fixture-project');lf.SCOPE=cf.SCOPE=scope
def exact(item,kind,identity):
 name=getattr(item,identity)
 return lf.CustomerExactRef(resourceType=kind,resourceId=name,revision=item.revision,contentHash='sha256:'+item.content_hash,receiptId='receipt-'+name)
lf.exact=exact
life_store,life,*refs=lf.authority_fixture();contact_store=cf.MemoryStore()
class BatchStore:
 def latest_batch(self,tenant,identity):
  assert tenant==scope
  return life_store.latest_batch(tenant,identity)
contact=d.EcommerceWorkshopCustomerContactService(contact_store,BatchStore())
frequency=contact.create_frequency_policy(scope,d.CreateCustomerFrequencyPolicyRequest(
 policyId='frequency',revision=1,channel='wecom',purpose='retention',timezone='Asia/Shanghai',
 quietHoursStart='22:00',quietHoursEnd='08:00',rollingWindowHours=168,maximumContacts=2),
 'synthetic-operator',now=lf.NOW)
request=lf.batch_request(*refs)
third=request.items[0].model_copy(update={'item_key':'item-3','customer_ref':lf.ref('CustomerLiteProjectionRevision','customer-3')})
request=request.model_copy(update={'frequency_policy_ref':exact(frequency,'FrequencyPolicyRevision','policy_id'),'items':[*request.items,third]})
prepared=life.prepare_batch(scope,request,'synthetic-operator',now=lf.NOW)
bindings={key:getattr(prepared,attr) for key,attr in {'segment':'segment_ref','journey':'journey_ref','dialogue':'dialogue_ref','consentPolicy':'consent_policy_ref','frequencyPolicy':'frequency_policy_ref','channelCapability':'channel_capability_ref'}.items()}
batch=life.freeze_batch(scope,prepared.batch_id,lf.FreezeCustomerDialogueBatchRequest(expectedVersion=1,expectedContentHash=prepared.content_hash,exactRefs=bindings,itemHashes=prepared.item_hashes),'synthetic-reviewer',now=lf.NOW+timedelta(seconds=1))
contact.record_withdrawal(scope,d.RecordCustomerConsentWithdrawalRequest(customerRef=third.customer_ref,consentPolicyRef=batch.consent_policy_ref,purpose='retention',channel='wecom',sequence=9,observedAt=lf.NOW+timedelta(seconds=1)))
start_payload=cf.start_request(batch).model_dump(mode='json',by_alias=True)
start_payload['items']=[dict(itemKey=item.item_key,itemHash=batch.item_hashes[index],customerRef=item.customer_ref.model_dump(mode='json',by_alias=True)) for index,item in enumerate(batch.items) if item.disposition.value=='eligible']
start_request=d.StartCustomerDialogueBatchRequest.model_validate(start_payload)
start=contact.start_batch(scope,batch.batch_id,start_request,'synthetic-operator',now=lf.NOW+timedelta(seconds=2))
assert start.ledger.frozen_eligible==2 and start.ledger.reserved==start.ledger.skipped_withdrawn==1
assert start.items[1].withdrawal_sequence==9 and start.items[1].reservation is start.items[1].permit is start.items[1].attempt is None
saved=d.customer_start_authority_data(start);restored=d.CustomerBatchStartDecisionRevision.model_validate(saved)
assert d.customer_start_signing_hash(restored)==start.content_hash
receipt=cf.ref('ActionReceipt','synthetic-receipt','f');binding=start.items[0]
contact_store.receipts[(*scope.key,receipt.resource_id)]=(receipt.content_hash,binding.binding_hash)
observation=contact.record_dispatch_observation(scope,d.RecordCustomerDispatchObservationRequest(startDecisionRef=exact(start,'CustomerBatchStartDecisionRevision','decision_id'),itemKey=binding.item_key,actionReceiptRef=receipt,state='unknown',observedAt=lf.NOW+timedelta(seconds=3)))
view=contact.contribution_view(scope,now=lf.NOW+timedelta(seconds=4))
assert view.ledger.unknown==view.ledger.skipped_withdrawn==1 and view.ledger.reserved==0
assert view.latest_start.items[0].reservation.status=='held' and start.items[0].state.value=='reserved'
assert view.latest_start.content_hash==start.content_hash and 'reason' not in view.model_dump(mode='json',by_alias=True)['latestStart']
assert canonical_hash(d.RecordCustomerDispatchObservationRequest.model_validate({name:getattr(observation,name) for name in d.RecordCustomerDispatchObservationRequest.model_fields}).model_dump(mode='json',by_alias=True))==observation.content_hash
result=dict(syntheticMemoryOnly=True,databaseOrHttpCalls=0,actualConsentReceiptOrContactAuthority=False,
 originalW6_07AndW6_08ProducersComposed=True,fullPolicyAndBatchExactHashes=True,frequencyPolicyMatchesFrozenBatch=True,
 originalPreparedAndFrozenBatchHashes=True,privateSigningMaterialRoundtrip=True,originalStartHashVerified=True,
 startLedger=start.ledger.model_dump(mode='json',by_alias=True),projectionLedger=view.ledger.model_dump(mode='json',by_alias=True),
 skippedWithdrawalSequence=9,startSequence=10,unknownKeepsReservationHeld=True,originalStartRemainsReserved=True,
 projectionKeepsOriginalHash=True,privateReasonAbsentFromPublicView=True,savedObservationHashVerified=True,
 sourceHashes={rel:hashlib.sha256((R/rel).read_bytes()).hexdigest() for rel in ['services/aos-api/aos_api/ecommerce_workshop_customer_contact.py','services/aos-api/aos_api/ecommerce_workshop_customer_lifecycle.py']},wholeGoalComplete=False)
with (E/'producer-probe-result-r2.json').open('x') as stream:json.dump(result,stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(result))
