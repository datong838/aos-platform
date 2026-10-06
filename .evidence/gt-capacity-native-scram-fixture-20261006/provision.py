"""Task-specific new isolated test fixture; no existing container mutation."""
import json, os, secrets, socket, subprocess, tempfile
from pathlib import Path
C='aos-capacity-publication-scram-20261006'
IMAGE='sha256:a0eb61b312f90f7c5891afc088edc2824ae8eae1dd21ab8ba0e3ef78b1027eb8'
PREFIX=['docker','--context','colima-aos-a0v-test-only']
def run(*args):
 return subprocess.run(PREFIX+list(args),capture_output=True,text=True,check=True).stdout.strip()
assert run('image','inspect','--format','{{.Id}}',IMAGE)==IMAGE
for kind,name in [('container',C),('volume',C+'-data'),('network',C+'-network')]:
 result=subprocess.run(PREFIX+[kind,'inspect',name],capture_output=True)
 assert result.returncode!=0, 'existing resource requires read-only reconciliation: '+name
with socket.socket() as sock:sock.bind(('127.0.0.1',5434))
label='aos.task=gt-capacity-native-scram-fixture-20261006'
run('volume','create','--label',label,C+'-data')
run('network','create','--internal','--label',label,C+'-network')
password=secrets.token_urlsafe(32)
fd,raw=tempfile.mkstemp(prefix='aos-capacity-scram-',suffix='.env');os.fchmod(fd,0o600)
with os.fdopen(fd,'w') as handle:
 handle.write('POSTGRES_USER=aos_app\nPOSTGRES_DB=aos_meta\nPOSTGRES_PASSWORD='+password+'\nPOSTGRES_HOST_AUTH_METHOD=scram-sha-256\n')
try:
 ident=run('run','-d','--name',C,'--label',label,'--memory','256m','--network',C+'-network','-p','127.0.0.1:5434:5432','-v',C+'-data:/var/lib/postgresql/data','--env-file',raw,IMAGE)
 # Dedicated temporary local test passfile is needed for future test invocations;
 # password never appears in logs/command arguments/evidence.
 fp=Path(tempfile.gettempdir())/(C+'.pgpass')
 assert not fp.exists()
 fd=os.open(fp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as handle:handle.write('127.0.0.1:5434:*:aos_app:'+password+'\n')
 info={'container':C,'id':ident,'image':IMAGE,'volume':C+'-data','internal_network':C+'-network','host':'127.0.0.1','port':5434,'memory_bytes':268435456,'test_only':True,'password_logged':False,'formal_database_accessed':False,'retained':True}
 Path(__file__).with_name('provision.json').write_text(json.dumps(info,indent=2)+'\n')
 print('New isolated fixture created; test password retained only in temporary0600 passfile')
finally:os.unlink(raw)
