import hashlib,json,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;lab=json.loads((B/'lab.json').read_text());r=json.loads((B/'results.json').read_text())
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname='aos_meta',passfile=lab['passfile'],row_factory=dict_row,require_auth='scram-sha-256') as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
    rows=c.execute('SELECT * FROM aos_precommit_probe_result').fetchall();assert len(rows)==1 and rows[0]['label']=='check_then_wait'
    statuses={x['label']:c.execute('SELECT pg_xact_status(%s::xid8) AS state',(x['xid'],)).fetchone()['state'] for x in r['cases']}
    assert statuses=={'check_then_wait':'committed','wait_then_check':'aborted'}
    assert rows[0]['xid']==r['cases'][0]['xid']
    durable={k:c.execute('SHOW '+k).fetchone()[k] for k in ('fsync','full_page_writes','synchronous_commit')};assert all(v=='on' for v in durable.values())
    acl=c.execute("SELECT coalesce(bool_or(a.grantee=0 AND a.privilege_type='EXECUTE'),false) AS public_execute FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid='public.aos_precommit_probe_arm(timestamptz,boolean)'::regprocedure").fetchone();assert not acl['public_execute']
canon=lambda x:sorted(x,key=lambda y:json.dumps(y,sort_keys=True))
count=0
for ctx,items in json.loads((B/'resource-baseline.json').read_text()).items():
    for x in items:
        now=json.loads(subprocess.check_output(['docker','--context',ctx,'inspect',x['Id']],text=True))[0]
        assert now['State']['StartedAt']==x['started'] and canon(now['Mounts'])==canon(x['mounts']) and now['HostConfig']['PortBindings']==x['ports'];count+=1
state=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['container_id']],text=True))[0];assert state['Image']==lab['image'] and state['RestartCount']==0
csha=subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so'],text=True).split()[0];assert csha=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
result=dict(read_only=True,rows=[dict(x,deadline=x['deadline'].isoformat()) for x in rows],xid_statuses=statuses,durability=durable,public_execute=False,old_resources_unchanged=True,old_resource_count=count,original_verifier_sha256=csha,strict_completion_candidate='RED',callback_mechanism_only=True,formal_execution=False)
(B/'independent-verification.json').write_text(json.dumps(result,indent=2));print('Independent committed/aborted xid and one retained row verified; all',count,'old containers unchanged')
