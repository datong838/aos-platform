"""Independent retained signed fixed-window history and durable hold checks."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

base=Path(__file__).resolve().parent
repo=base.parents[1]
sys.path.insert(0,str(repo/'services/aos-api'))
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
record=json.loads((base/'fixed-window-counterexample.json').read_text())
assert record['database']=='aos_test_1c592b9c2334_ti4_test'
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=record['database'],
    passfile=str(passfile),row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity=c.execute("SELECT current_database() AS database,current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
    assert identity==dict(database=record['database'],readonly='on',cluster=record['cluster'])
    row=c.execute("""SELECT s.source_raw,s.account_id,
        aos_ed25519.verify(s.signature,s.source_raw,decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS signature_valid
        FROM aos_capacity_publication_private.source_publication s
        JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)
        WHERE s.content_hash=%s""",(record['source_hash'],)).fetchall()
    assert len(row)==1 and row[0]['signature_valid'] is True
    raw=bytes(row[0]['source_raw'])
    assert hashlib.sha256(raw).hexdigest()==record['source_hash']
    source=parse_signed_capacity_body(raw,PublishedProviderCapacitySourceV2)
    assert source.token_limit.mode=='fixed_window_rate'
    assert source.token_limit.model_dump(mode='json',by_alias=True)==record['token_limit']
    assert source.execution_allowed is False
    assert str(source.physical_account_id)==str(row[0]['account_id'])==record['physical_account_id']
    providers=[p.asset_id for p in source.provider_refs]
    mappings=c.execute('SELECT provider_id,account_id FROM aos_capacity_publication_private.global_provider WHERE provider_id=ANY(%s)',(providers,)).fetchall()
    assert len(mappings)==len(providers)==3
    assert all(str(x['account_id'])==record['physical_account_id'] for x in mappings)
    ids=[x['reservation_id'] for x in record['rows']]
    rows=c.execute('SELECT reservation_id,pool_id,request_units,token_units,status FROM aip_model_capacity_reservation WHERE reservation_id=ANY(%s) ORDER BY reservation_id',(ids,)).fetchall()
    assert rows==record['rows'] and len(rows)==2
    tokens=sum(x['token_units'] for x in rows);requests=sum(x['request_units'] for x in rows)
    assert tokens==record['actual_token_units']==20002>source.token_limit.max_tokens==20000
    assert requests==record['actual_request_units']==2<=source.max_concurrency==record['signed_concurrency_limit']
    pools=c.execute('SELECT provider_id,token_unit_per_reservation FROM aip_model_capacity_pool_revision WHERE pool_id=ANY(%s)',([x['pool_id'] for x in rows],)).fetchall()
    assert len(pools)==2 and len({x['provider_id'] for x in pools})==2
    assert all(x['provider_id'] in providers and x['token_unit_per_reservation']==10001 for x in pools)
    anchor=source.token_limit.window_anchor
    for observation in (record['window_start_observation'],record['window_finish_observation']):
        at=datetime.fromisoformat(observation['at'])
        assert at.tzinfo is not None and (at-anchor).total_seconds()//source.token_limit.window_seconds==observation['window_index']
    assert record['window_start_observation']['window_index']==record['window_finish_observation']['window_index']
    events=c.execute('SELECT count(*) AS n FROM aip_model_capacity_event WHERE reservation_id=ANY(%s)',(ids,)).fetchone()['n']
    assert events==2
    assert c.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']==0
    assert c.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']==0
    assert c.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall()==[dict(epoch=2,head_origin_hash=None)]
    role=c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert role is not None and not any(role.values())
    assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE roleid='aos_provider_capacity_occupation'::regrole OR member='aos_provider_capacity_occupation'::regrole").fetchone()['n']==0
    heads=c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
names=['fixed_window_probe.py','run_fixed_window_probe.py','verify_fixed_window.py','fixed-window-r1.log','fixed-window-counterexample.json']
result=dict(status='SIGNED_FIXED_WINDOW_DURABLE_COUNTEREXAMPLE_VERIFIED',identity=identity,
    signature_valid=True,source_hash_valid=True,token_limit=record['token_limit'],same_window=True,
    reserved_tokens=tokens,request_units=requests,events=events,provider_count=3,pool_count=2,
    canary=0,agent_runs=0,origin_withdrawn=True,occupation_role_restored=True,migration_heads=heads,
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    file_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in names},
    limitations=record['limitations']+['Source now withdrawn; immutable signature history is not current admission',
        'Caller xid/pid, precommit invisibility and observation times are original probe observations; independent read verifies final rows and window arithmetic'])
(base/'fixed-window-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'signed20000 reserved20002 requests2 same_window signature_valid canary0 role_restored')
