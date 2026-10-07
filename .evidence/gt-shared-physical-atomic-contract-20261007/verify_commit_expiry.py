"""Read-only retained-state verification; do not infer historical clocks from rows."""
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO/'services/aos-api'))
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2, parse_signed_capacity_body
from aos_api.aip_provider_capacity_publication_transaction import CAPACITY_ORIGINAL_SOURCE_FACTS_SQL

r = json.loads((BASE/'commit-expiry-verification.json').read_text())
assert r['status'] == 'NONEXECUTING_SOURCE_READ_COMMIT_AFTER_JWT_EXPIRY_OBSERVED'
assert r['original_full_test_exitstatus'] == 0 and r['original_full_test_cleanup_passed']
assert r['commit_calls'] == 1 and r['commit_returned_idle'] and r['expired_fresh_read_rejected']
assert r['fresh_authentication_restored'] and r['execution_allowed'] is False
assert r['read_return']['clock'] < r['authentication_expiry'] < r['before_commit']['clock'] <= r['after_commit']['clock']
assert all(r[n]['xid'] == r['identity']['xid'] and r[n]['pid'] == r['identity']['pid'] for n in ('read_return','before_commit'))
assert r['probe_sha256'] == hashlib.sha256((BASE/'commit_expiry_probe.py').read_bytes()).hexdigest()
for name, sha in r['product_sha256'].items():
    assert hashlib.sha256((REPO/name).read_bytes()).hexdigest() == sha
prefix = re.findall(r'CREATE FUNCTION aos_capacity_publication_private.read_original_source_facts\([^)]*\).*?'
    r'AS \$body\$(.*?)\$body\$;', CAPACITY_ORIGINAL_SOURCE_FACTS_SQL, re.S)
assert len(prefix) == 1
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key, None)
passfile = Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=r['identity']['database'],
        passfile=str(passfile),row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity = c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,"
        "current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone()
    assert identity == dict(database=r['identity']['database'],cluster=r['cluster'],readonly='on')
    signed = c.execute("SELECT s.asset_id,s.revision,s.content_hash,s.source_raw,"
        "aos_ed25519.verify(s.signature,s.source_raw,decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS valid "
        "FROM aos_capacity_publication_private.source_publication s JOIN aos_capacity_publication_private.source_provenance p "
        "USING(org_id,project_id,asset_id)").fetchall()
    assert len(signed) == 1 and signed[0]['valid']
    s = signed[0]; ref = r['source_ref']
    assert (s['asset_id'],s['revision'],s['content_hash']) == (ref['assetId'],ref['revision'],ref['contentHash'])
    raw = bytes(s['source_raw']); assert hashlib.sha256(raw).hexdigest() == s['content_hash']
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    assert source.execution_allowed is False
    fn = c.execute('SELECT prosrc,prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',
        ('aos_capacity_publication_private.read_original_source_facts(text,jsonb,jsonb)',)).fetchone()
    assert fn['prosrc'] == prefix[0] and not fn['prosecdef'] and fn['proconfig'] == ['search_path=pg_catalog']
    assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE proname IN "
        "('read_capacity_source_for_occupation','require_capacity_occupation_source_installation') "
        "OR proname LIKE 'publication_facts_harness_%' OR proname LIKE 'publication_signed_harness_%'").fetchone()['n'] == 0
    flags = c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert flags and not any(flags.values())
    assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole "
        "OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n'] == 0
    counts = {t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in r['product_counts']}
    assert counts == r['product_counts'] and not any(counts.values())
    canary = {t:c.execute('SELECT count(*) AS n FROM '+t+" WHERE org_id='dev-org'").fetchone()['n'] for t in counts}
    assert not any(canary.values())
    assert c.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall() == [dict(epoch=2,head_origin_hash=None)]
result = dict(status='POST_EXPIRY_COMMIT_EXECUTION_AND_RETAINED_NONEXECUTING_STATE_VERIFIED',
    identity=identity, clocks_from_original_probe=True, current_read_only_verification=True,
    product_counts=counts, canary_counts=canary, source_signature_hash_valid=True,
    original_functions_cleaned=True, occupation_role_inert=True,
    file_sha256={n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in
        ('commit_expiry_probe.py','run_commit_expiry_probe_r2.py','commit-expiry-r2.log',
         'commit-expiry-verification.json','verify_commit_expiry.py')},
    limitations=['Successful expired read-transaction COMMIT is not a business admission or send',
        'Full joint finalize must attach an actual-COMMIT deadline gate; it remains unimplemented',
        'Retained state cannot independently reproduce the past clocks or COMMIT'])
(BASE/'commit-expiry-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],identity['database'],'signature valid; cleanup verified; business/canary0')
