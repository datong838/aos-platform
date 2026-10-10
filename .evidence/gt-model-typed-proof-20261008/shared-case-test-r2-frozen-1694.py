"""Real crypto over synthetic facts; never a transport or native authority test."""
from pathlib import Path
from datetime import datetime,timedelta
import copy,json,hashlib,base64
import pytest
from aos_api import aip_model_eval_execution_contracts as m
from aos_api.aip_model_runtime_store import canonical_hash
from shared_certificate_fixture_1673 import keys_for_manifest,issue

@pytest.fixture
def chain():
 B=Path(__file__).resolve().parents[1]
 d=json.loads((B/'gt-atomic-model-admission-20261008/shared-risk-description-native-1672-r6/native-description-proof.json').read_text())['description']
 d=copy.deepcopy(d);keys=keys_for_manifest(d['immutable']['manifest']);d['immutable']['manifestHash']=canonical_hash(d['immutable']['manifest']);d['contentHash']='sha256:'+canonical_hash(d['immutable'])
 t=datetime.fromisoformat(d['immutable']['manifest']['judgeRequest']['expiresAt'])-timedelta(seconds=10);proof=issue(d,keys,t)
 pairs=[]
 for ordinal,case in enumerate(d['immutable']['manifest']['cases']):
  envelopes=[];wires=[];outputs=[];certs=proof['certificates'][ordinal*2:ordinal*2+2]
  for purpose,cert in zip(('target','judge'),certs):
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
 return d,proof,t,keys,pairs

def verify(chain,index=0,purpose='judge',**change):
 d,p,t,keys,pairs=chain;x=copy.deepcopy(pairs[index]);n=0 if purpose=='target' else 1
 args=dict(certificate_envelope=x['certs'][n],issuer_input=p['presented_root'],checked_at=t,revoked_identity_ids=frozenset(),input_bytes=x['wires'][n],output_bytes=x['outputs'][n])
 if n:args.update(target_envelope=x['envelopes'][0],target_certificate_envelope=x['certs'][0],target_issuer_input=p['presented_root'],target_input_bytes=x['wires'][0],target_output_bytes=x['outputs'][0])
 args.update(change);return m.validate_shared_parent_case_signature(d,x['envelopes'][n],**args)

def test_four_independent_real_case_signatures_and_old_domain_denial(chain):
 d,p,t,keys,pairs=chain
 assert not p['execution_allowed'] and keys['target']!=keys['judge']
 for i,x in enumerate(pairs):
  assert verify(chain,i,'target') is None
  assert verify(chain,i,'judge') is None
  for n,e in enumerate(x['envelopes']):
   raw=m.canonical_shared_parent_signed_case_bytes(d,e['payload'],input_bytes=x['wires'][n],output_bytes=x['outputs'][n],target_envelope=None if n==0 else x['envelopes'][0])
   assert raw.startswith(b'AOS-MODEL-EVAL-SHARED-PARENT-SIGNED-CASE-v3\n')
   for old in (m.canonical_model_signed_case_bytes,m.canonical_original_target_signed_case_bytes):
    with pytest.raises(ValueError):old(d['immutable']['manifest'],e['payload'],input_bytes=x['wires'][n],output_bytes=x['outputs'][n])

@pytest.mark.parametrize('purpose',['target','judge'])
@pytest.mark.parametrize('field',['descriptionHash','originalRiskHash','callerXid','callerPid','manifestHash','requestHash','caseInputHash','candidateRef','leg','inputHash','outputHash'])
def test_full_case_origin_and_wire_binding(chain,purpose,field):
 d,p,t,keys,pairs=chain;n=0 if purpose=='target' else 1;e=copy.deepcopy(pairs[0]['envelopes'][n]);claim=e['payload']['claim']
 if field.endswith('Hash'):claim[field]=('sha256:' if field in ('descriptionHash','originalRiskHash') else '')+'f'*64
 elif field=='callerPid':claim[field]+=1
 elif field=='callerXid':claim[field]=str(int(claim[field])+1)
 elif field=='candidateRef':claim[field]['assetId']+='-wrong'
 else:claim[field]['intentRef']['resourceId']+='-wrong'
 with pytest.raises(ValueError):m.canonical_shared_parent_signed_case_bytes(d,e['payload'],input_bytes=pairs[0]['wires'][n],output_bytes=pairs[0]['outputs'][n],target_envelope=None if n==0 else pairs[0]['envelopes'][0])

@pytest.mark.parametrize('fault',['signature','certificate','target_signature','target_certificate','target_output','target_input','target_missing','borrowed_case','expired','root_key','revoked_target','revoked_judge','mutable_revocations','actual_output','mutable_input'])
def test_judge_independently_rejects_forged_or_unavailable_target(chain,fault):
 d,p,t,keys,pairs=chain;x=pairs[0];change={}
 if fault=='signature':x['envelopes'][1]['signatureBase64']=base64.b64encode(bytes(64)).decode()
 elif fault=='certificate':x['envelopes'][1]['payload']['certificateHash']='f'*64
 elif fault=='target_signature':
  x['envelopes'][0]['signatureBase64']=base64.b64encode(bytes(64)).decode();x['envelopes'][1]['payload']['claim']['targetClaimHash']=canonical_hash(x['envelopes'][0])
  raw=m.canonical_shared_parent_signed_case_bytes(d,x['envelopes'][1]['payload'],input_bytes=x['wires'][1],output_bytes=x['outputs'][1],target_envelope=x['envelopes'][0]);x['envelopes'][1]['signatureBase64']=base64.b64encode(keys['judge'].sign(raw)).decode()
 elif fault=='target_certificate':change['target_certificate_envelope']=pairs[1]['certs'][0]
 elif fault=='target_output':change['target_output_bytes']=x['outputs'][0]+b' '
 elif fault=='target_input':change['target_input_bytes']=x['wires'][0]+b' '
 elif fault=='target_missing':change['target_envelope']=None
 elif fault=='borrowed_case':change.update(target_envelope=pairs[1]['envelopes'][0],target_certificate_envelope=pairs[1]['certs'][0],target_input_bytes=pairs[1]['wires'][0],target_output_bytes=pairs[1]['outputs'][0])
 elif fault=='expired':change['checked_at']=datetime.fromisoformat(x['certs'][1]['certificate']['validUntil'])
 elif fault=='root_key':p['presented_root']['publicKeyBase64']=base64.b64encode(bytes(32)).decode()
 elif fault.startswith('revoked_'):change['revoked_identity_ids']=frozenset([x['certs'][0 if fault=='revoked_target' else 1]['certificate']['leg']['identityId']])
 elif fault=='mutable_revocations':change['revoked_identity_ids']=set()
 elif fault=='actual_output':change['output_bytes']=x['outputs'][1]+b' '
 else:change['input_bytes']=bytearray(x['wires'][1])
 with pytest.raises(ValueError):verify(chain,**change)

@pytest.mark.parametrize('field',['targetClaimHash','actualHash','expectedHash'])
def test_judge_target_binding_even_with_own_valid_signature(chain,field):
 d,p,t,keys,pairs=chain;x=pairs[0];x['envelopes'][1]['payload']['claim'][field]='f'*64
 with pytest.raises(ValueError):m.canonical_shared_parent_signed_case_bytes(d,x['envelopes'][1]['payload'],input_bytes=x['wires'][1],output_bytes=x['outputs'][1],target_envelope=x['envelopes'][0])
