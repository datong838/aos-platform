"""Independent read-only retained test ledger verification."""
from pathlib import Path
import json,tempfile,hashlib
import psycopg
from psycopg.rows import dict_row
b=Path(__file__).resolve().parent;r=json.loads((b/'eval-hold-hash-native-green.json').read_text());assert r['pytest_exit']==0
p=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass';assert p.stat().st_mode&0o077==0
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=r['database'],passfile=str(p),row_factory=dict_row) as c:
 c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
 cluster=c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'];assert cluster=='7693564235776004128'
 counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ('aip_model_eval_budget_reservation','aip_model_eval_budget_reservation_bucket','aip_agent_run','aip_model_capacity_reservation')};assert all(n==0 for n in counts.values())
 exposure=c.execute('SELECT coalesce(sum(held_minor+submitted_minor+unknown_minor),0) AS amount FROM aip_budget_bucket').fetchone()['amount'];assert exposure==0
 c.rollback()
(b/'independent-readback.json').write_text(json.dumps(dict(database=r['database'],cluster=cluster,counts=counts,exposure_minor=int(exposure),provider_calls=0,isolation='serializable read only'),indent=2)+'\n')
print(json.dumps(dict(verified=True,exposure_minor=int(exposure))))
