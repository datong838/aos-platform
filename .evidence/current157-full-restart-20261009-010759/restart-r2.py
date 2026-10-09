"""One journalled restart of the original preview volume, no DDL or execution."""
import hashlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql

E = Path(__file__).resolve().parent
R = E.parents[1]
HEAD = '0706f359ec344bf202bd155231d718fc01805e7c'
TASK = E.name
CTX = 'colima-aos-extension'
SOURCE = 'aos-a0v-recovery-pg'
ID = '9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'
IMAGE = 'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
EVENT = '2026-10-09T01:07:59.537Z'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, R / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


memory = load('full_restart_memory', 'scripts/memory/memoryctl.py')
maint = load('full_restart_process', 'scripts/a0v_current_142_maintenance.py')
bootstrap = load('full_restart_connection', 'scripts/a0v_current_preview_bootstrap.py')
g = load('full_restart_snapshot', 'scripts/a0v_current_142_restore_gate.py')


def save(name, value):
    with os.fdopen(os.open(E / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as out:
        json.dump(value, out, indent=2, default=str)
        out.flush()
        os.fsync(out.fileno())
    fd = os.open(E, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def guard():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip() == HEAD
    assert subprocess.check_output(['git', 'branch', '--show-current'], cwd=R, text=True).strip() == 'm1'
    assert memory.load_authority()['project_revision'] == 'AOS-001618'
    task = json.loads((E / 'task.json').read_text())
    assert task['owner'] == maint.OWNER and task['status'] == 'ACTIVE'
    assert datetime.fromisoformat(task['lease_expires_at']) > datetime.now(timezone.utc)
    leases = memory.load_leases(memory.DEFAULT_PATHS)['leases']
    assert [x for x in leases if x['task_id'] == TASK] == [task]
    assert json.loads((memory.DEFAULT_PATHS.receipts_path / 'tasks' / (TASK + '.json')).read_text()) == task
    assert not (memory.DEFAULT_PATHS.receipts_path / 'deliveries' / (TASK + '.json')).exists()
    for other in leases:
        if other['task_id'] != TASK:
            assert not memory.scopes_overlap(task['scope'], other['scope'])
    item = json.loads(subprocess.check_output(['docker', '--context', CTX, 'inspect', SOURCE], timeout=15))[0]
    maint.require_source(item)
    assert item['Id'] == ID and item['Image'] == IMAGE
    return item


def snapshot():
    parameters = bootstrap._connection_parameters()
    assert (parameters['host'], parameters['port'], parameters['dbname']) == (
        '127.0.0.1', 18435, 'aos_current_preview_20260927')
    with psycopg.connect(**parameters) as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
        conn.execute("SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public")
        public = g.snapshot(lambda statement: conn.execute(statement).fetchone()[0])
        assert public['version'] == 'a0v_157'
        names = conn.execute("""SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n
          ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p') AND n.nspname<>'information_schema'
          AND n.nspname NOT LIKE 'pg_%' ORDER BY n.nspname,c.relname""").fetchall()
        all_data = {}
        for start in range(0, len(names), 40):
            statements = []
            for namespace, name in names[start:start+40]:
                statements.append(sql.SQL("SELECT {} AS name,count(*) AS count,"
                  "encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS sha256 "
                  "FROM (SELECT encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') AS h FROM {} t) hashes"
                  ).format(sql.Literal(namespace + '.' + name), sql.Identifier(namespace, name)))
            for name, count, digest in conn.execute(sql.SQL(' UNION ALL ').join(statements)).fetchall():
                all_data[name] = {'count': count, 'sha256': digest}
        conn.rollback()
    return {'public': public, 'all_schema_data': all_data}


def preflight(argv, cwd, env, name):
    result = subprocess.run(argv[:-1], cwd=cwd, env=env, capture_output=True, timeout=60)
    save(name, {'exit_code': result.returncode, 'stdout': result.stdout.decode(),
                'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()})
    assert result.returncode == 0, 'Signed startup preflight failed'
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report['outcome'] == 'CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN'
    assert report['codeVersion'] == report['version'] == 'a0v_157'
    assert report['database'] == 'aos_current_preview_20260927' and report['runtimeBindings'] == 0
    return report


def listener(port):
    return subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'],
                          capture_output=True, text=True, timeout=10).stdout.strip()


def start_service(service):
    guard()
    assert not listener(service['port'])
    save(f"start-{service['port']}-intent.json", {k: service[k] for k in ('argv', 'cwd', 'port')})
    with os.fdopen(os.open(E / f"service-{service['port']}.log", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as out:
        process = subprocess.Popen(service['argv'], cwd=service['cwd'], env=service['env'],
                                   stdout=out, stderr=out, start_new_session=True)
    save(f"start-{service['port']}-pid.json", {'pid': process.pid})
    for _ in range(100):
        assert process.poll() is None, 'New process exited; reconcile, never blindly restart'
        try:
            path = '/v1/ready' if service['port'] == 8080 else '/'
            with urllib.request.urlopen(f"http://127.0.0.1:{service['port']}" + path, timeout=2) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        time.sleep(.2)
    else:
        raise RuntimeError('New service readiness timed out')
    fingerprint = maint.read_service_candidate(pid=process.pid, expected_argv=service['argv'],
        expected_cwd=service['cwd'], expected_port=service['port'], expected_child_argv=service['helper_argv'])
    save(f"start-{service['port']}-done.json", {'fingerprint': fingerprint})
    return {'fingerprint': fingerprint, **{k: service[k] for k in ('argv', 'cwd', 'port', 'helper_argv')}}


stage='resume_known_preparation'
try:
    assert json.loads((E/'failure.json').read_text())['stage']=='preparation'
    assert not list(E.glob('stop-*-intent.json')) and not (E/'restart-pg-intent.json').exists()
    original_pg=guard()
    frozen=json.loads((E/'frozen-source.json').read_text());assert frozen['head']==HEAD
    root=Path(frozen['root'])
    for name,digest in frozen['files'].items():
        data=(root/name).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==digest
    previous=json.loads((R/'.evidence/current157-full-restart-20261008-010137/web-repair-r2/result.json').read_text())
    originals=json.loads((R.parent/'aos-recovery/current157-fac006c02b6e/current-window-70b9d977b3d6/original-services.json').read_text())
    services=[]
    for descriptor in previous['services']:
        service=dict(descriptor)
        original=next(x for x in originals if x['port']==service['port'])
        env=original['environment'];assert set(env)<= {'PATH','PYTHONUNBUFFERED','VITE_AOS_API_PROXY_TARGET'}
        service['environment']=env
        observed=maint.read_service_candidate(pid=service['fingerprint']['pid'],expected_argv=service['argv'],expected_cwd=service['cwd'],expected_port=service['port'],expected_child_argv=service['helper_argv'])
        assert observed['started']==service['fingerprint']['started']
        services.append(service|{'fingerprint':observed})
    base_env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'LANG') if k in os.environ}
    new_api = services[0] | {'argv': [services[0]['argv'][0], str(root / 'scripts/a0v_current_preview_http.py'),
                                     *services[0]['argv'][2:]], 'env': base_env | services[0]['environment']}
    new_web = services[1] | {'cwd': str(root / 'apps/web'), 'env': base_env | services[1]['environment']}
    signed = preflight(new_api['argv'], new_api['cwd'], new_api['env'], 'signed-preflight-before.json')
    before = snapshot()
    save('before-data.json', before)
    save('preflight.json', {'signed': signed, 'source_id': ID, 'source_started': original_pg['State']['StartedAt'],
         'volume': 'aos-a0v-recovery-pg-data', 'all_user_table_count': len(before['all_schema_data']),
         'migration_needed': False, 'uncommitted_158_excluded': True})
    guard()
    stage = 'stop_clients'
    for service in services:
        guard()
        observed = maint.read_service_candidate(pid=service['fingerprint']['pid'], expected_argv=service['argv'],
            expected_cwd=service['cwd'], expected_port=service['port'], expected_child_argv=service['helper_argv'])
        maint.require_process(service['fingerprint'], observed, executor_pid=os.getpid())
        save(f"stop-{service['port']}-intent.json", observed)
        os.kill(observed['pid'], signal.SIGTERM)
        for _ in range(100):
            if not listener(service['port']):
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Original listener did not stop')
        for child in observed['children']:
            state = subprocess.run(['ps', '-p', str(child['pid']), '-o', 'stat='], capture_output=True, text=True)
            assert state.returncode != 0 or state.stdout.strip().startswith('Z'), 'Original helper still running'
        save(f"stop-{service['port']}-done.json", {'port_free': True})
    stage = 'restart_original_pg'
    assert guard()['State']['StartedAt'] == original_pg['State']['StartedAt']
    save('restart-pg-intent.json', {'id': ID, 'original_started': original_pg['State']['StartedAt'], 'volume': 'aos-a0v-recovery-pg-data'})
    result = subprocess.run(['docker', '--context', CTX, 'restart', SOURCE], capture_output=True, timeout=60)
    save('restart-pg-terminal.json', {'exit_code': result.returncode, 'stdout': result.stdout.decode()})
    assert result.returncode == 0, 'PG restart result requires reconciliation'
    for _ in range(30):
        ready = subprocess.run(['docker', '--context', CTX, 'exec', SOURCE, 'pg_isready', '-U', 'aos_app'], capture_output=True, timeout=5)
        if ready.returncode == 0:
            break
        time.sleep(.5)
    else:
        raise RuntimeError('Original PG not ready')
    now_pg = guard()
    assert now_pg['State']['StartedAt'] != original_pg['State']['StartedAt']
    assert snapshot() == before
    save('restart-pg-done.json', {'id': ID, 'started': now_pg['State']['StartedAt'], 'all_data_unchanged': True})
    stage = 'restart_api'
    preflight(new_api['argv'], new_api['cwd'], new_api['env'], 'signed-preflight-after-pg.json')
    api = start_service(new_api)
    stage = 'restart_web'
    web = start_service(new_web)
    stage = 'after_restart'
    after = snapshot()
    assert before == after
    save('after-data.json', after)
    save('result.json', {'status': 'ORIGINAL157_PG_LATEST0706_API_WEB_RESTART_GREEN_BROWSER_PENDING',
         'event': EVENT, 'head': HEAD, 'source_id': ID, 'volume': 'aos-a0v-recovery-pg-data',
         'pg_started': now_pg['State']['StartedAt'], 'services': [api, web], 'signed_preflight': signed,
         'all_user_table_count': len(after['all_schema_data']), 'all_data_and_public_catalog_unchanged': True,
         'host_worker_provider_off': True, 'migration_attempted': False, 'business_first_chain': False})
    print('ORIGINAL157_PG_LATEST0706_API_WEB_RESTART_GREEN_BROWSER_PENDING', flush=True)
except Exception as error:
    if not (E / 'failure-r2.json').exists():
        save('failure-r2.json', {'stage': stage, 'type': type(error).__name__, 'reconcile_only': True})
    raise
