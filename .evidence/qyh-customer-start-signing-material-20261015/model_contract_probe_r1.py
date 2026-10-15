"""Design spike in a separate model only, no product edits or DB/HTTP."""
from pathlib import Path
import importlib.util
import json
import os
import sys
from pydantic import create_model, Field
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.ecommerce_workshop_customer_contact import CustomerBatchStartDecisionRevision
from aos_api.public_contracts import redact_sensitive
spec=importlib.util.spec_from_file_location('signing_contract_probe_fixture',R/'services/aos-api/tests/aip/test_w6_08_customer_contact.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
f.SCOPE=f.TenantScope('dev-org','fixture-project');service,store,batch=f.service_fixture();request=f.start_request(batch)
original=service.start_batch(f.SCOPE,batch.batch_id,request,'synthetic-operator',now=f.NOW)
Prototype=create_model('PrivateReasonPrototype',__base__=CustomerBatchStartDecisionRevision,
 reason=(str|None,Field(default=None,min_length=1,max_length=500,exclude=True,repr=False)))
legacy=original.model_dump(mode='json',by_alias=True)
candidate=Prototype.model_validate({**legacy,'reason':request.reason})
assert candidate.model_dump(mode='json',by_alias=True)==legacy
assert 'reason' not in Prototype.model_json_schema(mode='serialization')['properties']
assert 'reason' in Prototype.model_json_schema(mode='validation')['properties']
assert request.reason not in repr(candidate) and Prototype.model_validate(legacy).reason is None
authority={**candidate.model_dump(mode='json',by_alias=True),'reason':candidate.reason}
roundtrip=Prototype.model_validate(authority)
expected=f.canonical_hash(dict(batchRef=roundtrip.batch_ref,startSequence=roundtrip.start_sequence,exactRefs=roundtrip.exact_refs,items=roundtrip.items,reason=roundtrip.reason))
assert expected==original.content_hash and roundtrip.model_dump(mode='json',by_alias=True)==legacy
assert redact_sensitive('fixture@example.test')!='fixture@example.test' and redact_sensitive(request.reason)==request.reason
result=dict(designPrototypeOnly=True,productCodeChanged=False,databaseOrHttpCalls=0,
 publicWireExactlyEqual=True,serializationSchemaOmitsReason=True,validationSchemaAcceptsPrivateReason=True,
 reprOmitsReason=True,legacyWithoutReasonStillDecodes=True,privateRoundtripRebuildsOriginalHash=True,
 originalSensitiveValueRedactorAvailable=True,actualStoreImplementationNotClaimed=True,wholeGoalComplete=False)
with (E/'model-contract-probe-result-r1.json').open('x') as stream:
 json.dump(result,stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(result))
