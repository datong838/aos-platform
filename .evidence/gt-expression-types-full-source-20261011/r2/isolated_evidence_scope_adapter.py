"""Current leased evidence path only; no Judge or Source semantic adaptation."""
import hashlib,json,os,time
from pathlib import Path

def install(patch,base,repo):
    from tests.aip import test_model_eval_judge_authority_pg as module
    original=module._judge_fixture_evidence_paths
    task='gt-expression-types-full-source-20261011'
    owner='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
    expected=base/'fresh-judge-evidence'
    models=repo/'.evidence/gt-atomic-model-admission-20261008'
    context=repo.parent/'docs/palantier/AOS项目开发上下文/memory'
    def validate_path(selected,require_helpers=True):
        path=Path(selected)
        if not path.is_absolute() or '..' in path.parts or path!=expected or not path.is_dir():
            raise ValueError('exact current Task child required')
        if any(x.is_symlink() for x in (path,*path.parents)):
            raise ValueError('symlink rejected')
        receipt=json.loads((context/'receipts/tasks'/f'{task}.json').read_text())
        leases=json.loads((context/'leases.json').read_text())['leases']
        authority=json.loads((context/'authority.json').read_text())
        from datetime import datetime
        scoped='aos-platform/'+str(path.relative_to(repo))
        if receipt.get('owner')!=owner or receipt.get('status')!='ACTIVE' or receipt not in leases or receipt.get('base_revision')!=authority['project_revision'] or datetime.fromisoformat(receipt['lease_expires_at']).timestamp()<=time.time() or not any(scoped==x or scoped.startswith(x.rstrip('/')+'/') for x in receipt['scope']):
            raise ValueError('current Task lease/owner/authority required')
        if require_helpers:
            for n in ['legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py']:
                p=path/n
                if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((models/n).read_bytes()).digest():
                    raise ValueError('exact original helper required')
            if any((path/n).exists() for n in ['legal-model-prefix-application-r4.json','legal-eval-application-result-r4.json']):
                raise ValueError('attempt already contains application evidence')
        return path,path
    def guarded():
        selected=os.environ.get('AOS_JUDGE_FIXTURE_EVIDENCE_ROOT')
        if selected is None:return original()
        return validate_path(selected)
    rejects=[]
    for candidate in [str(base),str(base.parent),str(base/'neighbor'),'relative-attempt']:
        try:validate_path(candidate,False)
        except ValueError:rejects.append(candidate)
        else:raise AssertionError('Out-of-task candidate admitted')
    validate_path(str(expected))
    with (base/'evidence-scope-adapter-verification.json').open('x') as f:
        json.dump({'owner':owner,'task':task,'exactPathAccepted':str(expected),'outOfScopeRejected':rejects,'originalHelperHashesPreserved':True,'existingResultRejectedByGuard':True,'semanticSourceOrJudgeChecksChanged':False},f,indent=2);f.write('\n')
    patch.setattr(module,'_judge_fixture_evidence_paths',guarded)
