from pathlib import Path
import subprocess,json
b=Path(__file__).resolve().parent;cmd=['docker','--context','desktop-linux'];image=(b/'image-id.txt').read_text().strip()
cid=subprocess.check_output(cmd+['create','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=16','--memory=64m',image],text=True).strip()
(b/'created.json').write_text(json.dumps({'image':image,'container':cid})+'\n');i=json.loads(subprocess.check_output(cmd+['inspect',cid],text=True))[0];assert not i['Mounts'] and i['Config']['User']=='501:20'
r=subprocess.run(cmd+['start','-a',cid],text=True,capture_output=True);i=json.loads(subprocess.check_output(cmd+['inspect',cid],text=True))[0]
result={'container':cid,'image':image,'client_exit':r.returncode,'exit_code':i['State']['ExitCode'],'status':i['State']['Status'],'stdout':r.stdout,'stderr':r.stderr,'no_mounts':not i['Mounts'],'readonly_rootfs':i['HostConfig']['ReadonlyRootfs'],'production_installed':False,'execution_authorized':False}
(b/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert r.returncode==0 and i['State']['ExitCode']==0 and i['State']['Status']=='exited'
