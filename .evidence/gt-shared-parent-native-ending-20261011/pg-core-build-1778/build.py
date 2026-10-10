import pathlib,json,subprocess,tarfile
root=pathlib.Path('/build/source');root.mkdir()
with tarfile.open('/build/postgresql-16.14.tar.bz2') as t:t.extractall(root)
src=root/'postgresql-16.14';p=src/'src/include/pg_config_manual.h';s=p.read_text();old='#define DEFAULT_PGSOCKET_DIR  "/tmp"';new='#define DEFAULT_PGSOCKET_DIR "/var/run/postgresql"';assert s.count(old)==1;p.write_text(s.replace(old,new))
subprocess.run(['./configure',*json.loads(pathlib.Path('/build/configure-flags.json').read_text())],cwd=src,check=True)
subprocess.run(['make','-j2','world-bin'],cwd=src,check=True)
