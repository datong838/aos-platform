"""Same-HEAD isolated candidate qualification and read-only signing preflight."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import build_ecommerce_qyh_successor_candidates as profile
import validate_ecommerce_qyh_successor_signing as signing
OUTPUT=profile.DEFAULT_OUTPUT
assert not OUTPUT.exists() and not (D/'build-receipt.json').exists(), 'reconcile existing outcomes first'
b=profile.load_builder();before={str(p):b._tree_hash(p) for p in (b.CANDIDATE_ROOT).glob('*/*')}
r=b.build(context='colima-aos-extension',port=18439,output=OUTPUT,retain_artifacts=True)
(D/'build-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
assert not list(OUTPUT.rglob('bundle.signature.json'))
assert r['contentHashes']['solution.ecommerce.operations-base']=='sha256:ca0f6e74bcb428efd78c868285cd9fbed136919d4676b46aee9e181e8eec33ec'
(D/'qualification-intent.json').write_text(json.dumps({'sourceHead':r['gitHead'],'buildTreeHash':r['outputTreeHash'],'ephemeralTestSignatureOnly':True,'formalPublishingAuthority':False})+'\n')
q=b.qualify(output=OUTPUT,build_receipt=D/'build-receipt.json',context='colima-aos-extension')
(D/'qualification-receipt.json').write_text(json.dumps(q,indent=2)+'\n')
state=ROOT.parent/'aos-recovery/qyh-successor-not-created-signing-state-20261012'
assert not state.exists()
v=signing.validate_inputs(build=OUTPUT,build_receipt=D/'build-receipt.json',qualification_receipt=D/'qualification-receipt.json',state=state)
assert not state.exists() and not list(OUTPUT.rglob('bundle.signature.json'))
assert all(b._tree_hash(Path(k))==v for k,v in before.items())
(D/'validation.json').write_text(json.dumps(v,indent=2)+'\n')
print('actual full4 sameHEAD Build/isolated qualification/read-only sign-input preflight PASS; no persisted key or formal signature')
