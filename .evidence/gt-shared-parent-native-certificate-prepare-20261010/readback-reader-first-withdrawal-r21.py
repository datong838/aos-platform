from pathlib import Path
import os,sys,json,hashlib,re,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';N=B/'native-r21';sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_shared_parent_certificate_prepare import shared_parent_certificate_prepare_statements,FUNCTION,MANIFEST,VERIFY,SOURCE_OWNER
from aos_api.aip_shared_parent_executor_set_reader import shared_parent_executor_set_statements,FUNCTION as READER
from aos_api.aip_model_eval_execution_authority import OWNER,ISSUER_OWNER
r=json.loads((N/'result-r21.json').read_text());p=json.loads((N/'published-identity-active.json').read_text());v=json.loads((N/'reader-first-withdrawal-proof.json').read_text());risk=json.loads((N/'native-description-proof.json').read_text());root=json.loads((N/'prepublished-root-proof.json').read_text());assert r['pytest_exit']==0 and r['old_files_unchanged']
assert v['blocking']['actual_blocking'] and v['blocking']['writer_live_observed'] and v['blocking']['reader']['pid'] in v['blocking']['blockers'] and v['blocking']['same_risk_caller_unchanged'] and v['blocking']['certificate_count']==4
assert v['statuses']==dict(risk='aborted',writer='committed') and v['writer']['commit_returned'] and v['fresh_private_original_identity_rejected'] and not v['fresh_full_v3_risk_attempted']
assert risk['actual_commit_rejected'] and risk['xid']==v['blocking']['reader']['xid']
p.update(withdrawal_xid=v['writer']['writer']['xid'],withdrawal_hash=v['event_hash'],after=v['head'])
v['risk_execution']=risk['manifest']['executionId']
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=r['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 statuses={k:c.execute('SELECT pg_xact_status(%s::xid8) AS s',(x,)).fetchone()['s'] for k,x in dict(risk=risk['xid'],root=root['root_xid'],identity=p['identity_xid'],withdrawal=p['withdrawal_xid']).items()};assert statuses==dict(risk='aborted',root='committed',identity='committed',withdrawal='committed')
 risk_counts={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] for t in ['prepared_plan_risk','prepared_shared_risk_description','prepared_parent_debit','prepared_execution_intent']};assert not any(risk_counts.values())
 legacy_counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ['aos_model_eval_execution_private.manifest','aos_model_eval_issuer_private.executor_certificate','aos_model_eval_issuer_private.certificate_identity_binding','aos_model_eval_issuer_private.certificate_epoch','aos_model_eval_issuer_private.identity_epoch','aos_model_eval_issuer_private.identity_withdrawal']};assert set(legacy_counts.values())=={1}
 assert c.execute('SELECT count(*) AS n FROM aos_model_eval_issuer_private.shared_parent_certificate_identity_binding').fetchone()['n']==0
 assert c.execute('SELECT count(*) AS n FROM aos_model_eval_execution_private.manifest WHERE execution_id=%s',(v['risk_execution'],)).fetchone()['n']==0
 for t,h in [('aos_model_eval_execution_private.manifest',p['manifest_hash']),('aos_model_eval_issuer_private.executor_certificate',p['certificate_hash']),('aos_model_eval_issuer_private.identity_withdrawal',p['withdrawal_hash'])]:
  row=c.execute('SELECT body,content_hash FROM '+t).fetchone();assert hashlib.sha256(bytes(row['body'])).hexdigest()==row['content_hash']==h
 head=dict(c.execute("SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id='target-identity'").fetchone());assert head==p['after']==dict(epoch=2,version=2,active=False)
 ddl=shared_parent_certificate_prepare_statements();functions={}
 for signature,statement,tag,owner in [(MANIFEST,ddl[1],'manifest',OWNER),(VERIFY,ddl[5],'verify',SOURCE_OWNER),(FUNCTION,ddl[9],'prepare',ISSUER_OWNER),(READER,shared_parent_executor_set_statements()[0],'shared',ISSUER_OWNER)]:
  row=c.execute('SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(signature,)).fetchone();body=re.search(r'\$'+tag+r'\$(.*?)\$'+tag+r'\$',statement,re.S)[1];assert row['prosrc']==body and row['prosecdef'] and row['owner']==owner and row['proconfig']==['search_path=pg_catalog']
  public=c.execute('SELECT count(*) AS n FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure AND a.grantee=0',(signature,)).fetchone()['n'];assert public==0;functions[signature]=dict(body_sha256=hashlib.sha256(body.encode()).hexdigest(),owner=owner,public_execute=public)
 c_acl=c.execute("SELECT a.grantee::regrole::text AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid='aos_ed25519.verify(bytea,bytea,bytea)'::regprocedure ORDER BY 1").fetchall();assert {x['grantee'] for x in c_acl}=={SOURCE_OWNER,'aos_ed25519_owner'} and all(x['privilege_type']=='EXECUTE' and not x['is_grantable'] for x in c_acl)
 perms=c.execute("SELECT has_function_privilege(%s,'aos_ed25519.verify(bytea,bytea,bytea)','EXECUTE') AS direct_c,has_schema_privilege(%s,'aos_ed25519','USAGE') AS direct_schema,has_function_privilege('aos_runtime',%s,'EXECUTE') AS runtime_delegate,has_function_privilege(%s,%s,'EXECUTE') AS issuer_delegate",(ISSUER_OWNER,ISSUER_OWNER,VERIFY,ISSUER_OWNER,VERIFY)).fetchone();assert dict(perms)==dict(direct_c=False,direct_schema=False,runtime_delegate=False,issuer_delegate=True)
 permissions={t:c.execute("SELECT has_table_privilege('aos_runtime',%s,'SELECT,INSERT,UPDATE,DELETE') AS p",(t,)).fetchone()['p'] for t in legacy_counts};assert not any(permissions.values())
 hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in r['file_hashes'].items()};assert all(hashes.values())
 out=dict(identity=identity,whole_termination_node_passed=True,reader_first_withdrawal=v,statuses=statuses,risk_counts=risk_counts,legacy_counts=legacy_counts,published_head=head,exact_original_metadata_hashes=True,current_frozen_hashes=hashes,functions=functions,original_c_acl=c_acl,verifier_permissions=dict(perms),runtime_table_permissions=permissions,root_provenance_verified=False,execution_allowed=False,full_task_delivered=False,reader_first_race_verified=True)
 (B/'independent-reader-first-withdrawal-readback-r21.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(database=identity['database'],statuses=statuses,head=head,whole_termination_node_passed=True,execution_allowed=False)))
