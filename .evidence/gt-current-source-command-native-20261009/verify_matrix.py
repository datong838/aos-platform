"""Independently read retained original consumer regression databases."""
import hashlib,json,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((B/'lab.json').read_text());databases=[]
for name,count in [('native-current-source-consumer-adjacent-r1-result.json',4),('native-current-source-consumer-regression-r1-result.json',2)]:
    result=json.loads((B/name).read_text());assert result['pytest_exit']==0
    calls=[x for x in result['results'] if x['phase']=='call'];bindings=[x for x in result['results'] if x['phase']=='database_binding']
    assert len(calls)==len(bindings)==count and all(x['outcome']=='passed' for x in calls)
    assert {x['nodeid'] for x in calls}=={x['nodeid'] for x in bindings}
    databases.extend(x['database'] for x in bindings)
assert len(databases)==len(set(databases))==6
reports=[]
for database in databases:
    with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=database,passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        rows=c.execute("""SELECT p.asset_id,p.content_hash,p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
        aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
        s.finalized,v.native_xid::text AS original_xid,v.native_pid AS original_pid,pg_xact_status(v.native_xid) AS original_state,
        v.native_session=s.native_session AND v.native_xid=s.native_xid AND v.native_pid=s.native_pid
        AND v.original_signed_facts=s.signed_facts AS provenance_ok
        FROM aos_capacity_publication_private.source_publication p JOIN aos_capacity_publication_private.source_pending s
        ON s.attempt_id=p.attempt_id JOIN aos_capacity_publication_private.source_provenance v
        ON (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)""").fetchall()
        assert rows and all(r['original_state']=='committed' and all(r[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok')) for r in rows)
        assert c.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_occupation') AND rolcanlogin").fetchone()['n']==0
        for fn in ('public.prepare_capacity_source(bytea,text,text,jsonb)','public.commit_capacity_source(text,bytea,bytea)',
            'public.read_current_capacity_source(bytea,jsonb)','aos_capacity_publication_private.require_current_source_installation()'):
            assert c.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(fn,)).fetchone()['absent']
        counts={}
        for table in ('prepared_call_occupation','prepared_plan_risk','prepared_parent_debit','prepared_execution_intent','call_occupation','call_occupation_event'):
            present=c.execute('SELECT to_regclass(%s) IS NOT NULL AS present',('aos_physical_capacity_occupation_private.'+table,)).fetchone()['present']
            counts[table]=c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+table).fetchone()['n'] if present else 'ABSENT'
        assert all(v in (0,'ABSENT') for v in counts.values())
        reports.append(dict(database=database,sources=rows,occupation=counts,temporary_interfaces_removed=True,roles_nologin=True))
change=json.loads((B/'expected-product-change.json').read_text());test=json.loads((B/'expected-test-change.json').read_text())
for item in (change,test):assert hashlib.sha256((R/item['path']).read_bytes()).hexdigest()==item['after_sha256']
before=(B/'source-consumer-before.py.txt').read_text();old="ProviderCapacityConsumptionCommand.model_validate(command.model_dump(mode='python',by_alias=True))"
assert before.count(old)==2 and (R/change['path']).read_text()==before.replace(old,'ProviderCapacityConsumptionCommand.model_validate(command)')
old_resources=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers']
for item in old_resources:
    started=item['started']
    if item['Id'].startswith('9cc6091c304b55'):
        started=json.loads((R/'.evidence/current157-full-restart-20261009-010759/final-independent-verification.json').read_text())['pg_started']
    now=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',item['Id']],text=True))[0]
    canonical=lambda v:sorted(v,key=lambda x:json.dumps(x,sort_keys=True))
    assert now['Id']==item['Id'] and now['State']['StartedAt']==started
    assert canonical(now['Mounts'])==canonical(item['mounts']) and now['HostConfig']['PortBindings']==item['ports']
(B/'independent-matrix-verification.json').write_text(json.dumps(dict(databases=reports,
    current_consumer_exact_two_line_fix=True,persistent_regression_exact_hash=True,
    old_resources_unchanged=True,old_resource_count=len(old_resources),formal_execution_allowed=False),indent=2)+'\n')
print('Independent six original regression databases/Source signatures/provenance/cleanup/resources verified')
