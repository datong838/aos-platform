import pathlib,json,subprocess,tarfile
root=pathlib.Path('/build/source');root.mkdir()
with tarfile.open('/build/postgresql-16.14.tar.bz2') as t:t.extractall(root)
src=root/'postgresql-16.14';p=src/'src/include/pg_config_manual.h';s=p.read_text();old='#define DEFAULT_PGSOCKET_DIR  "/tmp"';new='#define DEFAULT_PGSOCKET_DIR "/var/run/postgresql"';assert s.count(old)==1;p.write_text(s.replace(old,new))
sdk=pathlib.Path('/usr/local/include');park=pathlib.Path('/build/preexisting-sdk');assert sdk.is_dir() and not park.exists();sdk.rename(park)
try:
    subprocess.run(['./configure',*json.loads(pathlib.Path('/build/configure-flags.json').read_text())],cwd=src,check=True)
finally:
    park.rename(sdk)
global_text=(src/'src/Makefile.global').read_text();include_lines=[x for x in global_text.splitlines() if x.startswith(('INCLUDES =','CPPFLAGS ='))];print(json.dumps({'preexisting_include_parked_only_during_configure':True,'sdk_restored':sdk.is_dir(),'generated_include_lines':include_lines}))
subprocess.run(['make','-j2','world-bin'],cwd=src,check=True)
