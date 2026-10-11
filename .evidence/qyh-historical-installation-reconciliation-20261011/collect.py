import ast, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
INSTALL='97aeb2e7-59ba-40f6-89a3-fb0293bc0497'
SOURCE=REPO/'services/aos-api/aos_api/extension_runtime/runtime_configuration_candidates.py'
def read(db,sql):
    r=subprocess.run(['docker','--context','colima-aos-extension','exec','aos-a0v-recovery-pg','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',db,'-c','BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY; '+sql+'; COMMIT;'],capture_output=True,text=True,timeout=30)
    if r.returncode: raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)
history=read('aos_meta_head',f"""SELECT json_build_object(
 'database',current_database(),'migration',(SELECT version_num FROM alembic_version),
 'cluster',(SELECT system_identifier::text FROM pg_control_system()),'readOnly',current_setting('transaction_read_only'),
 'installation',(SELECT json_agg(json_build_object('id',installation_id,'name',display_name,'revision',current_revision,'activeRevision',active_revision)) FROM bundle_installation WHERE org_id='org-org' AND project_id='dev-project' AND installation_id='{INSTALL}'),
 'bindings',(SELECT json_agg(json_build_object('generation',generation,'installationRevision',installation_revision,'desiredState',desired_state,'observedState',observed_state,'enabled',enabled,'fence',operation_fence,'configRefPresent',config_ref IS NOT NULL,'revision',revision)) FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project' AND installation_id='{INSTALL}'),
 'configurationRows',(SELECT count(*) FROM extension_runtime_configuration WHERE org_id='org-org' AND project_id='dev-project' AND installation_id='{INSTALL}'))""")
assert history['cluster']=='7683855731447750695' and history['readOnly']=='on'
assert history['installation'][0]['id']==INSTALL
tree=ast.parse(SOURCE.read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_candidates')
queries=[n.value for n in ast.walk(fn) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.strip().startswith('SELECT')]
assert len(queries)==1 and queries[0].count('%s')==16
sql=queries[0] % tuple("'"+v+"'" for v in ('org-org','dev-project')*8)
try: candidates={'status':'read','counts':read('aos_meta_head','SELECT row_to_json(x) FROM ('+sql+') x')}
except RuntimeError as error: candidates={'status':'schema_or_read_failure','error':str(error)}
result={'observedAt':datetime.now(timezone.utc).isoformat(),'history':history,'currentQuerySourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'historicalCandidates':candidates,'effects':'Read-only metadata; no source business data, no runtime replay or DB switch','limitation':'Historical candidates and active/binding states grant no current installation authority; separate snapshots.'}
(ROOT/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
