"""Current-142 maintenance executor under construction.

Mandatory guards, a private journal and full isolated sequencing are implemented.
No production mutation entry point is exposed; source service control is pending.
"""
import json
import os
from pathlib import Path


class MaintenanceBlocked(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise MaintenanceBlocked(reason)


def require_source(item):
    require(item['Name'] == '/aos-a0v-recovery-pg' and item['State']['Running'], 'SOURCE_IDENTITY_DRIFT')
    require(item['Config']['Cmd'] == ['postgres'] and item['Config']['Entrypoint'] == ['docker-entrypoint.sh'], 'SOURCE_COMMAND_DRIFT')
    require(item['HostConfig']['RestartPolicy']['Name'] == 'no'
            and item['HostConfig']['NetworkMode'] == 'bridge', 'SOURCE_RESTART_OR_NETWORK_DRIFT')
    require(item['NetworkSettings']['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18435'}]}, 'SOURCE_PORT_DRIFT')
    mounts = item['Mounts']
    require(len(mounts) == 2, 'SOURCE_MOUNT_DRIFT')
    data = [m for m in mounts if m['Destination'] == '/var/lib/postgresql/data']
    backup = [m for m in mounts if m['Destination'] == '/backup']
    require(len(data) == 1 and data[0]['Type'] == 'volume'
            and data[0].get('Name') == 'aos-a0v-recovery-pg-data' and data[0]['RW'], 'SOURCE_VOLUME_DRIFT')
    require(len(backup) == 1 and backup[0]['Type'] == 'bind' and not backup[0]['RW']
            and backup[0]['Source'] == '/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups', 'SOURCE_BACKUP_MOUNT_DRIFT')


def record_attempt(directory: Path, step: str, evidence: dict):
    require(step in {'stop_clients', 'fence_tcp', 'snapshot_dump', 'independent_restore',
                     'migrate_steps', 'verify', 'restore_tcp', 'restart_clients', 'acceptance'}, 'UNKNOWN_STEP')
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), 'JOURNAL_DIRECTORY_INVALID')
    path = directory / (step + '-attempt.json')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise MaintenanceBlocked('EXISTING_ATTEMPT_RECONCILE_ONLY') from None
    with os.fdopen(fd, 'w') as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    # Persist the directory entry as well as file contents before any mutation.
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def require_window(*, listen_addresses, tcp_exit, other_clients, prepared):
    require(listen_addresses == '' and type(tcp_exit) is int and tcp_exit > 0, 'TCP_EXECUTION_NOT_FENCED')
    require(other_clients == 0 and prepared == 0, 'EXISTING_EXECUTION_NOT_DRAINED')


STEPS = ('stop_clients', 'fence_tcp', 'snapshot_dump', 'independent_restore',
         'migrate_steps', 'verify', 'restore_tcp', 'restart_clients', 'acceptance')


class MaintenanceJournal:
    def __init__(self, directory):
        self.directory = Path(directory)

    def perform(self, step, operation):
        require(step in STEPS, 'UNKNOWN_STEP')
        for prior in STEPS[:STEPS.index(step)]:
            require((self.directory / (prior + '-done.json')).is_file(), 'PRIOR_STEP_UNVERIFIED')
        record_attempt(self.directory, step, {'step': step})
        result = operation()
        require(isinstance(result, dict), 'POSTCONDITION_MISSING')
        path = self.directory / (step + '-done.json')
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return result


def run_isolated(*, backup_state, evidence_directory):
    """Real full sequencer acceptance. Cannot select the current Docker context."""
    import importlib.util
    import io
    import secrets
    import subprocess
    import tempfile
    import time
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('restore142_maintenance', root / 'scripts/a0v_current_142_restore_gate.py')
    g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    backup_state = Path(backup_state).resolve(strict=True)
    require(backup_state.parent == root.parent / 'aos-recovery', 'PRIVATE_BACKUP_PARENT_REQUIRED')
    expected = json.loads((backup_state / 'source.json').read_text())
    require(expected['version'] == 'a0v_135', 'EXACT_RESTORED_135_REQUIRED')
    backup_info = json.loads((backup_state / 'backup.json').read_text())
    require(g.sha(backup_state / 'current-full.dump') == backup_info['sha256'], 'BACKUP_HASH_DRIFT')
    require(g.sha(backup_state / 'globals-no-password.sql') == backup_info['globals_sha256'], 'GLOBALS_HASH_DRIFT')
    config = Config(str(root / 'services/aos-api/alembic.ini'))
    config.set_main_option('script_location', str(root / 'services/aos-api/alembic'))
    require(ScriptDirectory.from_config(config).get_heads() == ['a0v_142'], 'EXACT_CODE_142_REQUIRED')
    state = Path(tempfile.mkdtemp(prefix='.aos-maintenance142-', dir=root.parent / 'aos-recovery'))
    os.chmod(state, 0o700)
    journal = MaintenanceJournal(state)
    ctx = 'colima-aos-a0v-test-only'
    base = ['docker', '--context', ctx]
    names = ['aos-sequence142-' + secrets.token_hex(6) for _ in range(2)]
    tick = time.monotonic()

    def execute(args, data=None, check=True):
        result = subprocess.run(base + args, input=data, capture_output=True, timeout=180)
        require(not check or result.returncode == 0, 'ISOLATED_COMMAND_FAILED')
        return result

    image = json.loads(execute(['inspect', 'aos-e17-b17-acl-pg']).stdout)[0]['Image']
    g.save(state / 'intent.json', {'context': ctx, 'containers': names, 'image': image,
                                 'source_touched': False})

    def ready(name):
        for _ in range(30):
            if execute(['exec', name, 'pg_isready', '-U', 'aos_app', '-d', 'postgres'], check=False).returncode == 0:
                return
            time.sleep(1)
        raise MaintenanceBlocked('ISOLATED_SERVER_NOT_READY')

    def pg(name, statement, database='postgres', tcp=False, check=True):
        return execute(['exec', name, 'psql', '-U', 'aos_app', '-d', database, '-Atq', '-v', 'ON_ERROR_STOP=1']
                       + (['-h', '127.0.0.1'] if tcp else []) + ['-c', statement], check=check)

    def snapshot(name):
        def query(statement):
            return json.loads(pg(name, "BEGIN READ ONLY;SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public;"
                                 + statement + ';COMMIT', g.SOURCE).stdout)
        return g.snapshot(query, expected['role_names'])

    globals_data = g.prepare_globals((backup_state / 'globals-no-password.sql').read_bytes(), bootstrap='aos_app')
    for name in names:
        execute(['run', '-d', '--pull', 'never', '--name', name, '--network', 'none',
                 '--label', 'aos.restore-gate=' + g.LABEL, '--mount',
                 'type=volume,source=' + name + '-data,target=/var/lib/postgresql/data',
                 '-e', 'POSTGRES_USER=aos_app', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image])
        ready(name)
        execute(['exec', '-i', name, 'psql', '-U', 'aos_app', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-q', '-f', '-'], globals_data)
    source, target = names
    execute(['exec', '-i', source, 'pg_restore', '-U', 'aos_app', '-d', 'postgres', '--create', '--exit-on-error'],
            (backup_state / 'current-full.dump').read_bytes())
    require(snapshot(source) == expected, 'ISOLATED_INITIAL_RESTORE_MISMATCH')
    require(pg(source, 'SELECT 1', g.SOURCE, tcp=True).stdout.strip() == b'1', 'TCP_BASELINE_MISSING')
    journal.perform('stop_clients', lambda: {'scope': 'ISOLATED_NO_APPLICATION_CLIENTS'})

    def fence():
        pg(source, "ALTER SYSTEM SET listen_addresses=''")
        execute(['restart', source]); ready(source)
        listen = pg(source, 'SHOW listen_addresses').stdout.decode().strip()
        tcp_exit = pg(source, 'SELECT 1', g.SOURCE, tcp=True, check=False).returncode
        clients = int(pg(source, "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()").stdout)
        prepared = int(pg(source, 'SELECT count(*) FROM pg_prepared_xacts').stdout)
        require_window(listen_addresses=listen, tcp_exit=tcp_exit, other_clients=clients, prepared=prepared)
        return {'listen': listen, 'tcp_exit': tcp_exit, 'other_clients': clients, 'prepared': prepared}
    journal.perform('fence_tcp', fence)

    def dump():
        require(snapshot(source) == expected, 'SOURCE_CHANGED_BEFORE_DUMP')
        data = execute(['exec', source, 'pg_dump', '-U', 'aos_app', '-d', g.SOURCE, '-Fc']).stdout
        path = state / 'maintenance.dump'
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        return {'sha256': g.sha(path), 'bytes': len(data)}
    journal.perform('snapshot_dump', dump)

    def restore():
        execute(['exec', '-i', target, 'pg_restore', '-U', 'aos_app', '-d', 'postgres', '--create', '--exit-on-error'],
                (state / 'maintenance.dump').read_bytes())
        require(snapshot(target) == expected, 'INDEPENDENT_FULL_RESTORE_MISMATCH')
        return {'tables': len(expected['tables']), 'exact': True}
    journal.perform('independent_restore', restore)

    def migrate():
        config.set_main_option('sqlalchemy.url', 'postgresql://offline/offline')
        for number in range(136, 143):
            config.output_buffer = io.StringIO()
            command.upgrade(config, f'a0v_{number-1}:a0v_{number}', sql=True)
            g.save(state / f'migration-{number}-attempt.json', {'from': number-1, 'to': number})
            execute(['exec', '-i', source, 'psql', '-U', 'aos_app', '-d', g.SOURCE, '-v', 'ON_ERROR_STOP=1', '-q', '-f', '-'],
                    config.output_buffer.getvalue().encode())
            require(pg(source, 'SELECT version_num FROM alembic_version', g.SOURCE).stdout.strip() == f'a0v_{number}'.encode(), 'STEP_VERSION_DRIFT')
            g.save(state / f'migration-{number}-done.json', {'version': number})
        return {'version': 'a0v_142', 'steps': 7}
    journal.perform('migrate_steps', migrate)

    def verify():
        after = snapshot(source)
        g.require_old_rows(expected, after); g.require_catalog_preserved(expected, after)
        for table, additions in g.ADDITIONS.items():
            require(set(after['metadata'][table]) - set(expected['metadata'][table]) == additions, 'METADATA_ADDITION_DRIFT')
        require(all(after['tables'][t]['count'] == 0 for t in set(after['tables']) - set(expected['tables'])), 'NEW_TABLE_BACKFILL')
        added_roles = json.loads(pg(source, "SELECT json_agg(x ORDER BY rolname) FROM (SELECT rolname,rolcanlogin,rolinherit,"
            "rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,EXISTS(SELECT 1 FROM pg_auth_members m "
            "WHERE m.roleid=r.oid OR m.member=r.oid) AS members FROM pg_roles r WHERE rolname IN "
            "('aos_license_source_fence_owner','aos_source_license_approval_issuer','aos_source_license_issuer')) x").stdout)
        require(len(added_roles) == 3 and all(not value for row in added_roles for key, value in row.items()
                                           if key != 'rolname'), 'NEW_ROLE_PRIVILEGE_DRIFT')
        g.save(state / 'after.json', after)
        return {'old_tables': len(expected['tables']), 'rows_and_permissions_exact': True}
    journal.perform('verify', verify)

    def restore_tcp():
        pg(source, "ALTER SYSTEM SET listen_addresses='*'")
        execute(['restart', source]); ready(source)
        require(pg(source, 'SELECT 1', g.SOURCE, tcp=True).stdout.strip() == b'1', 'TCP_RESTORE_FAILED')
        return {'tcp_available': True}
    journal.perform('restore_tcp', restore_tcp)
    journal.perform('restart_clients', lambda: {'scope': 'ISOLATED_NO_APPLICATION_CLIENTS'})

    def acceptance():
        require(pg(source, 'SELECT version_num FROM alembic_version', g.SOURCE, tcp=True).stdout.strip() == b'a0v_142', 'FINAL_VERSION_DRIFT')
        for name in names:
            item = json.loads(execute(['inspect', name]).stdout)[0]
            require(item['HostConfig']['NetworkMode'] == 'none' and not any(item['NetworkSettings']['Ports'].values()), 'ISOLATION_DRIFT')
        return {'schema': 'a0v_142', 'isolated': True}
    journal.perform('acceptance', acceptance)
    result = {'outcome': 'ISOLATED_COMPLETE_MAINTENANCE_SEQUENCE_GREEN', 'state': str(state),
              'containers': names, 'tables': len(expected['tables']), 'elapsed_seconds': round(time.monotonic()-tick, 3),
              'current_source_touched': False, 'formal_current_window_proven': False}
    g.save(Path(evidence_directory) / 'isolated-sequence.json', result)
    return result


PROCESS_FIELDS = ('pid', 'ppid', 'uid', 'started', 'argv_sha256', 'cwd', 'children', 'listener_ports')


def require_process(expected, observed, *, executor_pid):
    require(all(key in expected and key in observed for key in PROCESS_FIELDS), 'PROCESS_FINGERPRINT_INCOMPLETE')
    require(type(observed['pid']) is int and observed['pid'] > 1
            and observed['pid'] != executor_pid, 'PROCESS_TARGET_INVALID')
    require(len(observed['listener_ports']) == 1, 'PROCESS_LISTENER_DRIFT')
    require(observed['children'] == expected['children'], 'PROCESS_CHILDREN_DRIFT')
    require(all(expected[key] == observed[key] for key in PROCESS_FIELDS), 'PROCESS_IDENTITY_DRIFT')


def read_service_candidate(*, pid, expected_argv, expected_cwd, expected_port, expected_child_argv=None):
    """Read-only exact original process candidate; does not authorize a signal."""
    import hashlib
    import shlex
    import subprocess

    def ps(columns):
        result = subprocess.run(['ps', '-p', str(pid), '-o', columns], capture_output=True, text=True, timeout=10)
        require(result.returncode == 0, 'PROCESS_MISSING_RECONCILE_ONLY')
        return result.stdout.strip()

    identity = ps('pid=,ppid=,uid=,lstart=')
    words = identity.split(maxsplit=3)
    require(len(words) == 4, 'PROCESS_METADATA_INVALID')
    argv = shlex.split(ps('args='))
    require(argv == expected_argv, 'PROCESS_ARGUMENTS_DRIFT')
    cwd_result = subprocess.run(['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
                                capture_output=True, text=True, timeout=10)
    directories = [line[1:] for line in cwd_result.stdout.splitlines() if line.startswith('n')]
    require(cwd_result.returncode == 0 and directories == [str(expected_cwd)], 'PROCESS_CWD_DRIFT')
    listeners = subprocess.run(['lsof', '-a', '-p', str(pid), '-nP', '-iTCP', '-sTCP:LISTEN', '-Fn'],
                              capture_output=True, text=True, timeout=10)
    endpoints = [line[1:] for line in listeners.stdout.splitlines() if line.startswith('n')]
    require(listeners.returncode == 0 and endpoints == [f'127.0.0.1:{expected_port}'], 'PROCESS_LISTENER_DRIFT')
    tree = subprocess.run(['ps', '-axo', 'pid=,ppid='], capture_output=True, text=True, timeout=10)
    require(tree.returncode == 0, 'PROCESS_TREE_UNAVAILABLE')
    children = sorted(int(row.split()[0]) for row in tree.stdout.splitlines() if int(row.split()[1]) == pid)
    if expected_child_argv is None:
        require(children == [], 'UNEXPECTED_SERVICE_CHILDREN')
    else:
        require(expected_port == 8434 and len(children) == 1, 'WEB_HELPER_COUNT_DRIFT')
        child_pid = children[0]
        child_args = subprocess.run(['ps', '-p', str(child_pid), '-o', 'args='], capture_output=True, text=True, timeout=10)
        require(child_args.returncode == 0 and shlex.split(child_args.stdout) == expected_child_argv, 'WEB_HELPER_ARGUMENTS_DRIFT')
        child_meta = subprocess.run(['ps', '-p', str(child_pid), '-o', 'pid=,ppid=,uid=,lstart='], capture_output=True, text=True, timeout=10)
        child_words = child_meta.stdout.strip().split(maxsplit=3)
        require(child_meta.returncode == 0 and len(child_words) == 4 and int(child_words[1]) == pid
                and int(child_words[2]) == int(words[2]), 'WEB_HELPER_IDENTITY_DRIFT')
        require(not any(int(row.split()[1]) == child_pid for row in tree.stdout.splitlines()), 'WEB_HELPER_DESCENDANTS_FORBIDDEN')
        children = [{'pid': child_pid, 'ppid': pid, 'uid': int(child_words[2]), 'started': child_words[3],
                     'argv_sha256': hashlib.sha256(json.dumps(expected_child_argv, separators=(',', ':')).encode()).hexdigest()}]
    require(ps('pid=,ppid=,uid=,lstart=') == identity and shlex.split(ps('args=')) == argv,
            'PROCESS_CHANGED_DURING_OBSERVATION')
    observed = {'pid': int(words[0]), 'ppid': int(words[1]), 'uid': int(words[2]), 'started': words[3],
                'argv_sha256': hashlib.sha256(json.dumps(argv, separators=(',', ':')).encode()).hexdigest(),
                'cwd': directories[0], 'children': children, 'listener_ports': [expected_port]}
    require_process(observed, observed, executor_pid=os.getpid())
    return observed
