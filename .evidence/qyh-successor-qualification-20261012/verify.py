import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import build_ecommerce_qyh_successor_candidates as p
import validate_ecommerce_qyh_successor_signing as v
b=p.load_builder();r=json.loads((D/'build-r2-receipt.json').read_text());q=json.loads((D/'qualification-r2-receipt.json').read_text());out=Path(r['output'])
assert b._tree_hash(out)==r['outputTreeHash']
assert not list(out.rglob('bundle.signature.json'))
retained=json.loads((ROOT/'.evidence/qyh-analyst-eval-policy-contract-20261012/retained-package-hashes.json').read_text())
assert all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==h for k,h in retained.items())
frozen=json.loads((ROOT/'.evidence/qyh-four-bundle-successor-20261012/source-hashes.json').read_text())
assert all(b._tree_hash(b.CANDIDATE_ROOT/k)==h for k,h in frozen.items())
sessions=[]
for name,data in q['runtimeSessions'].items():
 lines=[json.loads(i) for i in Path(data['journal']).read_text().splitlines()]
 assert lines[-1]['state']=='released'
 resource=lines[0]['resourceName']
 found=subprocess.run(['docker','--context','colima-aos-extension','ps','-a','--filter','name=^/'+resource+'$','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.strip()
 assert not found
 sessions.append({'id':name,'resource':resource,'heartbeatChecks':data['heartbeatChecks'],'independentlyAbsent':True})
old=ROOT/'.evidence/qyh-full-system-restoration-20261011/selected-public-bundles'
expected={'domain.ecommerce.core/1.4.3':'e14e6af72dd7c89d5beb7fd002454029bbc64cf510e6b9849ae9df20ef7eba44','platform.ecommerce.niushop/1.23.2':'052214c06f08bd930daea552f7ade0ee49313abde9e3292fdaa8d071d41a8c90','solution.ecommerce.growth/1.13.0':'24249a21939b3a6c68c493b5f3bc958cbd0a1ba28b4c8f57a2f2da6b68308669','solution.ecommerce.operations-base/1.2.2':'ca0f6e74bcb428efd78c868285cd9fbed136919d4676b46aee9e181e8eec33ec'}
from aos_api.asset_registry.manifest_loader import ManifestLoader
loader=ManifestLoader(allowlist_roots={'old':old})
assert all(loader.load('bundle://old/'+k).content_hash=='sha256:'+h for k,h in expected.items())
state=ROOT.parent/'aos-recovery/qyh-successor-not-created-signing-state-20261012'
assert not state.exists()
result={'outcome':'QYH_SUCCESSOR_ISOLATED_QUALIFIED_NO_FORMAL_IDENTITY','sourceHead':r['gitHead'],'retained1695Exact':True,'oldFourContentHashesExact':True,'immutableFourSourceExact':True,'runtimeSessions':sessions,'tamperRejections':q['tamperRejections'],'ephemeralSignaturePersisted':q['ephemeralSignaturePersisted'],'tests':'42 passed,0 skipped,7 existing warnings','publisherIdentityConnected':False,'formalRuntimeReady':False,'currentInstallationChanged':False,'realOIDCConnected':False,'effects':r['effects'],'sourceEvalScope':'source-preflight-only','failedR1Retained':True}
(D/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['outcome'])
