"""Fresh independent readback of both original Source consumer layouts."""
import json,re,hashlib,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent; R=B.parents[1]
lab=json.loads((B/'lab.json').read_text())
result=json.loads((B/'native-exact-ref-green-r1-result.json').read_text())
assert result['pytest_exit']==0 and len(result['results'])==2
assert all(x['phase']=='call' and x['outcome']=='passed' for x in result['results'])
assert {x['nodeid'].rsplit('[',1)[1] for x in result['results']}=={'shared]','distinct]'}
databases=sorted(set(re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)',(B/'native-exact-ref-green-r1.log').read_text())))
reports=[];sources=0
for database in databases:
    with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=database,passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        exists=c.execute("SELECT to_regclass('aos_capacity_publication_private.source_publication') IS NOT NULL AS present").fetchone()['present']
        rows=[]
        if exists:
            rows=c.execute("""SELECT p.asset_id,p.content_hash,p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
                aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
                s.finalized,v.native_xid::text AS xid,v.native_xid=s.native_xid AND v.native_pid=s.native_pid
                AND v.native_session=s.native_session AND v.original_signed_facts=s.signed_facts AS provenance_ok
                FROM aos_capacity_publication_private.source_publication p
                JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
                JOIN aos_capacity_publication_private.source_provenance v ON
                (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)
                WHERE p.asset_id LIKE 'consumed-source-%'""").fetchall()
        for row in rows:
            assert all(row[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok'))
            assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(row['xid'],)).fetchone()['state']=='committed'
        sources+=len(rows)
        assert c.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_occupation') AND rolcanlogin").fetchone()['n']==0
        for fn in ('public.prepare_capacity_source(bytea,text,text,jsonb)','public.commit_capacity_source(text,bytea,bytea)',
                   'public.read_current_capacity_source(bytea,jsonb)','aos_capacity_publication_private.require_current_source_installation()'):
            assert c.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(fn,)).fetchone()['absent']
        counts={}
        for table in ('prepared_call_occupation','prepared_plan_risk','prepared_parent_debit','prepared_execution_intent','call_occupation','call_occupation_event'):
            present=c.execute('SELECT to_regclass(%s) IS NOT NULL AS present',('aos_physical_capacity_occupation_private.'+table,)).fetchone()['present']
            counts[table]=c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+table).fetchone()['n'] if present else 'ABSENT'
        assert all(x in (0,'ABSENT') for x in counts.values())
        reports.append(dict(database=database,sources=rows,occupation_counts=counts,temporary_interfaces_removed=True,roles_nologin=True))
assert sources==2
changes=json.loads((B/'expected-changes.json').read_text())
for binding in json.loads((B/'bindings.json').read_text()):
    expected=changes['product']['after_sha256'] if binding['path']==changes['product']['path'] else binding['sha256']
    assert hashlib.sha256((R/binding['path']).read_bytes()).hexdigest()==expected
assert hashlib.sha256((R/changes['test']['path']).read_bytes()).hexdigest()==changes['test']['after_sha256']
old=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers']
for item in old:
    started=item['started']
    if item['Id'].startswith('9cc6091c304b55'):
        started=json.loads((R/'.evidence/current157-full-restart-20261009-010759/final-independent-verification.json').read_text())['pg_started']
    current=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',item['Id']],text=True))[0]
    canonical=lambda values:sorted(values,key=lambda x:json.dumps(x,sort_keys=True))
    assert current['Id']==item['Id'] and current['State']['StartedAt']==started
    assert canonical(current['Mounts'])==canonical(item['mounts']) and current['HostConfig']['PortBindings']==item['ports']
(B/'independent-original-green-verification.json').write_text(json.dumps(dict(databases=reports,original_cases=result['results'],
    source_count=sources,exact_changes_only=True,old_resources_unchanged=True,old_resource_count=len(old),full_source_delivery=False),indent=2))
print('Original shared/distinct consumer persistent regression and two real signed COMMIT Sources independently verified')
