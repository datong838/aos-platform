import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / 'services/aos-api/aos_api/extension_runtime/runtime_configuration_candidates.py'
tree = ast.parse(SOURCE.read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'read_candidates')
queries = [n.value for n in ast.walk(function) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.strip().startswith('SELECT')]
assert len(queries) == 1
sql = queries[0]
assert sql.count('%s') == 16

def read(query):
    command = ['docker', '--context', 'colima-aos-extension', 'exec', 'aos-a0v-recovery-pg',
               'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'aos_app',
               '-d', 'aos_current_preview_20260927', '-c',
               'BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY; ' + query + '; COMMIT;']
    return json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=30).stdout)

identity = read("SELECT json_build_object('database',current_database(),'cluster',(SELECT system_identifier::text FROM pg_control_system()),'migration',(SELECT version_num FROM alembic_version),'readOnly',current_setting('transaction_read_only'))")
assert identity['cluster'] == '7683855731447750695'
assert identity['migration'] == 'a0v_159' and identity['readOnly'] == 'on'
counts = {}
for org in ('org-org', 'dev-org'):
    bound = sql % tuple("'" + value + "'" for value in (org, 'dev-project') * 8)
    counts[org] = read('SELECT row_to_json(candidate) FROM (' + bound + ') candidate')
facts = read("SELECT json_build_object('installation',(SELECT json_agg(json_build_object('id',installation_id,'currentRevision',current_revision,'activeRevision',active_revision)) FROM bundle_installation WHERE org_id='org-org' AND project_id='dev-project'),'hostIdentities',(SELECT count(*) FROM extension_runtime_host_identity),'hostAssignments',(SELECT count(*) FROM extension_runtime_host_assignment),'bindings',(SELECT count(*) FROM extension_runtime_binding),'operations',(SELECT count(*) FROM extension_runtime_operation))")
result = {'observedAt': datetime.now(timezone.utc).isoformat(), 'identity': identity,
          'sourceSha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'querySha256': hashlib.sha256(sql.encode()).hexdigest(),
          'counts': counts, 'facts': facts, 'businessExecutionAuthorized': False,
          'limitation': 'Candidate counts do not prove installation binding or live process readiness. Reads are separate snapshots.'}
(ROOT / 'readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
