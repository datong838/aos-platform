"""Independent retained database readback; no caller replay or database deletion."""
import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((B/'lab.json').read_text())
result=json.loads((B/'native-current-body-expiry-r3-result.json').read_text())
assert result['pytest_exit']==0 and len(result['results'])==1 and result['results'][0]['outcome']=='passed'
obs=[json.loads(p.read_text()) for p in B.glob('observation-*.json')];assert len(obs)==1
reports=[]
for o in obs:
    parse=datetime.fromisoformat
    assert parse(o['positive_at'])<parse(o['source_valid_until'])<parse(o['after_expiry_at'])
    assert parse(o['after_expiry_at']).timestamp()<o['authentication_deadline']
    assert o['independent_owner'] and not o['execution_allowed']
    assert len(o['denials'])==2 and all(x['sqlstate']=='22023' and x['native_reason'] in
        ('CAPACITY_ORIGINAL_APPROVAL_EXPIRED','CAPACITY_CURRENT_SOURCE_EXPIRED') for x in o['denials'])
    with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=o['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        rows=c.execute("""SELECT p.asset_id,p.content_hash,p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
        aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
        s.finalized,v.native_xid::text AS original_xid,v.native_pid AS original_pid,
        v.native_session AS original_session,v.native_xid=s.native_xid AND v.native_pid=s.native_pid
          AND v.native_session=s.native_session AND v.original_signed_facts=s.signed_facts AS provenance_ok
        FROM aos_capacity_publication_private.source_publication p
        JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
        JOIN aos_capacity_publication_private.source_provenance v ON (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)
        WHERE p.asset_id=%s""",(o['asset'],)).fetchall()
        assert len(rows)==1;row=rows[0]
        assert all(row[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok'))
        assert row['content_hash']==o['source_sha256'] and row['original_session']=='aos_provider_capacity_issuer'
        assert row['original_xid']!=o['consumer_identity']['xid'] and row['original_pid']!=o['consumer_identity']['pid']
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(row['original_xid'],)).fetchone()['state']=='committed'
        counts={}
        for table in ('prepared_call_occupation','prepared_plan_risk','prepared_parent_debit','prepared_execution_intent','call_occupation','call_occupation_event'):
            counts[table]=c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+table).fetchone()['n']
        assert set(counts.values())=={0}
        assert c.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_occupation') AND rolcanlogin").fetchone()['n']==0
        for fn in ('public.prepare_capacity_source(bytea,text,text,jsonb)','public.commit_capacity_source(text,bytea,bytea)',
            'public.read_current_capacity_source(bytea,jsonb)','aos_capacity_publication_private.require_current_source_installation()'):
            assert c.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(fn,)).fetchone()['absent']
        reports.append(dict(database=o['database'],source=rows,occupation_counts=counts,
            original_source_committed=True,temporary_interfaces_removed=True,roles_nologin=True,denials=o['denials']))
for binding in json.loads((B/'baseline-files.json').read_text())+json.loads((B/'consumer-baseline-files.json').read_text()):
    assert hashlib.sha256((R/binding['path']).read_bytes()).hexdigest()==binding['sha256']
old=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers']
for item in old:
    started=item['started']
    if item['Id'].startswith('9cc6091c304b55'):
        started=json.loads((R/'.evidence/current157-full-restart-20261009-010759/final-independent-verification.json').read_text())['pg_started']
    now=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',item['Id']],text=True))[0]
    canonical=lambda v:sorted(v,key=lambda x:json.dumps(x,sort_keys=True))
    assert now['Id']==item['Id'] and now['State']['StartedAt']==started
    assert canonical(now['Mounts'])==canonical(item['mounts']) and now['HostConfig']['PortBindings']==item['ports']
teardown=json.loads((B/'teardown-original-expired-refusal.json').read_text())
assert teardown['original_generator_cleanup_executed'] and teardown['reason']=='CAPACITY_NATIVE_SIGNED_SUPPLIER_INPUTS_REQUIRED'
(B/'independent-verification.json').write_text(json.dumps(dict(observations=reports,
    original_products_unchanged=True,old_resources_unchanged=True,old_resource_count=len(old),
    teardown_expected_expired_input_refusal=teardown,full_feature_delivery=False,formal_execution_allowed=False),indent=2)+'\n')
print('Independent expired current Source denial/signature/provenance/six-zero/role/resource PASS')
