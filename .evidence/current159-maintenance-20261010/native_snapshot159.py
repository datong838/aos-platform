import sys,json
import psycopg
sys.path.insert(0,'/evidence')
from snapshot_all import snapshot
with psycopg.connect(host='/pgsocket',user='aos_app',dbname='aos_current_preview_20260927') as c:
 c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
 assert c.execute('select inet_server_addr()').fetchone()[0] is None
 assert c.execute("select current_setting('transaction_read_only')").fetchone()[0]=='on'
 print(json.dumps(snapshot(c),sort_keys=True),flush=True)
 c.rollback()
