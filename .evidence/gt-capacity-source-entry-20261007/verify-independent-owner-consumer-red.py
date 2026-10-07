"""Read-only preservation proof for a real independent consumer RED."""
import hashlib,json,re,tempfile
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
log=Path('.evidence/gt-capacity-source-publication-20261006/independent-owner-consumer-red-r1.log')
raw=log.read_text()
assert raw.count("E           ImportError: cannot import name 'ProviderCapacityConsumptionCommand'")==2
assert '2 failed, 379 deselected, 7 warnings in 65.12s' in raw
password=(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass').read_text().strip().split(':')[-1]
assert password not in raw and not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',raw)
outputs=[];count=0
for database in sorted(set(re.findall(r'Retained isolated test database: (aos_test_\w+_ti4_test)',raw))):
 with psycopg.connect(host='127.0.0.1',port=5434,dbname=database,user='aos_app',password=password,row_factory=dict_row) as conn:
  conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
  conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
  conn.execute('SET LOCAL ROLE aos_capacity_publication_owner')
  rows=conn.execute("""SELECT p.asset_id,p.content_hash,
   p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
   aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
   s.finalized,(v.native_xid=s.native_xid AND v.native_pid=s.native_pid AND v.native_session=s.native_session) AS provenance_ok,
   (s.command_raw::text IS NOT NULL) AS history_retained
   FROM aos_capacity_publication_private.source_publication p
   JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
   JOIN aos_capacity_publication_private.source_provenance v ON v.asset_id=p.asset_id AND v.org_id=p.org_id AND v.project_id=p.project_id
   WHERE p.asset_id LIKE 'independent-consumer-source-%'""").fetchall()
  for row in rows:assert all(row[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok','history_retained'))
  clean=conn.execute("""SELECT to_regprocedure('public.prepare_capacity_source(bytea,text,text,jsonb)') IS NULL
   AND to_regprocedure('public.commit_capacity_source(text,bytea,bytea)') IS NULL
   AND to_regprocedure('public.read_current_capacity_source(bytea,jsonb)') IS NULL
   AND to_regprocedure('aos_capacity_publication_private.require_current_source_installation()') IS NULL AS clean""").fetchone()['clean']
  assert clean
  outputs.append({'database':database,'sources':rows,'temporary_functions_absent':clean})
  count+=len(rows);conn.rollback()
assert count==2
files=[log,Path('services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py'),Path('.evidence/gt-capacity-source-entry-20261007/audit-business-consumer-callers.py')]
result={'schema':'aos-independent-owner-consumer-red/v1','base_head':'d1878575a14c151a2b791d040bd96036d9008dba','authority_revision':'AOS-001460','working_tree_test':True,'summary':'2 FAILED 65.12s; missing independent consumption command after all real preconditions','durable_sources_verified':count,'databases':outputs,'file_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'consumer_implemented':False,'full_source_delivery':False,'formal_resources_touched':False}
Path('.evidence/gt-capacity-source-entry-20261007/independent-owner-consumer-real-red.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'durable_sources_verified':count,'temporary_functions_absent':True,'consumer_implemented':False}))
