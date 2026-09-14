"""Single read-only business-window aggregate, never identity or financial export."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import subprocess
import sys
from time import monotonic
import warnings

logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')
_path = Path(__file__).with_name('audit-real-customer-reference-origin.py')
_spec = importlib.util.spec_from_file_location('existing_source_audit', _path)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

WINDOW = """CASE WHEN p.create_time IS NULL OR p.create_time<=0 THEN 'unknown'
 WHEN p.create_time>%s THEN 'future' WHEN p.create_time>=%s THEN 'last30days'
 ELSE 'earlier' END"""
STATE = "CASE WHEN p.is_delete=0 THEN 'active' WHEN p.is_delete=1 THEN 'deleted' ELSE 'unknown' END"
QUERIES = {
    'Order': 'SELECT '+STATE+' AS parentState,'+WINDOW+''' AS businessWindow,
        COUNT(*) AS rowsObserved,
        COALESCE(SUM(p.member_id>0 AND m.member_id IS NULL),0) AS missingCustomerRows,
        MIN(CASE WHEN p.create_time>0 THEN p.create_time END) AS minCreatedUnix,
        MAX(CASE WHEN p.create_time>0 THEN p.create_time END) AS maxCreatedUnix
        FROM ns_order p LEFT JOIN ns_member m ON m.member_id=p.member_id
        WHERE p.site_id=%s GROUP BY parentState,businessWindow ORDER BY parentState,businessWindow''',
    'OrderLine': "SELECT CASE WHEN p.order_id IS NULL THEN 'missing-parent' ELSE "+STATE+' END AS parentState,'+WINDOW+''' AS businessWindow,
        COUNT(*) AS rowsObserved,
        COALESCE(SUM(g.create_time IS NULL OR g.create_time<=0),0) AS ownCreatedUnknownRows
        FROM ns_order_goods g LEFT JOIN ns_order p ON p.order_id=g.order_id AND p.site_id=g.site_id
        WHERE g.site_id=%s GROUP BY parentState,businessWindow ORDER BY parentState,businessWindow''',
    'Product': """SELECT CASE WHEN is_delete=1 THEN 'deleted' WHEN is_delete=0 AND goods_state=1 THEN 'active'
        WHEN is_delete=0 AND goods_state=0 THEN 'off-shelf' ELSE 'unknown' END AS productState,
        COUNT(*) AS rowsObserved FROM ns_goods WHERE site_id=%s GROUP BY productState ORDER BY productState""",
}


def audit():
    destination=Path(__file__).with_name('real-business-window-20260914.json')
    if destination.exists(): raise ValueError('immutable diagnostic output already exists')
    output=subprocess.run(['docker','--context','colima-aos-extension','exec','-i','aos-a0v-recovery-pg','sh','-c',
        'exec psql -U "$POSTGRES_USER" -d aos_meta_head -X -t -A -v ON_ERROR_STOP=1'],
        input=base.METADATA_QUERY,text=True,capture_output=True,check=True,timeout=15).stdout
    values=[json.loads(line) for line in output.splitlines() if line.startswith('{')]
    if len(values)!=1:raise ValueError('exact current source required')
    config=base.normalize_source_connection_config('jdbc-mysql-ssh',
        {key:value for key,value in values[0].items() if key in base.SOURCE_CONNECTION_FIELDS})
    started=datetime.now(timezone.utc);cutoff=int(started.timestamp());start=cutoff-30*86400
    clock=monotonic();results={}
    with base.JdbcConnectorRuntime(config,reuse_cache=False) as runtime:
        with runtime._standalone_lease:
            with runtime._conn.cursor() as cursor:cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            with runtime._read_only_transaction():
                with runtime._conn.cursor() as cursor:
                    cursor.execute("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('ns_order','ns_order_goods','ns_member','ns_goods')")
                    engines=cursor.fetchall()
                    if len(engines)!=4 or any(row['ENGINE']!='InnoDB' for row in engines):raise ValueError('InnoDB scope required')
                    for name,query in QUERIES.items():
                        if monotonic()-clock>30:raise TimeoutError('diagnostic deadline')
                        cursor.execute(query,(1,) if name=='Product' else (cutoff,start,1))
                        rows=cursor.fetchall()
                        if len(rows)>16:raise ValueError('bounded aggregate cardinality required')
                        results[name]=[{key:value if key in ('parentState','businessWindow','productState') or value is None else int(value)
                            for key,value in row.items()} for row in rows]
    if monotonic()-clock>30:raise TimeoutError('diagnostic deadline')
    for name,rows in results.items():
        for row in rows:
            if row['rowsObserved']<0:raise ValueError('nonnegative aggregate required')
            for key in ('missingCustomerRows','ownCreatedUnknownRows'):
                if key in row and not 0<=row[key]<=row['rowsObserved']:raise ValueError('aggregate count exceeds rows')
    report=dict(schemaVersion='aos.developer-business-window-aggregate/v1',
        tenant={'orgId':'org-org','projectId':'dev-project'},siteId=1,
        startedAt=started.isoformat(),completedAt=datetime.now(timezone.utc).isoformat(),elapsedSeconds=round(monotonic()-clock,3),
        windowStartUnix=start,windowEndUnix=cutoff,windowBoundaries='inclusive-start-inclusive-end',
        orderLineWindowBasis='existing-same-site-parent-order-created-time',
        accessMode='read-only',isolation='repeatable-read',tableEngines='InnoDB',
        sourceRoute='current-P02-meta-source-configuration',identifiersExported=False,businessWrites=False,
        formalFulfillment=False,historicalSnapshotClaim=False,
        queryHash='sha256:'+hashlib.sha256(json.dumps(QUERIES,sort_keys=True).encode()).hexdigest(),results=results)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:audit()
    except Exception as exc:
        print('BUSINESS_WINDOW_AUDIT_FAILED:'+type(exc).__name__)
        sys.exit(1)
