"""Exact original reference fix and stage evidence; do not close full Tasks."""
from pathlib import Path
import json,hashlib,subprocess,importlib.util,sys
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2]; B=Path(__file__).resolve().parent
def git(*args): return subprocess.check_output(['git',*args],cwd=R,text=True)
changes=json.loads((B/'expected-changes.json').read_text())
verification=json.loads((B/'independent-original-green-verification.json').read_text())
assert verification['source_count']==2 and verification['old_resources_unchanged']
product=changes['product'];test=changes['test']
assert hashlib.sha256((R/product['path']).read_bytes()).hexdigest()==product['after_sha256']
assert hashlib.sha256(git('show','HEAD:'+product['path']).encode()).hexdigest()==product['before_sha256']
assert hashlib.sha256(git('show',':'+test['path']).encode()).hexdigest()==test['index_sha256']
assert git('diff','--cached','--name-only').splitlines()==[test['path']]
plans=['.evidence/gt-capacity-source-publication-20261006/plan.md',
 '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-gt-provider-capacity-publication-20261005/plan.md']
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file()]
subprocess.run(['git','add','--',*files,*plans,product['path']],cwd=R,check=True)
assert set(git('diff','--cached','--name-only').splitlines())==set(files+plans+[product['path'],test['path']])
assert hashlib.sha256(git('show',':'+test['path']).encode()).hexdigest()==test['index_sha256']
subprocess.run(['git','commit','-m','fix(aip): revalidate original current Source reference instances'],cwd=R,check=True)
head=git('rev-parse','HEAD').strip()
assert git('diff','--numstat','--',test['path']).split()[:2]==['6','1']
sp=importlib.util.spec_from_file_location('m',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(sp);sys.modules['m']=m;sp.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001631'
for tid in ('gt-provider-capacity-publication-schema-20261005','gt-capacity-source-publication-20261006','gt-capacity-occupation-source-20261007',B.name):
    receipt=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text())
    assert receipt['status']=='ACTIVE' and not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
update=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],
 last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',
 summary='Current frozen full Source/profile dependency review: independent model review again local Prime daemon ownership exit1/no result; no PASS/no shared restart. Manual complete dependency audit finds legacy FormalExactRef instance extra-key acceptance in original actual Source COMMIT/new consumer (native RED43.93s, earlier wrapper whitelist setup failure retained separately). Original exact Task scopes/plans before one-line instance validation correction and selective four-line persistent regression. Full original shared/distinct consumer2PASS84.11s; two signed committed Sources/roles/interfaces/31old resources independently verified. Prior fixture6/1 unstaged protected; no full Source/profile/legacy Delivery or finalCOMMIT temporal/first-chain claim. Review and original feature Tasks ACTIVE; no currentDB/runtime/Goal change.')])
orig=m.atomic_write_text
m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in [str((B/'review.md').relative_to(R)),str((B/'expected-changes.json').relative_to(R)),str((B/'independent-native-ref-verification.json').relative_to(R)),str((B/'independent-original-green-verification.json').relative_to(R)),product['path'],test['path'],*plans]]
paths=[]
for tid in ('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008'):
    receipt=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text())
    assert receipt['status']=='ACTIVE' and datetime.fromisoformat(receipt['lease_expires_at'])>datetime.now(timezone.utc)
    cpfile=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpfile.read_text())
    prior='.evidence/'+tid+'/current-source-command-fix-reference-1631.json';new='.evidence/'+tid+'/current-source-exact-ref-fix-reference-1632.json'
    assert prior in cp['evidence_files']
    (R/new).write_text(json.dumps(dict(authority_revision=update['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2))
    cp.update(authority_revision=update['project_revision'],step='original-legacy-source-reference-native-fixed-full-source-dependency-review-active')
    cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpfile.write_text(json.dumps(cp,indent=2))
    paths.extend([new,str(cpfile.relative_to(R))])
assert m.validate_installation()['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
(B/'context-stage-sync.json').write_text(json.dumps(dict(authority_revision=update['project_revision'],code_commit=head,sync=sync,installation_validation='GREEN',strong_projections='CURRENT',original_feature_and_review_tasks='ACTIVE',protected_fixture_unstaged='6 additions/1 deletion'),indent=2))
paths.append(str((B/'context-stage-sync.json').relative_to(R)))
assert not git('diff','--cached','--name-only').strip()
subprocess.run(['git','add','--',*paths],cwd=R,check=True)
assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record original Source reference native correction'],cwd=R,check=True)
print(update['project_revision'],'EXACT_REFERENCE_STAGE_VERIFIED_ORIGINAL_TASKS_ACTIVE')
