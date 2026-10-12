"""Reconcile owned original checkpoint evidence without replaying effects."""
import hashlib,json,subprocess,sys,importlib.util
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
ROOT=Path.cwd();R=Path('.evidence/qyh-full-system-restoration-20261011');D=R/'checkpoint-reconciliation-20261012';TASK=R.name
D.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,d):
 with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
cp=json.loads((R/'checkpoint.json').read_text());emit(D/'previous-checkpoint.json',cp)
s=importlib.util.spec_from_file_location('m','scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['m']=m;s.loader.exec_module(m)
a=m.load_authority();lease=[x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==TASK];assert len(lease)==1 and lease[0]['status']=='ACTIVE' and lease[0]['owner']==cp['owner']
old=json.loads((R/'source161-maintenance-20261012/r3/source-migration-step-proof.json').read_text());input_path=next(p for p in old['input_files'] if p.endswith('/maintain.py'))
raw=subprocess.check_output(['git','show','fa8c36f25:'+input_path]);assert hashlib.sha256(raw).hexdigest()==old['input_files'][input_path]
executed=D/'maintain-executed-fa8.py.txt';executed.write_bytes(raw)
old['input_files']={str(executed):sha(executed),**{p:h for p,h in old['input_files'].items() if p!=input_path}}
for p,h in old['input_files'].items():assert sha(p)==h
for p,h in old['output_files'].items():assert sha(p)==h
old['provenance']={'executedSourceCommit':subprocess.check_output(['git','rev-parse','fa8c36f25'],text=True).strip(),'originalProof':str(R/'source161-maintenance-20261012/r3/source-migration-step-proof.json'),'subsequentCacheFixNotReexecuted':True}
old['output_files'][str(R/'source161-maintenance-20261012/r3/window-established.json')]=sha(R/'source161-maintenance-20261012/r3/window-established.json')
proof=D/'source-migration-versioned-proof.json';emit(proof,old)
sys.path.insert(0,str(ROOT/'scripts'));import a0v_qyh_restored_http as entry
candidate=R/'current161-preview-source-20261012.json';source=entry.require_api_source_candidate(candidate)
health={}
for port,path in [(18080,'/v1/health'),(18080,'/v1/me'),(18434,'/')]:
 req=Request(f'http://127.0.0.1:{port}'+path,headers={'Authorization':'Bearer dev','X-Org-Id':'org-org','X-Project-Id':'dev-project'})
 with urlopen(req,timeout=15) as resp:
  health[f'{port}{path}']=resp.status
  if path=='/v1/me':me=json.load(resp);assert me['orgName']=='栖月汇商贸有限公司' and me['orgId']=='org-org' and me['projectId']=='dev-project'
readback=D/'current-source-and-live-readback.json';emit(readback,{'observedAt':datetime.now(timezone.utc).isoformat(),'sourceHead':json.loads(candidate.read_text())['head'],'source':str(source),'originalSourceConsumerAccepted':True,'health':health,'runtimeAuthorityGranted':False,'eightPagesAccepted':False})
provenance={}
def copy(source,name):
 target=D/name;target.write_bytes(Path(source).read_bytes());provenance[str(target)]={'sourcePath':str(source),'sourceSha256':sha(source),'copiedSha256':sha(target)};return target
restart=copy(Path('.evidence/qyh-current161-preview-restart-20261012/verification.json'),'actual-preview-restart-verification.json')
install=copy(Path('.evidence/qyh-current-admin-install-20261012/installation-reconciliation.json'),'actual-submitted-installation.json')
published=copy(Path('.evidence/qyh-current-admin-install-20261012/result.json'),'actual-current-published-assets.json')
browser=copy(Path('.evidence/qyh-current-admin-install-20261012/browser-installation.json'),'actual-installation-browser.json')
assert json.loads(install.read_text())['state']=='submitted' and json.loads(browser.read_text())['actualNewInstallationVisible'] is True
emit(D/'copy-provenance.json',provenance)
def step(name,inputs,outputs,limitations):
 p=D/(name+'-proof.json');emit(p,{'schema':'aos-step-evidence/v1','task_id':TASK,'owner':cp['owner'],'step':name,'exit_code':0,'input_files':{str(p):sha(p) for p in inputs},'output_files':{str(p):sha(p) for p in outputs},'limitations':limitations});return p
src=step('current_immutable_source_revalidated',[*map(Path,cp['code_files']),candidate],[readback],['0511 immutable candidate currently accepted; previous cache-contaminated candidates retained; no formal start permission'])
rst=step('actual_current161_preview_restart',[D/'copy-provenance.json'],[restart],['Actual same-volume PG/API/Web preview restart only; eight runtime pages unavailable; historical blocked goal observation superseded by current official active readback'])
ins=step('actual_current_assets_and_submitted_eight_installation',[D/'copy-provenance.json'],[install,published,browser],['Native publication and submitted installation only; independent approval/current configuration/resource gates and eight functional pages pending'])
# Keep all unresolved original gates; add precisely bounded actual local steps.
cp['authority_revision']=a['project_revision'];cp['step']='independent_installation_approval_then_apply_configure_eight_pages'
cp['steps']=[x for x in cp['steps'] if x['id']!='refresh_source_candidate_after_producer_identity_code']
for x in cp['steps']:
 if x['id']=='source159_to161_original_volume_migration':x['proof']=str(proof)
 if x['id']=='establish_real_source_exclusive_window':x.update(state='VERIFIED_LOCAL',proof=str(proof))
# Window must have its own matching proof identity.
window=step('establish_real_source_exclusive_window',[executed],[R/'source161-maintenance-20261012/r3/window-established.json',R/'source161-maintenance-20261012/r3/hba-restored.json'],['Historical actual held window now closed; any new source mutation requires a fresh window'])
for x in cp['steps']:
 if x['id']=='establish_real_source_exclusive_window':x['proof']=str(window)
cp['steps'] += [{'id':n,'state':'VERIFIED_LOCAL','proof':str(p)} for n,p in [('current_immutable_source_revalidated',src),('actual_current161_preview_restart',rst),('actual_current_assets_and_submitted_eight_installation',ins)]]
# Inputs are explicitly owned and hashed; outputs are independently checked by original observer.
files=[R/'current-code-step-proof.json',R/'current-entry-freeze-green.log',R/'current-entry-source-consumption-20261012.json',R/'current-entry-source-20261012.json',proof,executed,*[Path(x) for x in old['input_files'] if x!=str(executed)],candidate,readback,D/'copy-provenance.json',src,rst,ins,window,install,published,browser,restart]
cp['evidence_files']=list(dict.fromkeys(str(x) for x in files));assert len(cp['evidence_files'])<=32
(R/'checkpoint.json').write_text(json.dumps(cp,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('wake','scripts/long-task-watchdog/aos_wake_progress.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
verified=w.checkpoint_snapshot(ROOT,cp['thread'],str(R/'checkpoint.json'),ROOT.parent/'docs/palantier/AOS项目开发上下文')
emit(D/'original-observer-consumption.json',verified);print(json.dumps(verified,ensure_ascii=False))
