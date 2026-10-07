"""Read-only native probe of historical issuance authentication, never replay it."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

os.environ['AOS_DOTENV_DISABLED'] = '1'
sys.path.insert(0, str(Path.cwd() / 'services/aos-api'))
import psycopg
from psycopg.rows import dict_row

base = Path('.evidence/gt-capacity-source-entry-20261007')
prior = json.loads((base / 'full157-current-consumer-next-investigation.json').read_text())
database = prior['database']
assert re.fullmatch(r'aos_test_[a-z0-9_]+_ti4_test', database)
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
password = passfile.read_text().strip().split(':')[-1]
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert head == prior['head']
with psycopg.connect(host='127.0.0.1', port=5434, dbname=database,
                      user='aos_app', password=password, row_factory=dict_row) as conn:
    conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
    conn.execute("SET LOCAL statement_timeout='5s'")
    conn.execute("SET LOCAL lock_timeout='2s'")
    conn.execute("SET LOCAL TimeZone='UTC'")
    conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
    identity = conn.execute("SELECT current_database() AS db,system_identifier::text AS cluster,"
        "current_setting('transaction_read_only') AS read_only "
        "FROM pg_control_system()").fetchone()
    assert identity == {'db': database, 'cluster': '7693564235776004128', 'read_only': 'on'}
    conn.execute('SET LOCAL ROLE aos_capacity_publication_owner')
    statement = """SELECT p.source_raw,p.signature,p.content_hash,s.command_raw,s.finalized,
        encode(sha256(p.source_raw),'hex') AS actual_hash,
        aos_ed25519.verify(p.signature,p.source_raw,
          decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS valid_signature,
        s.native_xid::text AS xid,s.native_pid,s.native_session,
        v.native_xid::text AS provenance_xid,v.native_pid AS provenance_pid,
        v.native_session AS provenance_session,clock_timestamp() AS checked_at
      FROM aos_capacity_publication_private.source_publication p
      JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
      JOIN aos_capacity_publication_private.source_provenance v
        ON v.org_id=p.org_id AND v.project_id=p.project_id AND v.asset_id=p.asset_id
      WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.asset_id=%s"""
    before = conn.execute(statement, (prior['asset_id'],)).fetchone()
    assert before and before['finalized'] and before['valid_signature']
    assert before['content_hash'] == before['actual_hash'] == prior['source_hash']
    for k, p in [('xid', 'provenance_xid'), ('native_pid', 'provenance_pid'),
                  ('native_session', 'provenance_session')]:
        assert before[k] == before[p]
    command = json.loads(bytes(before['command_raw']))
    source = json.loads(bytes(before['source_raw']))
    from datetime import datetime, timedelta
    expiry = datetime.fromisoformat(command['authentication']['authenticationExpiresAt'].replace('Z', '+00:00'))
    assert expiry <= before['checked_at']
    conn.execute('SAVEPOINT old_issuance_parser_probe')
    denial = None
    try:
        conn.execute('SELECT aos_capacity_publication_private.read_source_command(%s)',
                     (bytes(before['command_raw']),)).fetchone()
    except psycopg.Error as error:
        denial = {'sqlstate': error.sqlstate, 'reason': error.diag.message_primary}
    finally:
        conn.execute('ROLLBACK TO SAVEPOINT old_issuance_parser_probe')
    assert denial == {'sqlstate': '22023', 'reason': 'CAPACITY_SOURCE_COMMAND_REQUIRED'}
    # Unsigned in-memory input to the pure parser only: establish single cause.
    # Never pass it to fact readers, a signer, publication or a consumer.
    import copy
    from aos_api.asset_registry.canonical_json import canonical_json
    parser_control = copy.deepcopy(command)
    parser_control['authentication']['authenticationExpiresAt'] = (
        before['checked_at'] + timedelta(minutes=5)).isoformat().replace('+00:00', 'Z')
    original_expiry = command['authentication']['authenticationExpiresAt']
    changed_expiry = parser_control['authentication']['authenticationExpiresAt']
    parser_control['authentication']['authenticationExpiresAt'] = original_expiry
    assert parser_control == command
    parser_control['authentication']['authenticationExpiresAt'] = changed_expiry
    control = conn.execute('SELECT aos_capacity_publication_private.read_source_command(%s) AS packet',
                           (canonical_json(parser_control),)).fetchone()
    assert control['packet'] == parser_control
    after = conn.execute(statement, (prior['asset_id'],)).fetchone()
    assert {k: v for k, v in before.items() if k != 'checked_at'} == {
        k: v for k, v in after.items() if k != 'checked_at'}
    conn.rollback()

paths = ['services/aos-api/aos_api/aip_provider_capacity_publication_transaction.py',
         'services/aos-api/aos_api/aip_provider_capacity_source_issuer.py']
result = {'schema': 'aos-consumer-historical-auth-native-probe/v1', 'head': head,
          'authority': prior['authority'], 'database': database, 'identity': identity,
          'asset_id': prior['asset_id'], 'source_hash': before['actual_hash'],
          'source_signature_native_valid': before['valid_signature'],
          'source_finalized': before['finalized'], 'historical_provenance_matches': True,
          'historical_auth_expired': True, 'original_parser_denial': denial,
          'single_variable_unsigned_parser_control_accepted': True,
          'parser_control_is_authentication_or_authority': False,
          'source_fingerprint_unchanged': True, 'transaction_rolled_back': True,
          'checked_at': before['checked_at'].isoformat(),
          'source_expiry': source['validUntil'],
          'files': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
          'consumer_positive_proven': False,
          'conclusion': 'Original issuance parser cannot be reused for later consumption; '
                        'consumer must independently authenticate current caller and recheck '
                        'current originals while preserving historical signed provenance.'}
serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
assert password not in serialized and not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.', serialized)
(base / 'full157-consumer-currentness-native-probe.json').write_text(serialized)
print(json.dumps({'native_expired_auth_denial': denial, 'source_preserved': True,
                  'consumer_positive_proven': False}))
