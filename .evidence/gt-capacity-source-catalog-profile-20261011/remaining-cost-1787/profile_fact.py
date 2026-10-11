"""Read-only instrumentation of the complete fixed FACT body; no installation."""
import datetime
import hashlib
import json
from pathlib import Path

import psycopg
from aos_api import aip_provider_capacity_catalog_audit_profile as profile

target = Path(__file__).with_name('fact-segments-r2.json')
assert not target.exists(), 'Preserve previous attempt'
original = profile.catalog_fact_body()
lines = original.splitlines()
instrumented = []
markers = []
for line in lines:
    if line == 'DECLARE':
        instrumented.extend([line, ' profile_started timestamptz;'])
        continue
    if line == 'BEGIN':
        instrumented.extend([line, ' profile_started := clock_timestamp();'])
        continue
    if line.startswith((' IF ', ' FOREACH ')) or line == 'END ' or line == 'END':
        label = f'segment_{len(markers):02d}'
        markers.append({'label': label, 'next_statement': line})
        instrumented.append(" RAISE NOTICE '" + label + " %', extract(epoch FROM clock_timestamp()-profile_started)*1000;")
    instrumented.append(line)
body = '\n'.join(instrumented)
notices = []
result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'body_sha256': hashlib.sha256(original.encode()).hexdigest(),
          'markers': markers, 'rounds': [],
          'limitations': ['DO includes fresh parsing; not a cached production function.',
                         'Admin invoker; role privilege checks still use original explicit Owner.',
                         'No Source, expiration refresh, function installation or business write.']}
conn = psycopg.connect('host=127.0.0.1 port=5441 dbname=aos_test_83510ad98496_ti4_test user=aos_app passfile=/Users/ddt/.aos-lab-secrets/aos-source-desktop-shm-20261009/pgpass', autocommit=True)
conn.add_notice_handler(lambda diagnostic: notices.append(diagnostic.message_primary))
try:
    conn.execute('SET default_transaction_read_only=on')
    conn.execute('SET search_path=pg_catalog')
    conn.execute("SET statement_timeout='10s'")
    for index in range(5):
        notices.clear()
        conn.execute('DO $instrumented$' + body + '$instrumented$')
        result['rounds'].append({'index': index, 'notices': list(notices)})
    result['status'] = 'RETURNED'
except Exception as error:
    result.update(status='REJECTED', error=str(error), notices=list(notices))
finally:
    conn.close()
    target.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
