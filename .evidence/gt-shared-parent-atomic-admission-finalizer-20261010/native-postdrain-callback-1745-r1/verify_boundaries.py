"""Fresh negative arms and read-only independent result reconciliation."""
import json,hashlib,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2];a=json.loads((B/'attempt.json').read_text());v=json.loads((B/'verification.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());schema=a['schema']
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=a['database'],passfile=lab['passfile'],row_factory=dict_row)
negative=[]
with psycopg.connect(**params) as c:
 c.execute('SELECT 1')
 try:
  with c.transaction():c.execute('SELECT '+schema+'.arm(%s::regclass,false)',(schema+'.naive',))
 except psycopg.errors.InsufficientPrivilege as e:
  assert 'TEST_CALLBACK_TOP_OWNED_ARM_REQUIRED' in str(e);negative.append('subtransaction_arm_denied')
 else:raise AssertionError('subtransaction arm accepted')
 c.rollback()
 try:c.execute('SELECT '+schema+'.arm(%s::regclass,false)',('pg_catalog.pg_class',))
 except psycopg.errors.InsufficientPrivilege as e:
  assert 'TEST_CALLBACK_PRIVATE_RELATION_REQUIRED' in str(e);negative.append('non_private_relation_arm_denied')
 else:raise AssertionError('non-private arm accepted')
 c.rollback()
 c.execute('SET LOCAL ROLE aos_runtime')
 try:c.execute('SELECT '+schema+'.arm(%s::regclass,false)',(schema+'.naive',))
 except psycopg.errors.InsufficientPrivilege:negative.append('runtime_arm_denied')
 else:raise AssertionError('runtime arm accepted')
 c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 for row in v['cases']:assert c.execute('SELECT pg_xact_status(%s::xid8) AS s',(row['xid'],)).fetchone()['s']==v['independent_statuses'][row['label']]
 counts={t:c.execute('SELECT count(*) AS n FROM '+schema+'.'+t).fetchone()['n'] for t in v['owned_counts']};assert counts==v['owned_counts']
 durability={k:c.execute('SHOW '+k).fetchone()[k] for k in ['fsync','full_page_writes','synchronous_commit']};assert set(durability.values())=={'on'}
 original_so=subprocess.check_output(['docker','exec',lab['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so'],text=True).split()[0];assert original_so=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
result=dict(status='POSTDRAIN_CALLBACK_BOUNDARIES_AND_DURABLE_READBACK_VERIFIED',authority='AOS-001745',negative_arms=negative,owned_counts=counts,durability=durability,original_signature_binary_unchanged=True,c_sha256=hashlib.sha256((B/'probe.c').read_bytes()).hexdigest(),library_sha256=v['binary_sha256'],full_admission=False,execution_allowed=False,remaining_matrix=['Prepared and parallel channels have explicit C denial but were not exercised in this isolated three-case probe.','No original Source/hold/complete end positive was performed; a real admission protocol still requires exact native package, caller, closure and postcommit confirmation.'])
(B/'independent-boundaries.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],negative_arms=negative)))
