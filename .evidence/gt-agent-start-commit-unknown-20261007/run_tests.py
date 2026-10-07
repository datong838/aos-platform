"""Run scoped tests with retained owned PG and an existing private passfile."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

base=Path(__file__).resolve().parent
assert len(sys.argv)>2 and Path(sys.argv[1]).name==sys.argv[1]
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
env={k:v for k,v in os.environ.items() if k not in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS')}
env.update(PGPASSFILE=str(passfile),AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5434/aos_meta',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5434',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',
    AOS_TEST_RETAIN_DATABASE='1',AOS_DOTENV_DISABLED='1')
with (base/sys.argv[1]).open('w') as out:
    r=subprocess.run(['services/aos-api/.venv/bin/python','-m','pytest',*sys.argv[2:],'-q','-s'],env=env,stdout=out,stderr=subprocess.STDOUT)
print('Owned retained tests exit',r.returncode)
raise SystemExit(r.returncode)
