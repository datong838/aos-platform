"""Unchanged original closure producer, synthetic memory resolvers only."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
spec=importlib.util.spec_from_file_location('closure_fixture',R/'services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from aos_api.ecommerce_workshop_three_module_closure import ThreeModule,canonical_hash
class Fixture(f.ProducerFixture):
    def resolve_domain_items(self,scope,module,source):
        assert module is ThreeModule.PRICE and source.resource_type=='PriceDispositionRevision'
        return [f.ThreeModuleItemOutcome(itemKey=key,originalStatus=status,canonicalOutcome=outcome,
            originalRef=source.model_copy(update={'resource_id':source.resource_id+':'+key}),
            receiptRef=f.ref('ActionReceipt','synthetic-'+key))
            for key,status,outcome in [('sku-a','applied','succeeded'),('sku-b','unknown','unknown')]]
store=Fixture();service=f.EcommerceWorkshopThreeModuleClosureService(store)
request=f.CompileThreeModuleClosureRequest(module='price',sourceRef=f.ref('PriceDispositionRevision','synthetic-price-disposition'))
closure=service.compile(f.SCOPE,request,'synthetic-actor',now=f.NOW)
payload=dict(module=closure.module,sourceRef=closure.source_ref,items=closure.items)
assert canonical_hash(payload)==closure.content_hash
assert canonical_hash(json.loads(json.dumps(payload,default=lambda v:v.model_dump(mode='json',by_alias=True) if hasattr(v,'model_dump') else str(v))))!=closure.content_hash
exact=service._ref('ThreeModuleClosureRevision',closure.closure_id,closure.content_hash)
usage=service.bind_usage(f.SCOPE,f.BindThreeModuleUsageRequest(closureRef=exact,usageReceiptId='synthetic-usage'),now=f.NOW)
effect=service.bind_effect(f.SCOPE,f.BindThreeModuleEffectRequest(closureRef=exact,effectReviewId='synthetic-effect'),now=f.NOW)
handoff=service.bind_handoff(f.SCOPE,f.BindThreeModuleHandoffRequest(closureRef=exact,handoffId='synthetic-handoff'),now=f.NOW)
assert usage.quantity is None and usage.quality==usage.settlement=='unknown'
assert effect.accepted is True and effect.maturity_status=='immature' and not effect.effect_completed
assert effect.cutoff_at>effect.observed_at
assert handoff.transport_status=='consumed' and handoff.business_decision=='request_more'
values=dict(closure=closure,usage=usage,effect=effect,handoff=handoff)
store.latest_bindings=lambda scope,module:values
view=service.contribution_view(f.SCOPE,ThreeModule.PRICE,now=f.NOW)
assert view.latest_closure.ledger.state.value=='partial'
assert view.latest_closure.ledger.succeeded==view.latest_closure.ledger.unknown==1
assert not view.external_effects_allowed and not view.handoff_consume_allowed and not view.memory_promotion_allowed
result=dict(syntheticMemoryOnly=True,databaseOrHttpCalls=0,productionAuthority=False,module='price',
    originalProducerTypedHashVerified=True,jsonDumpHashIsDifferent=True,
    itemLedger={'total':2,'succeeded':1,'unknown':1,'state':'partial'},usageQuantity=None,
    effectAccepted=True,effectCompleted=False,maturity='immature',handoffTransport='consumed',businessDecision='request_more',
    bindingIds={key:value.binding_id for key,value in values.items() if key!='closure'},
    originalServiceSha=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_workshop_three_module_closure.py').read_bytes()).hexdigest(),
    wholeGoalComplete=False)
with (E/'producer-probe-result-r1.json').open('x') as stream:
    json.dump(result,stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(result))
