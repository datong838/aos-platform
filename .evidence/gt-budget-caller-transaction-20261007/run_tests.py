"""Retained owned lab schemas; credentials stay in the existing 0600 passfile."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
container=subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()
assert container=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
env={k:v for k,v in os.environ.items() if k not in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS')}
env.update(PGPASSFILE=str(passfile),AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5434/aos_meta',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',
    AOS_EXTENSION_PG_PORT='5434',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',
    AOS_TEST_RETAIN_DATABASE='1',AOS_DOTENV_DISABLED='1')
assert Path(sys.argv[1]).name==sys.argv[1]
template_log = Path(__file__).with_name('green-r1.log')
if template_log.exists():
    templates = re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)', template_log.read_text())
    assert len(templates) == 1
    env['AOS_CONTENT_TEST_TEMPLATE'] = templates[0]
with Path(__file__).with_name(sys.argv[1]).open('w') as out:
    result=subprocess.run(['services/aos-api/.venv/bin/python','-m','pytest',*sys.argv[2:],'-q','-s'],env=env,stdout=out,stderr=subprocess.STDOUT)
print('Owned isolated budget tests exit',result.returncode)
raise SystemExit(result.returncode)
