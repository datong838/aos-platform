"""Independent semantic readback: signed content is not the registration DTO."""
import hashlib
import json
import sys
from pathlib import Path
import real_contract as C
sys.path.insert(0,str(C.ROOT / '.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from prepare_public_bundle_root import OUTPUT, fingerprints

previous=json.loads((C.R/'signed-media-source-result.json').read_text())
assert previous['scriptHash']==hashlib.sha256((C.R/'audit_signed_media_sources.py').read_bytes()).hexdigest()
now=fingerprints(OUTPUT)
assert len(now)==previous['filesCount']
assert hashlib.sha256(json.dumps(now,sort_keys=True).encode()).hexdigest()==previous['filesHash']
loader=T.ManifestLoader({'qyh-selected':OUTPUT},trust_roots=T.FileTrustRootProvider(T.TRUST).snapshot())
for row in previous['versions']:
    loaded=loader.load(f"bundle://qyh-selected/{row['id']}/{row['version']}")
    assert loaded.content_hash==row['contentHash'] and loaded.signature is not None
growth=OUTPUT/'solution.ecommerce.growth'/'1.13.0'
profile=json.loads((growth/'content/production-profiles/ecommerce.media-studio.json').read_text())
policy=json.loads((growth/'content/policies/growth-gates.json').read_text())
assert profile['schema']=='aos.ecommerce-production-profile/v1'
assert {'fact','brand','copyright','platform'}<=set(profile['eval']['gates'])
assert profile['eval']['sameRevisionRequired'] and profile['eval']['failClosed']
templates=[]
for p in sorted((growth/'content/media-production-templates').glob('*.json')):
    x=json.loads(p.read_text())
    templates.append({'path':str(p.relative_to(growth)),'schema':x['schema'],
        'templateId':x['templateId'],'revision':x['revision'],'profile':x['profile'],
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
assert len(templates)==6
result={'task':previous['task'],'authority':'AOS-001895',
    'originalLoaderIndependentlyVerifiedFourSignatures':True,
    'allSelectedPackageFileHashesUnchanged':True,
    'eightModuleDefinitionsAndSixMediaTemplatesPreserved':True,
    'mediaProductionProfileSchema':profile['schema'],
    'mediaEvalGateNames':profile['eval']['gates'],
    'mediaEvalRequiresSameRevisionAndFailClosed':True,
    'growthGateIds':[x.get('gate_id') for x in policy['gates']],
    'growthGateDocumentIsNotFourMediaRuleExactRefs':not all('ruleRef' in x for x in policy['gates']),
    'mediaTemplateDocuments':templates,
    'fullRegistrationRequestAbsenceNotProofOfMissingSignedPolicy':True,
    'registrationSourceSignatureRefsMustBeDerivedOutsideTheirOwnSignedBundle':True,
    'productionProfileGateNamesAloneNotCanonicalRulesOrPolicyProducer':True,
    'requiredRepair':'Bind signed policy contribution schema and canonical Rule refs to server-derived manifest/signature/policy exact refs in one original authority snapshot; preserve templates and original Eval/Issue/Return.',
    'databaseWrites':0,'registryTransitions':0,'privateKeysRead':False,
    'formalPublisherConnected':False,'fullRestorationAccepted':False,
    'auditScriptHash':previous['scriptHash'],
    'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (C.R/'signed-media-source-independent-readback.json').open('x') as stream:
    stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'independentFourSignatures':True,'templates':len(templates),
    'signedMediaGateNames':profile['eval']['gates'],'registrationPayloadAbsenceIsNotMissingPolicyProof':True}))
