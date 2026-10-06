"""Use only newly generated test admin secret, never global PG environment."""
import os, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import quote
p=Path(__file__).parent
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
password=passfile.read_text().strip().split(':')[-1]
env={k:v for k,v in os.environ.items() if k not in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS')}
env.update(AOS_DATABASE_URL='postgresql://aos_app:'+quote(password,safe='')+'@127.0.0.1:5434/aos_meta',AOS_DOTENV_DISABLED='1',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0')
log=sys.argv[1]; tests=sys.argv[2:]
assert Path(log).name==log and tests
with (p/log).open('w') as out:
 result=subprocess.run(['services/aos-api/.venv/bin/python','-m','pytest',*tests,'-q','-s'],env=env,stdout=out,stderr=subprocess.STDOUT)
print('Isolated same-database tests exit',result.returncode)
raise SystemExit(result.returncode)
