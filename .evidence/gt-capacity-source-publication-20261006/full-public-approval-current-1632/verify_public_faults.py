"""Read-only reconciliation of direct public prepare fault matrix."""
import json,hashlib,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2]
result=json.loads((B/'native-public-faults-r2-result.json').read_text())
lab=json.loads((B/'lab.json').read_text())
calls=[x for x in result['results'] if x['phase']=='call']
bindings=[x for x in result['results'] if x['phase']=='database_binding']
assert result['pytest_exit']==0 and len(calls)==len(bindings)==24
assert all(x['outcome']=='passed' for x in calls)
assert {x['nodeid'] for x in calls}=={x['nodeid'] for x in bindings}
assert len({x['database'] for x in bindings})==24
reports=[]
for binding in bindings:
    param=binding['nodeid'].rsplit('[',1)[1].removesuffix(']')
    fault,layout=param.rsplit('-',1)
    proof=json.loads((B/(fault+'-'+layout+'-r2.json')).read_text())
    assert proof['database']==binding['database'] and proof['fault']==fault
    observations=proof['observations']
    assert [x['outcome'] for x in observations]==['prepared_actual_public_source','native_refusal','prepared_actual_public_source']
    assert observations[1]['sqlstate'] in ('P0002','22023')
    assert all(x['identity']['session']==x['identity']['role']=='aos_provider_capacity_issuer' for x in observations)
    with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=binding['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        counts={table:c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.'+table).fetchone()['n'] for table in
                ('source_pending','source_publication','source_provenance','global_account','global_provider')}
        assert all(x==0 for x in counts.values())
        assert c.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher','aos_provider_capacity_occupation') AND rolcanlogin").fetchone()['n']==0
        for fn in ('public.prepare_capacity_source(bytea,text,text,jsonb)','public.commit_capacity_source(text,bytea,bytea)',
                   'public.read_current_capacity_source(bytea,jsonb)','aos_capacity_publication_private.require_current_source_installation()'):
            assert c.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(fn,)).fetchone()['absent']
        reports.append(dict(nodeid=binding['nodeid'],database=binding['database'],actual_public_sql_observations=observations,
                            publication_counts=counts,temporary_interfaces_removed=True,roles_nologin=True))
for record in json.loads((R/'.evidence/gt-source-full-contract-current-20261009/input-bindings.json').read_text()):
    assert hashlib.sha256((R/record['path']).read_bytes()).hexdigest()==record['sha256']
old=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers']
for item in old:
    started=item['started']
    if item['Id'].startswith('9cc6091c304b55'):
        started=json.loads((R/'.evidence/current157-full-restart-20261009-010759/final-independent-verification.json').read_text())['pg_started']
    now=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',item['Id']],text=True))[0]
    canonical=lambda values:sorted(values,key=lambda x:json.dumps(x,sort_keys=True))
    assert now['Id']==item['Id'] and now['State']['StartedAt']==started
    assert canonical(now['Mounts'])==canonical(item['mounts']) and now['HostConfig']['PortBindings']==item['ports']
(B/'independent-public-fault-verification.json').write_text(json.dumps(dict(schema='aos-direct-public-source-original-fault-verification/v1',
    authority_revision='AOS-001632',head='0eba54befe62b6b625b0272ee9a82e98da22abf3',node_count=24,databases=reports,
    old_resources_unchanged=True,old_resource_count=len(old),product_hashes_unchanged=True,
    original_test_unchanged=True,full_source_delivery=False,business_execution=False),indent=2))
print('24 direct-public original field faults: valid before/refused native after mutation/valid after restoration, no publication residue')
