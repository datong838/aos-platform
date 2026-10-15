"""Original customer lifecycle producer, isolated memory only; no actual consent."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
spec=importlib.util.spec_from_file_location('customer_original_fixture',R/'services/aos-api/tests/aip/test_w6_07_customer_lifecycle.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from aos_api.ecommerce_workshop_customer_lifecycle import canonical_hash
f.SCOPE=f.TenantScope('dev-org','fixture-project')
def exact(item,kind,identity_field):
    identity=getattr(item,identity_field)
    return f.CustomerExactRef(resourceType=kind,resourceId=identity,revision=item.revision,
        contentHash='sha256:'+item.content_hash,receiptId='receipt-'+identity)
f.exact=exact
store,service,policy,segment,journey,dialogue=f.authority_fixture()
request=f.batch_request(policy,segment,journey,dialogue)
prepared=service.prepare_batch(f.SCOPE,request,'synthetic-operator',now=f.NOW)
refs={'segment':request.segment_ref,'journey':request.journey_ref,'dialogue':request.dialogue_ref,
      'consentPolicy':request.consent_policy_ref,'frequencyPolicy':request.frequency_policy_ref,
      'channelCapability':request.channel_capability_ref}
hashes=[canonical_hash(item.model_dump(mode='json',by_alias=True)) for item in request.items]
assert prepared.item_hashes==hashes
assert prepared.binding_hash==canonical_hash({'refs':refs,'itemHashes':hashes})
typed_hash=canonical_hash({**request.model_dump(mode='json',by_alias=True),'ledger':prepared.ledger,'bindingHash':prepared.binding_hash})
json_hash=canonical_hash({**request.model_dump(mode='json',by_alias=True),'ledger':prepared.ledger.model_dump(mode='json',by_alias=True),'bindingHash':prepared.binding_hash})
assert typed_hash==prepared.content_hash and typed_hash!=json_hash
frozen=service.freeze_batch(f.SCOPE,prepared.batch_id,f.FreezeCustomerDialogueBatchRequest(
    expectedVersion=1,expectedContentHash=prepared.content_hash,exactRefs=refs,itemHashes=hashes),'synthetic-reviewer',now=f.NOW)
excluded={'revision','version','lifecycle','prior_content_hash','content_hash','created_by','created_at'}
inherited=prepared.model_dump(mode='json',by_alias=True,exclude=excluded)
assert frozen.model_dump(mode='json',by_alias=True,exclude=excluded)==inherited
assert frozen.content_hash==canonical_hash({**inherited,'revision':2,'version':2,'lifecycle':'frozen','priorContentHash':prepared.content_hash})
assert frozen.ledger.input==2 and frozen.ledger.eligible==frozen.ledger.unknown==1
unknown=next(item for item in frozen.items if item.disposition.value=='unknown')
assert unknown.consent_decision.value=='unknown' and unknown.retention_active is unknown.k_anonymity_satisfied is None
assert (frozen.contact_resolution_count,frozen.action_count,frozen.provider_call_count,frozen.send_count,frozen.external_effect_count)==(0,0,0,0,0)
result=dict(syntheticMemoryOnly=True,databaseOrHttpCalls=0,actualConsentAuthority=False,
    originalProducerUsed=True,fullExactRefs=True,typedLedgerHashVerified=True,jsonLedgerHashDifferent=True,
    itemHashesVerified=True,frozenFullPayloadHashVerified=True,inheritedFieldsEqual=True,
    ledger=frozen.ledger.model_dump(mode='json',by_alias=True),unknownConsentPreserved=True,fiveEffectCountsZero=True,
    sourceSha=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_workshop_customer_lifecycle.py').read_bytes()).hexdigest(),wholeGoalComplete=False)
with (E/'producer-probe-result-r1.json').open('x') as stream:
    json.dump(result,stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(result))
