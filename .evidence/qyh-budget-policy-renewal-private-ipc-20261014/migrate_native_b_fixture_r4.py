"""Original full migration in the exact new owned test fixture only."""
from pathlib import Path
import json,os,sys,subprocess
P=Path(__file__).resolve().parent
ready=json.loads((P/'native-b-fixture-ready-r4.json').read_text())
D=['docker','--context','colima-aos-extension']
info=json.loads(subprocess.check_output(D+['inspect',ready['cid']],text=True))[0]
assert info['State']['Running'] and info['Config']['Labels']['aos.owner']==ready['owner']
assert len(info['Mounts'])==1 and info['Mounts'][0]['Type']=='tmpfs'
assert not (P/'native-b-migration-intent-r4.json').exists()
(P/'native-b-migration-intent-r4.json').write_text(json.dumps({'cid':ready['cid'],'originalVolumeTouched':False}))
sys.path.insert(0,str(P/'native-b-public-r4-latest/services/aos-api'))
os.environ.update(AOS_DATABASE_URL=f"postgresql://aos_app@127.0.0.1:{ready['port']}/postgres",AOS_DOTENV_DISABLED='1',AOS_TEST_RETAIN_DATABASE='1')
os.environ.pop('AOS_TEST_USE_SHARED_DATABASE',None)
from tests.conftest import _isolated_postgres_database
from aos_api.db import get_dsn
import psycopg
from psycopg.conninfo import conninfo_to_dict
fixture=_isolated_postgres_database.__wrapped__();next(fixture)
dsn=get_dsn();parts=conninfo_to_dict(dsn)
assert parts['host']=='127.0.0.1' and int(parts['port'])==ready['port']
assert parts['dbname'].startswith('aos_test_')
with psycopg.connect(dsn) as conn:
    revision=conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    assert revision=='a0v_162'
    count=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]
(P/'native-b-migration-ready-r4.json').write_text(json.dumps({'cid':ready['cid'],'database':parts['dbname'],'revision':revision,'tables':count,'originalVolumeTouched':False}))
try:next(fixture)
except StopIteration:pass
print(json.dumps({'migration':revision,'tables':count,'ownedFixtureOnly':True}))
