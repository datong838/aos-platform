import json
from pathlib import Path

R = Path(__file__).resolve().parents[2]
B = Path(__file__).resolve().parent
O = R / '.evidence/gt-source-full-suite-desktop-r2-20261009'
for directory, step, proofs in (
    (B, 'entire386-terminal-green-independent-readback-complete', ['independent-whole-final-verification.json', 'terminal-resource-verification.json']),
    (O, 'whole-r3-terminal-failed-shm-exhaustion-readonly-reconciled', ['independent-failure-verification.json', 'failure-reconciliation.json']),
):
    f = directory / 'checkpoint.json'
    cp = json.loads(f.read_text(encoding='utf-8'))
    cp.pop('command', None)
    cp['step'] = step
    for name in proofs:
        ref = str((directory / name).relative_to(R))
        if ref not in cp['evidence_files']:
            cp['evidence_files'].append(ref)
    f.write_text(json.dumps(cp, indent=2), encoding='utf-8')
    with (directory / 'plan.md').open('a', encoding='utf-8') as output:
        output.write('\nTerminal receipt: ' + step + '. Bounded evidence delivery only; actual COMMIT deadline remains pending.\n')

source = (O / 'finalize_full_green.py').read_text(encoding='utf-8')
source = source.replace("native-whole-r3-result.json", "native-whole-r4-result.json")
source = source.replace("files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]", "old=R/'.evidence/gt-source-full-suite-desktop-r2-20261009'\nfiles=[str(x.relative_to(R)) for directory in (B,old) for x in sorted(directory.iterdir()) if x.is_file()]\nassert all(x.startswith('.evidence/') for x in files)")
source = source.replace("u=m.update_authority(", "failed=json.loads((old/'independent-failure-verification.json').read_text())\nassert failed['database_count']==127 and failed['sources']==7 and failed['old_resources_unchanged'] and failed['exact_inputs_unchanged']\ndfailed=m.complete_task(m.DEFAULT_PATHS,task_id=old.name,expected_revision=a['project_revision'],result='WHOLE_R3_341PASS_SETUP_SHM_ERROR_TERMINAL_READONLY_RECONCILED',changed_files=[x for x in files if x.startswith(str(old.relative_to(R))+'/')],commits=[head],verification=[failed['summary'],'127 retained databases / 7 committed signed Sources; SIG11 and WAL recovery preserved; no replay'],risks=['64MiB shared memory exhaustion and backend SIG11; r3 is FAILED, not cumulative green'],blockers=[])\nu=m.update_authority(")
source = source.replace("B/'next-final-commit-investigation.md'", "old/'next-final-commit-investigation.md'")
source = source.replace("delivery=d,sync=sync", "delivery=d,prior_failed_delivery=dfailed,sync=sync")
source = source.replace("print(u['project_revision'],p['summary'])", "print(u['project_revision'],p['summary'])")
(B / 'finalize_full_green.py').write_text(source, encoding='utf-8')
print('Prepared terminal checkpoints and exact bounded finalizer')
