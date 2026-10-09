"""Independent full selected-core readback, never replays any caller effect."""
from pathlib import Path
import json,re,hashlib,subprocess
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
result=json.loads((B/'native-core-r1-result.json').read_text())
lab=json.loads((B/'lab.json').read_text())
selection=json.loads((B/'selection.json').read_text())
calls=[x for x in result['results'] if x['phase']=='call']
bindings=[x for x in result['results'] if x['phase']=='database_binding']
all_passed=result['pytest_exit']==0 and all(x['outcome']=='passed' for x in calls)
assert {x['nodeid'].split('::')[-1].split('[')[0] for x in calls}==set(selection)
assert {x['nodeid'] for x in calls}=={x['nodeid'] for x in bindings}
log=(B/'native-core-r1.log').read_text()
summary=next(x for x in reversed(log.splitlines()) if re.search(r'\d+ (?:passed|failed)',x))
assert not re.search(r'\d+ (?:skipped|xfailed|xpassed|deselected)',summary)
reports=[];total_sources=0
for database in sorted({x['database'] for x in bindings}):
    assert re.fullmatch(r'aos_test_[a-z0-9]+_ti4_test',database)
    with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=database,
                         passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        sources=[]
        exists=c.execute("SELECT to_regclass('aos_capacity_publication_private.source_publication') IS NOT NULL AS present").fetchone()['present']
        if exists:
            sources=c.execute("""SELECT p.asset_id,p.account_id::text,p.content_hash,
                p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
                aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
                s.finalized,v.native_xid::text AS xid,v.native_session,
                v.native_xid=s.native_xid AND v.native_pid=s.native_pid AND v.native_session=s.native_session
                AND v.original_signed_facts=s.signed_facts AS provenance_ok,
                EXISTS(SELECT 1 FROM aos_capacity_publication_private.global_account a WHERE a.account_id=p.account_id) AS account_present
                FROM aos_capacity_publication_private.source_publication p
                JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
                JOIN aos_capacity_publication_private.source_provenance v ON
                (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)""").fetchall()
        for row in sources:
            assert all(row[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok','account_present'))
            assert row['native_session']=='aos_provider_capacity_issuer'
            assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(row['xid'],)).fetchone()['state']=='committed'
        total_sources+=len(sources)
        roles=c.execute("SELECT rolname,rolcanlogin,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher','aos_provider_capacity_occupation') ORDER BY rolname").fetchall()
        assert all(not x['rolcanlogin'] and not x['rolsuper'] and not x['rolbypassrls'] for x in roles)
        for fn in ('public.prepare_capacity_source(bytea,text,text,jsonb)','public.commit_capacity_source(text,bytea,bytea)',
                   'public.read_current_capacity_source(bytea,jsonb)','aos_capacity_publication_private.require_current_source_installation()'):
            assert c.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(fn,)).fetchone()['absent']
        occupation={}
        for table in ('prepared_call_occupation','prepared_plan_risk','prepared_parent_debit','prepared_execution_intent','call_occupation','call_occupation_event'):
            present=c.execute('SELECT to_regclass(%s) IS NOT NULL AS present',('aos_physical_capacity_occupation_private.'+table,)).fetchone()['present']
            occupation[table]=c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+table).fetchone()['n'] if present else 'ABSENT'
        assert all(x in (0,'ABSENT') for x in occupation.values())
        reports.append(dict(database=database,nodeids=[x['nodeid'] for x in bindings if x['database']==database],
            sources=sources,roles=roles,occupation=occupation,temporary_interfaces_removed=True))
assert total_sources>=4
for binding in json.loads((B/'input-bindings.json').read_text()):
    assert hashlib.sha256((R/binding['path']).read_bytes()).hexdigest()==binding['sha256']
old=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers']
for item in old:
    started=item['started']
    if item['Id'].startswith('9cc6091c304b55'):
        started=json.loads((R/'.evidence/current157-full-restart-20261009-010759/final-independent-verification.json').read_text())['pg_started']
    now=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',item['Id']],text=True))[0]
    canonical=lambda values:sorted(values,key=lambda x:json.dumps(x,sort_keys=True))
    assert now['Id']==item['Id'] and now['State']['StartedAt']==started
    assert canonical(now['Mounts'])==canonical(item['mounts']) and now['HostConfig']['PortBindings']==item['ports']
proof=dict(schema='aos-source-selected-core-native-verification/v1',head='0eba54befe62b6b625b0272ee9a82e98da22abf3',
    authority_revision='AOS-001632',summary=summary,all_selected_passed=all_passed,node_count=len(calls),
    database_count=len(reports),sources=total_sources,databases=reports,exact_inputs_unchanged=True,
    old_resources_unchanged=True,old_resource_count=len(old),full_source_delivery=False,formal_business_execution=False)
(B/'independent-core-verification.json').write_text(json.dumps(proof,indent=2))
print(summary,'independent retained DBs',len(reports),'signed actual COMMIT Sources',total_sources)
if not all_passed: raise SystemExit('Full selected core has failures; original evidence retained, diagnose without replay')
