"""Frozen current159 preview target/source guard; no migration or alternative target."""
import hashlib,json,os,runpy,subprocess,sys
from pathlib import Path
STATE=Path('/Users/ddt/work/projects/ai_agent/aos-recovery/api159-source-132b92e20d26')
SOURCE=STATE/'source';CONTEXT='colima-aos-extension'
ID='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
DB='aos_current_preview_20260927';CLUSTER='7683855731447750695'
MANIFEST_SHA='ed69fd4241bcebae2ef56f7a19f65b90696f23a71406149ff37a17223b70c117'
PYTHON_SHA='ed958d09c2b6fef15e9f194c39c15dbe2e6ece9ae78d0983df63ace9cc047097'
SIGNED='/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json'

def require(value,reason):
 if not value:raise ValueError(reason)
def digest(raw):return hashlib.sha256(raw).hexdigest()

def require_source(item):
 require(item.get('Id')==ID and item.get('Name')=='/aos-a0v-recovery-pg' and item.get('Image')==IMAGE
  and item.get('State',{}).get('Running') is True,'ORIGINAL_CURRENT_CONTAINER_REQUIRED')
 require(item.get('Config',{}).get('Cmd')==['postgres'] and item['Config'].get('Entrypoint')==['docker-entrypoint.sh'],'ORIGINAL_POSTGRES_COMMAND_REQUIRED')
 host=item.get('HostConfig',{});require(host.get('NetworkMode')=='bridge' and host.get('RestartPolicy',{}).get('Name')=='no','ORIGINAL_CURRENT_TOPOLOGY_REQUIRED')
 require(item.get('NetworkSettings',{}).get('Ports',{}).get('5432/tcp')==[{'HostIp':'127.0.0.1','HostPort':'18435'}],'ORIGINAL_LOCAL_PORT_REQUIRED')
 mounts=item.get('Mounts');require(type(mounts) is list and len(mounts)==2,'ORIGINAL_TWO_MOUNTS_REQUIRED')
 data=[x for x in mounts if x.get('Destination')=='/var/lib/postgresql/data'];backup=[x for x in mounts if x.get('Destination')=='/backup']
 require(len(data)==1 and data[0].get('Type')=='volume' and data[0].get('Name')=='aos-a0v-recovery-pg-data' and data[0].get('RW') is True,'ORIGINAL_NAMED_VOLUME_REQUIRED')
 require(len(backup)==1 and backup[0].get('Type')=='bind' and backup[0].get('Source')=='/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups' and backup[0].get('RW') is False,'ORIGINAL_READONLY_BACKUP_MOUNT_REQUIRED')

def require_database(value):
 require(type(value) is dict and value=={'cluster':CLUSTER,'database':DB,'version':'a0v_159'},'CURRENT_NATIVE159_DATABASE_REQUIRED')

def verify_source(root,manifest):
 require(type(manifest) is dict and len(manifest)==5604 and digest(json.dumps(manifest,sort_keys=True).encode())==MANIFEST_SHA,'EXACT_FROZEN_MANIFEST_REQUIRED')
 require(root.is_dir() and not root.is_symlink() and root.resolve()==root and root.stat().st_uid==os.getuid() and root.stat().st_mode&0o077==0,'PRIVATE_CODE_ROOT_REQUIRED')
 observed={}
 for path in root.rglob('*'):
  require(not path.is_symlink() and path.stat().st_uid==os.getuid() and path.stat().st_mode&0o077==0,'PRIVATE_REGULAR_SOURCE_REQUIRED')
  if path.is_file():observed[str(path.relative_to(root))]=digest(path.read_bytes())
  else:require(path.is_dir(),'SOURCE_SPECIAL_FILE_FORBIDDEN')
 require(observed==manifest,'FROZEN_API_SOURCE_CHANGED')

def main():
 require(sys.argv[1:] in (['--signed-receipt',SIGNED],['--signed-receipt',SIGNED,'--serve']),'EXACT_PREVIEW_START_ARGUMENTS_REQUIRED')
 require(digest(Path(sys.executable).read_bytes())==PYTHON_SHA,'ORIGINAL_PYTHON_BINARY_REQUIRED')
 def checked(args):
  result=subprocess.run(args,capture_output=True,timeout=20)
  require(result.returncode==0,'NATIVE_STARTUP_READBACK_FAILED');return result.stdout.decode('utf8',errors='strict')
 fmt='{"Id":{{json .Id}},"Name":{{json .Name}},"Image":{{json .Image}},"State":{"Running":{{json .State.Running}}},"Config":{"Cmd":{{json .Config.Cmd}},"Entrypoint":{{json .Config.Entrypoint}}},"HostConfig":{"NetworkMode":{{json .HostConfig.NetworkMode}},"RestartPolicy":{{json .HostConfig.RestartPolicy}}},"NetworkSettings":{"Ports":{{json .NetworkSettings.Ports}}},"Mounts":{{json .Mounts}}}'
 require_source(json.loads(checked(['docker','--context',CONTEXT,'inspect','--format',fmt,'aos-a0v-recovery-pg'])))
 query="BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'database',current_database(),'version',(SELECT version_num FROM alembic_version)); COMMIT;"
 require_database(json.loads(checked(['docker','--context',CONTEXT,'exec',ID,'psql','-X','-U','aos_app','-d',DB,'-qAt','-v','ON_ERROR_STOP=1','-c',query])))
 manifest_path=STATE/'manifest.json';require(not manifest_path.is_symlink() and manifest_path.stat().st_uid==os.getuid() and manifest_path.stat().st_mode&0o077==0,'PRIVATE_MANIFEST_REQUIRED')
 verify_source(SOURCE,json.loads(manifest_path.read_text()))
 os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
 runpy.run_path(str(SOURCE/'scripts/a0v_current_preview_http.py'),run_name='__main__')

if __name__=='__main__':
 try:main()
 except ValueError as exc:
  print(json.dumps({'outcome':'CURRENT_API_TARGET_GUARD_REJECTED','reason':str(exc),'business_runtime_authorized':False}),flush=True);raise SystemExit(2)
