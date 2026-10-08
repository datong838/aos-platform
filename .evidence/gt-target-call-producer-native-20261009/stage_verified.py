from pathlib import Path
import json,subprocess
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
result=json.loads((B/'native-r2-result.json').read_text());assert result['pytest_exit']==0
readback=json.loads((B/'independent-readback.json').read_text());assert readback['old_resources_unchanged'] and readback['xact_state']=='aborted'
assert '318 passed' in (B/'adjacent-r1.log').read_text()
files=['services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py']
for folder in (R/'.evidence/gt-target-call-original-binding-native-20261009',B):
 files.extend(str(p.relative_to(R)) for p in sorted(folder.iterdir()) if p.is_file() and p.name not in ('stage-files.json','code-commit.json','delivery.json','context-sync-1613.json'))
# Readiness Delivery is already terminal and belongs to this wave.
files.append('.evidence/gt-target-call-original-binding-native-20261009/delivery.json')
files.append('.evidence/gt-atomic-model-admission-20261008/renewals-trusted-target-1612.json')
for prefix in ('source-newjudge-target-binding-r1-','source-newjudge-target-call-r1-','source-newjudge-target-call-r2-'):
 files.extend(str(p.relative_to(R)) for p in sorted((R/'.evidence/gt-atomic-model-admission-20261008').glob(prefix+'*.json')))
for prefix in ('target-binding-r1-','target-call-r1-','target-call-r2-'):
 files.extend(str(p.relative_to(R)) for p in sorted((R/'.evidence/gt-judge-call-authority-20261008').glob(prefix+'*.json')))
files=sorted(set(files));(B/'stage-files.json').write_text(json.dumps(files,indent=2)+'\n')
files.append(str((B/'stage-files.json').relative_to(R)))
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files],cwd=R,check=True)
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines());assert staged<=set(files)
subprocess.run(['git','commit','-m','feat(aip): bind original Target Intent to prepare-only call'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();(B/'code-commit.json').write_text(json.dumps(dict(head=head),indent=2)+'\n');print(head)
