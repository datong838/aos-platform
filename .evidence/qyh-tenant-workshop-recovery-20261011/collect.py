import subprocess,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
FROZEN=Path('/Users/ddt/work/projects/ai_agent/aos-recovery/api159-reboot-ba05d7d655ea/source')
def run(args):
 return subprocess.run(args,check=True,capture_output=True,text=True,timeout=30).stdout.strip()
def query(db,sql):
 return json.loads(run(['docker','--context','colima-aos-extension','exec','aos-a0v-recovery-pg','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',db,'-c','BEGIN READ ONLY; '+sql+'; COMMIT;']))
current=query('aos_current_preview_20260927',"SELECT json_build_object('database',current_database(),'cluster',(SELECT system_identifier::text FROM pg_control_system()),'migration',(SELECT version_num FROM alembic_version),'orgs',(SELECT json_agg(json_build_object('id',id,'name',name)) FROM meta_org),'workspaces',(SELECT json_agg(json_build_object('orgId',org_id,'projectId',project_id,'name',name)) FROM meta_workspace),'installations',(SELECT json_agg(json_build_object('orgId',org_id,'projectId',project_id,'id',installation_id,'name',display_name,'currentRevision',current_revision,'activeRevision',active_revision)) FROM bundle_installation),'states',(SELECT json_agg(json_build_object('revision',revision,'state',state) ORDER BY revision) FROM bundle_installation_revision),'hostIdentities',(SELECT count(*) FROM extension_runtime_host_identity),'hostAssignments',(SELECT count(*) FROM extension_runtime_host_assignment),'runtimeBindings',(SELECT count(*) FROM extension_runtime_binding),'runtimeOperations',(SELECT count(*) FROM extension_runtime_operation))")
original=query('aos_meta',"SELECT json_build_object('database',current_database(),'targetOrg',(SELECT json_agg(json_build_object('id',id,'name',name)) FROM meta_org WHERE id='org-org'),'targetWorkspace',(SELECT json_agg(json_build_object('orgId',org_id,'projectId',project_id,'name',name)) FROM meta_workspace WHERE org_id='org-org' AND project_id='dev-project'))")
files=['services/aos-api/aos_api/orgs.py','services/aos-api/aos_api/asset_registry/workshop_catalog_source.py','services/aos-api/aos_api/ecommerce_runtime_workshop_catalog.py','services/aos-api/aos_api/routers/ecommerce_workshop.py']
identities=[]
for rel in files:
 live=REPO/rel;frozen=FROZEN/rel
 identities.append({'file':rel,'currentSha256':hashlib.sha256(live.read_bytes()).hexdigest(),'frozenSha256':hashlib.sha256(frozen.read_bytes()).hexdigest() if frozen.exists() else None})
result={'observedAt':datetime.now(timezone.utc).isoformat(),'head':run(['git','-C',str(REPO),'rev-parse','HEAD']),'current':current,'originalTarget':original,'sourceIdentity':identities,'readOnly':True,'businessExecutionAuthorized':False}
assert current['database']=='aos_current_preview_20260927' and current['cluster']=='7683855731447750695'
assert original['targetOrg']==[{'id':'org-org','name':'栖月汇商贸有限公司'}]
assert len(current['installations'])==1 and current['installations'][0]['activeRevision'] is None
assert current['states']==[{'revision':1,'state':'draft'},{'revision':2,'state':'submitted'},{'revision':3,'state':'approved'}]
assert all(current[k]==0 for k in ['hostIdentities','hostAssignments','runtimeBindings','runtimeOperations'])
(ROOT/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'outcome':'READONLY_DIAGNOSIS_VERIFIED','migration':current['migration'],'currentOrg':current['orgs'],'originalOrg':original['targetOrg'],'installationState':'approved@3','runtimeBindings':current['runtimeBindings'],'differentRelevantSourceFiles':[x['file'] for x in identities if x['currentSha256']!=x['frozenSha256']]},ensure_ascii=False))
