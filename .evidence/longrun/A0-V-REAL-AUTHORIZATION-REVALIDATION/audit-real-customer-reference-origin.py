"""Developer diagnostic: only scoped aggregate counts; never customer identifiers."""
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
from time import monotonic
import warnings

logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'services/aos-api'))
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.source_connection_config import SOURCE_CONNECTION_FIELDS, normalize_source_connection_config

METADATA_QUERY = """BEGIN READ ONLY;
SELECT s.props::text FROM meta_source s JOIN meta_pipeline p
 ON p.source_id=s.id AND p.org_id=s.org_id AND p.project_id=s.project_id
 WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.id='P02-product-qyh';
COMMIT;"""
AGGREGATES = """
COUNT(*) AS parentRows,
COUNT(DISTINCT CASE WHEN p.member_id>0 THEN p.member_id END) AS distinctPositiveReferences,
COALESCE(SUM(p.member_id IS NULL OR p.member_id<=0),0) AS invalidReferences,
COALESCE(SUM(p.member_id>0 AND m.member_id IS NULL),0) AS sourceMemberAbsent,
COUNT(DISTINCT CASE WHEN p.member_id>0 AND m.member_id IS NULL THEN p.member_id END) AS distinctAbsentReferences,
COALESCE(SUM(p.member_id>0 AND m.member_id IS NOT NULL AND m.site_id=1),0) AS sameSiteMember,
COALESCE(SUM(p.member_id>0 AND m.member_id IS NOT NULL AND m.site_id<>1),0) AS otherSiteMember,
COUNT(DISTINCT CASE WHEN p.member_id>0 AND m.member_id IS NOT NULL AND m.site_id<>1 THEN p.member_id END) AS distinctOtherSiteReferences,
COALESCE(SUM(p.member_id>0 AND m.member_id IS NOT NULL AND m.site_id IS NULL),0) AS unknownMemberSite,
COALESCE(SUM(p.member_id>0 AND m.member_id IS NOT NULL AND m.is_delete=1),0) AS sourceMemberDeleted,
COALESCE(SUM(p.member_id>0 AND m.member_id IS NOT NULL AND m.status<>1),0) AS sourceMemberInactive
"""
QUERIES = {
    'Order': "SELECT CASE WHEN p.is_delete=1 THEN 'deleted' WHEN p.is_delete=0 THEN 'active' ELSE 'unknown' END AS parentState," + AGGREGATES +
        ' FROM ns_order p LEFT JOIN ns_member m ON m.member_id=p.member_id WHERE p.site_id=%s GROUP BY parentState ORDER BY parentState',
    'ProductReview': "SELECT 'present' AS parentState," + AGGREGATES +
        ' FROM ns_goods_evaluate p LEFT JOIN ns_member m ON m.member_id=p.member_id WHERE p.site_id=%s',
}


def audit():
    destination = Path(__file__).with_name('real-customer-reference-origin-20260914.json')
    if destination.exists(): raise ValueError('immutable diagnostic output already exists')
    output = subprocess.run(['docker','--context','colima-aos-extension','exec','-i','aos-a0v-recovery-pg','sh','-c',
        'exec psql -U "$POSTGRES_USER" -d aos_meta_head -X -t -A -v ON_ERROR_STOP=1'],
        input=METADATA_QUERY, text=True, capture_output=True, check=True, timeout=15).stdout
    values = [json.loads(line) for line in output.splitlines() if line.startswith('{')]
    if len(values)!=1: raise ValueError('exact current source required')
    config = normalize_source_connection_config('jdbc-mysql-ssh', {key:value for key,value in values[0].items() if key in SOURCE_CONNECTION_FIELDS})
    started = datetime.now(timezone.utc); clock = monotonic(); results = {}
    with JdbcConnectorRuntime(config, reuse_cache=False) as runtime:
        with runtime._standalone_lease:
            with runtime._conn.cursor() as cursor: cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            with runtime._read_only_transaction():
                with runtime._conn.cursor() as cursor:
                    cursor.execute("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('ns_order','ns_goods_evaluate','ns_member')")
                    engines = cursor.fetchall()
                    if len(engines)!=3 or any(row['ENGINE']!='InnoDB' for row in engines): raise ValueError('InnoDB scope required')
                    for name, query in QUERIES.items():
                        if monotonic()-clock>30: raise TimeoutError('diagnostic deadline')
                        cursor.execute(query,(1,))
                        rows = cursor.fetchall()
                        if len(rows)>3: raise ValueError('unexpected aggregate cardinality')
                        results[name] = [dict(parentState=row['parentState'], **{key:int(value) for key,value in row.items() if key!='parentState'}) for row in rows]
    if monotonic()-clock>30: raise TimeoutError('diagnostic deadline')
    for rows in results.values():
        for row in rows:
            if row['parentRows']!=sum(row[key] for key in ('invalidReferences','sourceMemberAbsent','sameSiteMember','otherSiteMember','unknownMemberSite')):
                raise ValueError('reference partition inconsistent')
    report = dict(schemaVersion='aos.developer-customer-reference-aggregate/v1', tenant={'orgId':'org-org','projectId':'dev-project'},
        startedAt=started.isoformat(), completedAt=datetime.now(timezone.utc).isoformat(), elapsedSeconds=round(monotonic()-clock,3),
        sourceRoute='current-P02-meta-source-configuration', parentSiteId=1, accessMode='read-only', isolation='repeatable-read',
        tableEngines='InnoDB', customerIdentifiersExported=False, businessWrites=False, formalFulfillment=False,
        queryHash='sha256:'+hashlib.sha256(json.dumps(QUERIES,sort_keys=True).encode()).hexdigest(), results=results)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try: audit()
    except Exception as exc:
        print('CUSTOMER_REFERENCE_AUDIT_FAILED:'+type(exc).__name__)
        sys.exit(1)
