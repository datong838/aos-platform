from pathlib import Path
import sys,json,os,hashlib,re,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';N=B/'native-r16';sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_shared_parent_certificate_prepare import shared_parent_certificate_prepare_statements,FUNCTION,MANIFEST,VERIFY,SOURCE_OWNER
from aos_api.aip_shared_parent_executor_set_reader import shared_parent_executor_set_statements,FUNCTION as READER
from aos_api.aip_model_eval_execution_authority import OWNER,ISSUER_OWNER
result=json.loads((N/'result-r16.json').read_text());proof=json.loads((N/'native-same-transaction-prepare-proof.json').read_text());risk=json.loads((N/'native-description-proof.json').read_text());root=json.loads((N/'prepublished-root-proof.json').read_text())
domain=json.loads((N/'caller-domain-proof.json').read_text());assert domain['original_caller_unchanged'] and domain['manifest_absent_after_negatives'] and len(domain['rejections'])==2
other,old=domain['rejections'];assert other['name']=='other_native_backend_original_origin' and other['message']=='SHARED_DESCRIPTION_RISK_ORIGIN_REQUIRED' and other['scram_password_used'] and other['transaction_rolled_back'] and other['manifest_absent']
assert other['caller']['pid']!=domain['original_caller']['pid'] and other['caller']['xid']!=domain['original_caller']['xid']
assert old['name']=='valid_old_domain_signature' and old['message']=='SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED' and old['old_domain_crypto_valid'] and old['v3_domain_crypto_invalid']
from datetime import datetime
assert datetime.fromisoformat(old['before_clock'])<=datetime.fromisoformat(old['after_clock'])<datetime.fromisoformat(old['certificate_until'])
assert result['pytest_exit']==0 and result['old_files_unchanged'] and proof['certificate_count']==4 and all(proof['postwrite_savepoint_cleanup'].values())
assert risk['actual_commit_rejected'] and risk['xid']==proof['native_caller']['xid']
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 status=c.execute('SELECT pg_xact_status(%s::xid8) AS status',(risk['xid'],)).fetchone()['status'];assert status=='aborted'
 root_status=c.execute('SELECT pg_xact_status(%s::xid8) AS status',(root['root_xid'],)).fetchone()['status'];assert root_status=='committed'
 tables=['aos_physical_capacity_occupation_private.'+t for t in ['prepared_plan_risk','prepared_shared_risk_description','prepared_parent_debit','prepared_execution_intent']]
 tables+=['aos_model_eval_execution_private.manifest']+['aos_model_eval_issuer_private.'+t for t in ['executor_certificate','shared_parent_certificate_identity_binding','certificate_epoch','identity_epoch']]
 counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in tables};assert set(counts.values())=={0}
 functions={}
 ddl=shared_parent_certificate_prepare_statements()
 for signature,statement,tag,owner in [(MANIFEST,ddl[1],'manifest',OWNER),(VERIFY,ddl[5],'verify',SOURCE_OWNER),(FUNCTION,ddl[9],'prepare',ISSUER_OWNER),(READER,shared_parent_executor_set_statements()[0],'shared',ISSUER_OWNER)]:
  row=c.execute('SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(signature,)).fetchone()
  body=re.search(r'\$'+tag+r'\$(.*?)\$'+tag+r'\$',statement,re.S)[1]
  assert row['prosrc']==body and row['prosecdef'] and row['owner']==owner and row['proconfig']==['search_path=pg_catalog']
  public=c.execute('SELECT count(*) AS n FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure AND a.grantee=0',(signature,)).fetchone()['n'];assert public==0
  functions[signature]=dict(body_sha256=hashlib.sha256(body.encode()).hexdigest(),owner=owner,public_execute=public)
 permissions={t:c.execute("SELECT has_table_privilege('aos_runtime',%s,'SELECT,INSERT,UPDATE,DELETE') AS allowed",(t,)).fetchone()['allowed'] for t in tables};assert not any(permissions.values())
 historical_test='services/aos-api/tests/aip/test_shared_parent_certificate_prepare_pg.py'
 hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in result['file_hashes'].items()};assert all(hashes.values())
 replay=proof['replay_verification'];assert replay['identity_versions_before']==replay['identity_versions_after']==[2,2,2,2] and replay['same_original_certificate_set_replayed'] and replay['same_caller_and_current_metadata_unchanged']
 assert replay['boundaries_rejected']==['canary_scope_before_writes','runtime_direct_verifier_denied']
 c_acl=c.execute("SELECT a.grantee::regrole::text AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid='aos_ed25519.verify(bytea,bytea,bytea)'::regprocedure ORDER BY 1").fetchall()
 assert {r['grantee'] for r in c_acl}=={SOURCE_OWNER,'aos_ed25519_owner'} and all(r['privilege_type']=='EXECUTE' and not r['is_grantable'] for r in c_acl)
 verifier_permissions=c.execute("SELECT has_function_privilege(%s,'aos_ed25519.verify(bytea,bytea,bytea)','EXECUTE') AS direct_c,has_schema_privilege(%s,'aos_ed25519','USAGE') AS direct_schema,has_function_privilege('aos_runtime',%s,'EXECUTE') AS runtime_delegate,has_function_privilege(%s,%s,'EXECUTE') AS issuer_delegate",(ISSUER_OWNER,ISSUER_OWNER,VERIFY,ISSUER_OWNER,VERIFY)).fetchone()
 assert verifier_permissions==dict(direct_c=False,direct_schema=False,runtime_delegate=False,issuer_delegate=True)
 out=dict(identity=identity,caller_domain=domain,whole_node_passed=True,replay=replay,current_final_test_hash_bound=True,original_c_acl=c_acl,verifier_permissions=verifier_permissions,same_caller_staging_and_reader_substep_verified=True,postwrite_cleanup=proof['postwrite_savepoint_cleanup'],actual_commit_rejected=True,risk_xid_status=status,root_xid_status=root_status,counts=counts,functions=functions,runtime_table_permissions=permissions,frozen_hashes_match=hashes,root_provenance_verified=False,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False,next='same-caller replay/canary/withdrawal/final expiry matrix; formal Root/final joint independent')
 (B/'independent-core-readback-r16.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
