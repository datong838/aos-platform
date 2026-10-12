"""Original Skill Suite route refusal, without starting an execution or writer."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
s=importlib.util.spec_from_file_location('snap',ROOT/'.evidence/qyh-skill-proof-snapshot-20261012/recheck.py')
snap=importlib.util.module_from_spec(s);s.loader.exec_module(snap)
from aos_api.aip_eval_runner import AipEvalRunner
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_contracts import AssetType

SCOPE=snap.detail.SCOPE
factory=snap.snapshot
def counts():
    with factory(SCOPE) as conn:
        return {name:conn.execute('SELECT count(*) AS n FROM '+name+' WHERE org_id=%s AND project_id=%s',SCOPE.key).fetchone()['n']
            for name in ['aip_eval_run','aip_eval_report_revision','aip_eval_case_execution_proof','aip_production_contract_receipt']}

if __name__=='__main__':
    assert not (OUT/'result.json').exists()
    before=counts()
    with factory(SCOPE) as conn:
        suites=conn.execute("SELECT suite_id,revision FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND target_ref->>'assetType'=%s ORDER BY suite_id,revision",
            (*SCOPE.key,AssetType.SKILL_TEMPLATE.value)).fetchall()
    assert suites, 'No original Skill Suite: do not manufacture one'
    callbacks=[]
    def forbidden(*args,**kwargs):
        callbacks.append('unexpected execution callback')
        raise AssertionError('readonly Skill route must never execute target/judge/artifact')
    runner=AipEvalRunner(factory)
    denials=[]
    for row in suites:
        try:
            runner.run(SCOPE,suite_id=row['suite_id'],suite_revision=row['revision'],
                idempotency_key='readonly-producer-route-audit-'+row['suite_id'],
                actor='test-only:readonly-producer-audit',resolve_artifact=forbidden,
                execute_target=forbidden,execute_judge=forbidden)
        except AipEvalAuthorityConflict as error:
            assert str(error)=='formal Skill Eval executor authority unavailable'
            denials.append({**row,'reason':str(error)})
        else:raise AssertionError('Original unsupported Skill unexpectedly executed')
    after=counts();assert before==after and not callbacks
    calls=[]
    tracked=subprocess.check_output(['git','ls-files','services/aos-api/aos_api/*.py'],cwd=ROOT,text=True).splitlines()
    for relative in tracked:
        committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=ROOT)
        for node in ast.walk(ast.parse(committed.decode('utf-8-sig'))):
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
                if name=='persist_signed_skill_eval_report':calls.append({'path':relative,'line':node.lineno})
    result={'originalSuiteCount':len(suites),'originalDenials':denials,'callbacks':callbacks,
        'countsBefore':before,'countsAfter':after,'trackedWriterCalls':calls,
        'databaseWrites':0,'oldRunReplay':False,'newExecutionProduced':False,
        'identityConfigurationAloneIsSufficient':False,'formalRestoreAccepted':False}
    with (OUT/'result.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'originalSuitesDenied':len(denials),'writerCalls':len(calls),'callbacks':0,'countsUnchanged':True}))
