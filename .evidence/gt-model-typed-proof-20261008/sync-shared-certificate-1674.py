"""Official CAS and exact checkpoint evidence; never write private Goal/memory."""
from pathlib import Path
import importlib.util, sys, json, hashlib, subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001673'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
proof=R/'.evidence/gt-atomic-model-admission-20261008/shared-parent-certificate-native-1673-r3/independent-readback.json'
assert json.loads(proof.read_text())['identity']['status']=='aborted'
review=B/'shared-certificate-review-1673.md'
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Independent full-v3 certificate signing domain binds whole prepared description/original risk/caller xid-pid/2cases4legs; true Ed25519 necessary validation. 332 pure PASS with DB connect denied; fresh Source/original independently approved 100s native full node PASS; isolated actual COMMIT rejected and independent aborted/4 private counts zero. No issuer authority or execution grant.'],
 incomplete=a['incomplete']+['V3 certificate presented-root crypto is necessary only: persisted current issuer provenance/epoch, independent v3 identity/certificate binding and withdrawal, final joint admission and real token/transport remain pending. R1 auxiliary path and R2 missing fourth fixture node failures retained; R3 full node separate. Historical two experiment before-image bytes remain unavailable.'],
 next_steps=['Continue registered v3 distinct private identity/certificate binding and same-snapshot original issuer/withdrawal reconciliation; preserve legacy v1/v2 domain and runtime denial.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-v3-certificate-domain':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(review),summary='v3 necessary certificate domain 332 pure + complete native isolated node; issuer metadata/provenance, identity/current epochs and joint execution still pending; no formal DB, Provider or Delivery')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010']
extra=[str(review.relative_to(R)),str((B/'shared-certificate-old-definitions-1673.json').relative_to(R)),str((B/'shared-certificate-pure-result-1673.json').relative_to(R)),str(proof.relative_to(R)),str(proof.with_name('native-certificate-proof.json').relative_to(R)),str(proof.with_name('result-r3.json').relative_to(R))]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 assert old.endswith('current-shared-risk-description-reference-1673.json')
 refs=[old]+extra
 path=root/'current-shared-certificate-reference-1674.json'
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,executors_authenticated=False,issuer_metadata_current=False,root_provenance_verified=False,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.write_text(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='v3-certificate-necessary-crypto-green-persisted-root-identity-withdrawal-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'shared-certificate-context-sync-1674.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,issuer_metadata_current=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'])
