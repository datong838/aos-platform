"""Independent retained Source signature, no extra grants, and exact cleanup."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

base=Path(__file__).resolve().parent
record=json.loads((base/'owner-bridge-verification.json').read_text())
assert record['database']=='aos_test_fc2688b199ad_ti4_test'
assert record['test_owned_functions_removed'] and record['original_source_definitions_unchanged']
assert len(record['denials'])==4
assert len([r for r in record['denials'] if r.get('sqlstate') in ('22023','42501')])==3
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
observations={}
for database in (record['database'],'aos_test_6b38fa994717_ti4_test'):
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=database,
        passfile=str(passfile),row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity=c.execute("SELECT current_database() AS database,current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity==dict(database=database,readonly='on',cluster='7693564235776004128')
        assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE pronamespace='public'::regnamespace AND (proname LIKE 'gt_source_bridge_%' OR proname LIKE 'gt_physical_reader_%')").fetchone()['n']==0
        assert c.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']==0
        assert c.execute('SELECT count(*) AS n FROM aip_model_capacity_reservation').fetchone()['n']==0
        source_count=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n']
        if database==record['database']:
            assert source_count==1
            signed=c.execute("""SELECT s.source_raw,aos_ed25519.verify(s.signature,s.source_raw,
                decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS signature_valid
                FROM aos_capacity_publication_private.source_publication s
                JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)
                WHERE s.content_hash=%s""",(record['source_hash'],)).fetchone()
            assert signed['signature_valid'] and hashlib.sha256(bytes(signed['source_raw'])).hexdigest()==record['source_hash']
            assert c.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall()==[dict(epoch=2,head_origin_hash=None)]
        else:assert source_count==0
        flags=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(record['role'],)).fetchone()
        assert flags and not any(flags.values())
        grant_count=c.execute("""SELECT (
            SELECT count(*) FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole
            )+(SELECT count(*) FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee=%s::regrole)
            +(SELECT count(*) FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee=%s::regrole)
            +(SELECT count(*) FROM pg_class t,LATERAL aclexplode(t.relacl) a WHERE a.grantee=%s::regrole)
            AS n""",(record['role'],)*5).fetchone()['n']
        assert grant_count==0
        assert c.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']==0
        observations[database]=dict(identity=identity,source_count=source_count,test_functions=0,extra_role_grants=0,
            role_inert=True,agent_runs=0,capacity_reservations=0,canary=0,
            migration_heads=c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall())
names=['owner_bridge_probe.py','run_owner_bridge_probe.py','verify_owner_bridge.py',
    'owner-bridge-verification.json','owner-bridge-r2.log','owner-bridge-r1.safe.log']
result=dict(status='OWNER_BRIDGE_DURABLE_HISTORY_AND_CLEANUP_VERIFIED',databases=observations,
    file_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in names},
    limitations=['Unchanged original Source definitions/ACL and caller xid/pid are original live-run observations',
        'Source now withdrawn; signature history is not current admission',
        'Owner bridge prototype does not implement physical capacity/budget/Intent or authorize formal grants'])
(base/'owner-bridge-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'signature valid; test functions0 grants0; role inert; Sourcewithdrawn; AgentRun0/capacity0/canary0')
