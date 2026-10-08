import json,tempfile,hashlib
from pathlib import Path
import psycopg
repo=Path(__file__).resolve().parents[2];base=Path(__file__).resolve().parent
p=repo/'.evidence/gt-judge-call-authority-20261008/whole-manifest-native-green-r5-1602-whole-plan-proof.json';v=json.loads(p.read_text())
r=repo/'.evidence/gt-judge-call-authority-20261008/whole-manifest-native-green-r5-1602-result.json';result=json.loads(r.read_text());assert result['pytest_exit']==0 and result['results'][0]['outcome']=='passed'
pf=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass';assert pf.stat().st_mode&0o077==0
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname='aos_test_379975a6f96d_ti4_test',passfile=str(pf)) as c:
 c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];assert cluster=='7693564235776004128';assert c.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='a0v_159'
 xid=c.execute('SELECT pg_xact_status(%s::xid8)',(v['caller']['xid'],)).fetchone()[0];assert xid=='aborted'
 counts=[c.execute('SELECT count(*) FROM '+table+' WHERE reservation_id=%s',(v[key],)).fetchone()[0] for table,key in [('aip_model_eval_budget_reservation','target_parent_id'),('aip_model_judge_budget_reservation','judge_parent_id')]];assert counts==[0,0]
 live=c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()[0];assert live==0
assert v['missing_parent_denied_no_bucket_write'] is True
old=(base/'whole-manifest-native-before-owner-1602.bin').read_bytes();owner=repo/'services/aos-api/aos_api/aip_model_eval_execution_owner.py';assert owner.read_bytes().startswith(old)
out={'authority_revision':'AOS-001602','exact_isolated_cluster':cluster,'xact_status':xid,'dual_parent_counts':counts,'other_active_clients':live,'caller':v['caller'],'both_fresh_xmin_match':v['target_parent_xmin']==v['judge_parent_xmin']==v['caller']['xid'],'cases':len(v['manifest']['cases']),'negative_cases':v['negative_cases']+['committed_parent_xmin','non_native','non_SERIAL','admin','missing_parent_no_bucket_write'],'execution_allowed':False,'old_owner_bytes_exact':True,'old_owner_sha256':hashlib.sha256(old).hexdigest(),'current_owner_sha256':hashlib.sha256(owner.read_bytes()).hexdigest(),'current_test_sha256':hashlib.sha256((repo/'services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py').read_bytes()).hexdigest(),'limits':['Necessary original row reader only; no authenticatedSource/physical account proof or finalizer','Per-call allocation/Intent/joint/executor refs synthetic; cumulative actual call fees and held allocations not proven','No SCRAM occupation identity or natural firstchain','New reader specific deadline wait proof pending; original adjacent waits passed']}
(base/'whole-manifest-native-independent-r5-1602.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
