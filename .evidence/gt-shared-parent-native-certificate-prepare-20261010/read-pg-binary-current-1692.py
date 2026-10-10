from pathlib import Path
import subprocess,json,re
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';name='aos-source-desktop-shm-20261009';dc=['docker','--context','desktop-linux']
def run(args):return subprocess.check_output([*dc,*args],text=True,timeout=25).strip()
id,image,running=run(['inspect','--format','{{.Id}} {{.Image}} {{.State.Running}}',name]).split();assert id=='8d2a50eb82cd8e5a8feea0ee647ad63090edb685416c777fcf9deafa9b877d3f' and running=='true'
meta=json.loads(run(['image','inspect','--format','{{json .RepoDigests}}',image]));ldd=run(['exec',name,'ldd','/usr/local/bin/postgres']);libs=sorted(set(re.findall(r'(/[^\s()]+)',ldd)));assert all(p.startswith(('/usr/lib/','/lib/')) for p in libs)
hashes=run(['exec',name,'sha256sum','/usr/local/bin/postgres',*libs]);files={}
for line in hashes.splitlines():h,p=line.split(maxsplit=1);assert re.fullmatch('[a-f0-9]{64}',h);files[p.strip()]=h
assert len(files)==len(libs)+1
out=dict(authority='AOS-001692',container=id,image=image,image_repo_digests=meta,ldd_output=ldd,file_sha256=files,read_only_installation_observation=True,release_signature_verified=False,official_kernel_source_binary_match_verified=False,formal_installation_approved=False,execution_allowed=False)
(B/'pg-binary-current-1692.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(image=image,image_repo_digests=meta,exact_binary_and_library_files=len(files),formal_installation_approved=False),indent=2))
