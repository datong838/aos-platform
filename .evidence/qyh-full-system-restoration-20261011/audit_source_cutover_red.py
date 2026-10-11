"""Rollback-only real PostgreSQL counterexample to an incomplete ACL cutover."""
import json
import subprocess
import promote_stage_transport as E

TARGET = 'qyh-stage-transport-rehearsal-r2-20261011'
CID = 'f5e9055abb9512765470e9480afa31effb1a20aa661614baebed3c82b9018e0d'


def clone_metadata():
    return E.D.metadata(TARGET)


if __name__ == '__main__':
    result_path = E.P.R/'source-cutover-rollback-red.json'
    intent_path = E.P.R/'source-cutover-rollback-intent.json'
    assert not result_path.exists() and not intent_path.exists(), 'Reconcile existing probe instead of replay'
    item = json.loads(E.run(['inspect','--format',
        '{"Id":{{json .Id}},"Network":{{json .HostConfig.NetworkMode}},"Ports":{{json .HostConfig.PortBindings}},"Mounts":{{json .Mounts}}}',TARGET]))
    assert item['Id']==CID and item['Network']=='none' and item['Ports']=={}
    assert all(m.get('Name')!=E.P.VOLUME for m in item['Mounts'])
    source_before=E.P.M.fingerprint(E.SOURCE)
    before=E.P.M.fingerprint(TARGET)
    assert before==source_before and len(before)==647
    metadata=clone_metadata()
    with intent_path.open('x') as stream:
        json.dump({'target':TARGET,'containerId':CID,'sourceAttached':False,
            'transaction':'BEGIN/ROLLBACK only','originalWriterProbe':'UPDATE Plan WHERE false',
            'commitAuthorized':False},stream,indent=2)
    sql="""\set VERBOSITY verbose
BEGIN;
REVOKE INSERT,UPDATE,DELETE ON public.aip_responsibility_plan_head FROM aos_runtime;
REVOKE INSERT,UPDATE,DELETE ON public.aip_responsibility_plan_revision FROM aos_runtime;
REVOKE INSERT,UPDATE,DELETE ON public.aip_production_contract_receipt FROM aos_runtime;
SELECT json_build_object('tables',count(*),'readOnlySourceAcl',bool_and(
 has_table_privilege('aos_runtime',name,'SELECT') AND
 NOT has_table_privilege('aos_runtime',name,'INSERT') AND
 NOT has_table_privilege('aos_runtime',name,'UPDATE') AND
 NOT has_table_privilege('aos_runtime',name,'DELETE') AND
 NOT has_table_privilege('aos_runtime',name,'TRUNCATE')))
FROM unnest(ARRAY['public.aip_responsibility_plan_head',
 'public.aip_responsibility_plan_revision','public.aip_production_contract_receipt']) AS name;
SET LOCAL ROLE aos_runtime;
UPDATE public.aip_responsibility_plan_head SET version=version WHERE false;
ROLLBACK;
"""
    probe=subprocess.run(E.DOCKER+['exec','-i',TARGET,'psql','-X','-qAt',
        '-v','ON_ERROR_STOP=0','-U','aos_app','-d',E.P.M.DB],
        input=sql.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    facts=[json.loads(line) for line in probe.stdout.decode().splitlines() if line.startswith('{')]
    assert facts==[{'tables':3,'readOnlySourceAcl':True}]
    assert b'42501' in probe.stderr and b'permission denied for table aip_responsibility_plan_head' in probe.stderr
    assert clone_metadata()==metadata, 'Rollback metadata differs: no replay'
    assert E.P.M.fingerprint(TARGET)==before and E.P.M.fingerprint(E.SOURCE)==source_before
    result={'outcome':'INCOMPLETE_SOURCE_ACL_CUTOVER_REAL_WRITER_RED',
        'threeSourceReadonlyAclWouldPass':True,'existingPlanWriterSqlState':'42501',
        'probeWhereFalse':True,'businessRowsInserted':0,'transactionRolledBack':True,
        'processExit':probe.returncode,'exitZeroIsNotWriterSuccess':True,
        'cloneSixMetadataScopesRestored':True,'cloneAndSource647TablesUnchanged':True,
        'sourceAclChanged':False,'needsCompleteIssuerCallerCutover':True,
        'fullRestorationAccepted':False}
    with result_path.open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'outcome':result['outcome'],'sourceUnchanged':True,'rollbackExact':True}))
