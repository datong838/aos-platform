"""Independent read-only audit of known native terminals and retained DBs."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import psycopg
E=Path(__file__).resolve().parent; R=E.parents[1]
sys.path.insert(0,str(E))
from reboot_resource_review import require_same
nodes=json.loads((E/'reboot-native-r1/terminal.json').read_text())['collected']
end=json.loads((E/'reboot-native-r6/terminal.json').read_text())
assert end['all_34_passed'] and len(nodes)==len(end['results'])==34
labs=[json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text()),json.loads((E/'reboot-lab.json').read_text())]
records=[]; databases=set()
for index,(node,result) in enumerate(zip(nodes,end['results']),1):
 lab=labs[1]; child=result['child']
 attempt=json.loads((E/child/'attempt.json').read_text()); terminal=json.loads((E/child/'terminal.json').read_text())
 assert result['node']==node and result['process_exit']==terminal['exit']==0
 assert terminal['results']==[{'nodeid':node,'phase':'call','outcome':'passed'}]
 assert attempt['lab_container']==lab['container_id'] and attempt['lab_cluster']==lab['cluster']
 for path,digest in attempt['source_hashes'].items():
  assert hashlib.sha256((R/path).read_bytes()).hexdigest()==digest
 database=terminal['database']; assert database not in databases and database.startswith('aos_test_'); databases.add(database)
 assert lab['port'] in (5441,5442)
 with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=database,passfile=lab['passfile']) as conn:
  conn.read_only=True
  row=conn.execute("SELECT current_database(),(SELECT system_identifier::text FROM pg_control_system()),(SELECT version_num FROM alembic_version),current_setting('fsync'),current_setting('synchronous_commit')").fetchone()
  assert row==(database,lab['cluster'],'a0v_159','on','on'); conn.rollback()
 records.append({'index':index,'node':node,'child':child,'database':database,'cluster':lab['cluster'],'version':'a0v_159','terminal_sha256':hashlib.sha256((E/child/'terminal.json').read_bytes()).hexdigest()})
intent=json.loads((E/'reboot-lab-create/intent.json').read_text())
for context,old in intent['before'].items():
 current={x['Id']:x for x in json.loads(subprocess.check_output(['docker','--context',context,'inspect',*[z['Id'] for z in old]]))}
 for before in old:
  x=current[before['Id']]; require_same(before,dict(Id=x['Id'],started=x['State']['StartedAt'],mounts=x['Mounts'],ports=x['HostConfig']['PortBindings']))
report={'at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'all_34_known_passed':True,'retained_distinct_databases':len(databases),'records':records,'original_resources_unchanged':True,'formal_database_writes':0,'root_trust_proven':False,'execution_allowed':False,'full_task_delivery':False}
with os.fdopen(os.open(E/'reboot-native-independent-audit.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:
 json.dump(report,out,indent=2);out.flush();os.fsync(out.fileno())
print(json.dumps({k:report[k] for k in ('all_34_known_passed','retained_distinct_databases','original_resources_unchanged','formal_database_writes')}))
