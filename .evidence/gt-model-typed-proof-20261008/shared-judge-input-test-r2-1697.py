"""Real crypto over synthetic facts; never a transport or native authority test."""
from pathlib import Path
from datetime import datetime,timedelta
import copy,json,hashlib,base64
import pytest
from aos_api import aip_model_eval_execution_contracts as m
from aos_api.aip_model_runtime_store import canonical_hash
from shared_certificate_fixture_1673 import keys_for_manifest,issue

@pytest.fixture
def chain(request):
 B=Path(__file__).resolve().parents[1]
 d=json.loads((B/'gt-atomic-model-admission-20261008/shared-risk-description-native-1672-r6/native-description-proof.json').read_text())['description']
 d=copy.deepcopy(d)
 mode=getattr(request,'param','present')
 expected=None if mode=='absent' else (b'' if mode=='empty' else (b'x'*800000 if mode=='large' else '  synthetic expected 🙂\n'.encode()))
 manifest=d['immutable']['manifest']
 for case,original in zip(manifest['cases'],manifest['judgeRequest']['cases']):
  digest=None if expected is None else hashlib.sha256(expected).hexdigest()
  case['expectedHash']=digest
  if expected is None:original['expectedArtifact']=None
  else:original['expectedArtifact']['contentHash']=digest
 manifest['judgeRequest']['caseSetHash']=canonical_hash(manifest['judgeRequest']['cases'])
 manifest['judgeRequestHash']=canonical_hash(manifest['judgeRequest'])
 manifest['judgeParentBudget']['requestHash']=manifest['judgeRequestHash']
 manifest['caseSetHash']=canonical_hash([dict(caseId=c['caseId'],inputHash=c['inputHash'],expectedHash=c['expectedHash']) for c in manifest['cases']])
 keys=keys_for_manifest(d['immutable']['manifest']);d['immutable']['manifestHash']=canonical_hash(d['immutable']['manifest']);d['contentHash']='sha256:'+canonical_hash(d['immutable'])
 t=datetime.fromisoformat(d['immutable']['manifest']['judgeRequest']['expiresAt'])-timedelta(seconds=10);proof=issue(d,keys,t)
 proof['certificates']=[m.ModelSharedParentRiskSignedCertificateEnvelope.model_validate(e).model_dump(mode='json',by_alias=True) for e in proof['certificates']]
 pairs=[]
 for ordinal,case in enumerate(d['immutable']['manifest']['cases']):
  envelopes=[];wires=[];outputs=[];certs=proof['certificates'][ordinal*2:ordinal*2+2]
  for purpose,cert in zip(('target',),certs):
   wire=('  wire '+purpose+case['caseId']+'🙂\n').encode();out=('  output '+purpose+case['caseId']+'🙂\n').encode()
   claim={k:copy.deepcopy(v) for k,v in cert['certificate'].items() if k not in ('issuerId','issuerKeyId','publicKeyBase64','validFrom','validUntil')}
   claim.update(schemaVersion='aos.model-eval-shared-parent-case-signing-input/v3',caseInputHash=case['inputHash'],inputHash=hashlib.sha256(wire).hexdigest(),outputHash=hashlib.sha256(out).hexdigest(),occurredAt=t.isoformat())
   if purpose=='judge':claim.update(targetClaimHash=canonical_hash(envelopes[0]),actualHash=envelopes[0]['payload']['claim']['outputHash'],expectedHash=case['expectedHash'],passed=True,detailCode='synthetic-test-only')
   payload=dict(schemaVersion='aos.model-eval-shared-parent-case-signature-payload/v3',certificateHash=canonical_hash(cert),claim=claim)
   raw=m.canonical_shared_parent_signed_case_bytes(d,payload,input_bytes=wire,output_bytes=out,target_envelope=None if purpose=='target' else envelopes[0])
   envelope=dict(schemaVersion='aos.model-eval-shared-parent-signed-case-envelope/v3',payload=payload,signatureBase64=base64.b64encode(keys[purpose].sign(raw)).decode())
   envelope=m.ModelSharedParentRiskSignedCaseEnvelope.model_validate(envelope).model_dump(mode='json',by_alias=True)
   envelopes.append(envelope);wires.append(wire);outputs.append(out)
  pairs.append(dict(envelopes=envelopes,wires=wires,outputs=outputs,certs=certs))
 return d,proof,t,keys,pairs,expected

def args(chain,index=0):
 d,p,t,keys,pairs,expected=chain;x=pairs[index]
 return dict(certificate_envelope=x['certs'][0],issuer_input=p['presented_root'],checked_at=t,
   revoked_identity_ids=frozenset(),target_input_bytes=x['wires'][0],
   target_output_bytes=x['outputs'][0],expected_output=expected)

def build(chain,index=0,**change):
 d,p,t,keys,pairs,expected=chain;a=args(chain,index);a.update(change)
 return m.build_shared_parent_target_judge_input(d,pairs[index]['envelopes'][0],**a)

@pytest.mark.parametrize('chain',['present','absent','empty'],indirect=True)
def test_exact_judge_input_preserves_target_and_expected_raw_bytes(chain):
 d,p,t,keys,pairs,expected=chain
 for i,x in enumerate(pairs):
  raw=build(chain,i);doc=json.loads(raw)
  assert doc['schemaVersion']=='aos.model-eval-shared-parent-target-judge-input/v3'
  assert doc['executionAllowed'] is False
  assert doc['descriptionHash']==d['contentHash'] and doc['manifestHash']==d['immutable']['manifestHash']
  assert doc['originalRiskHash']==d['immutable']['originalRiskHash']
  assert (doc['callerXid'],doc['callerPid'])==(d['immutable']['callerXid'],d['immutable']['callerPid'])
  assert doc['judgeRequestHash']==d['immutable']['manifest']['judgeRequestHash']
  assert doc['judgeLeg']==d['immutable']['manifest']['cases'][i]['judge']
  assert doc['targetCaseHash']==canonical_hash(x['envelopes'][0])
  assert doc['targetCertificateHash']==x['envelopes'][0]['payload']['certificateHash']
  assert base64.b64decode(doc['actualBase64'])==x['outputs'][0]
  assert doc['actualHash']==hashlib.sha256(x['outputs'][0]).hexdigest()
  assert (None if doc['expectedBase64'] is None else base64.b64decode(doc['expectedBase64']))==expected
  assert m.validate_shared_parent_target_judge_input(d,x['envelopes'][0],judge_input_bytes=raw,**args(chain,i)) is None
  assert raw==build(chain,i)

@pytest.mark.parametrize('fault',['signature','certificate','root','expired','revoked','actual','wire','expected','mutable_expected','missing_expected','oversize_expected','borrowed_case'])
def test_builder_rejects_unbound_target_or_expected(chain,fault):
 original_d,original_p,t,keys,original_pairs,expected=chain;d=copy.deepcopy(original_d);p=copy.deepcopy(original_p);pairs=copy.deepcopy(original_pairs);local=(d,p,t,keys,pairs,expected);a=args(local)
 if fault=='signature':pairs[0]['envelopes'][0]['signatureBase64']=base64.b64encode(b'0'*64).decode()
 elif fault=='certificate':a['certificate_envelope']=pairs[0]['certs'][1]
 elif fault=='root':a['issuer_input']['publicKeyBase64']=base64.b64encode(b'0'*32).decode()
 elif fault=='expired':a['checked_at']=t+timedelta(seconds=20)
 elif fault=='revoked':a['revoked_identity_ids']=frozenset([pairs[0]['envelopes'][0]['payload']['claim']['leg']['identityId']])
 elif fault=='actual':a['target_output_bytes']+=b' '
 elif fault=='wire':a['target_input_bytes']+=b' '
 elif fault=='expected':a['expected_output']+=b' '
 elif fault=='mutable_expected':a['expected_output']=bytearray(expected)
 elif fault=='missing_expected':a['expected_output']=None
 elif fault=='oversize_expected':a['expected_output']=b'x'*1048577
 else:a['certificate_envelope']=pairs[1]['certs'][0]
 with pytest.raises(ValueError):m.build_shared_parent_target_judge_input(d,pairs[0]['envelopes'][0],**a)

@pytest.mark.parametrize('fault',['reordered','actual','expected','case','extra','missing','allowed','mutable','oversize','empty'])
def test_exact_wire_consumer_rejects_resigned_or_semantic_aliases(chain,fault):
 d,p,t,keys,pairs,expected=chain;raw=build(chain);doc=json.loads(raw)
 if fault=='reordered':bad=json.dumps(doc,ensure_ascii=False,indent=2).encode()
 elif fault=='mutable':bad=bytearray(raw)
 elif fault=='oversize':bad=b'x'*1048577
 elif fault=='empty':bad=b''
 else:
  if fault=='actual':doc['actualBase64']=base64.b64encode(b'other').decode()
  elif fault=='expected':doc['expectedBase64']=base64.b64encode(b'other').decode()
  elif fault=='case':doc['caseId']='other'
  elif fault=='extra':doc['unbound']='value'
  elif fault=='missing':del doc['targetCaseHash']
  else:doc['executionAllowed']=True
  bad=json.dumps(doc,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
 with pytest.raises(ValueError):m.validate_shared_parent_target_judge_input(d,pairs[0]['envelopes'][0],judge_input_bytes=bad,**args(chain))

@pytest.mark.parametrize('chain',['absent'],indirect=True)
def test_absent_expected_ref_rejects_present_bytes(chain):
 with pytest.raises(ValueError,match='absent'):build(chain,expected_output=b'')

@pytest.mark.parametrize('chain',['large'],indirect=True)
def test_serialized_wire_bound_includes_base64_and_full_binding(chain):
 with pytest.raises(ValueError,match='wire bound'):build(chain)
