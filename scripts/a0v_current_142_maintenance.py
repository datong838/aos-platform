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
            path = self.directory / (prior + '-done.json')
            require(path.is_file() and not path.is_symlink(), 'PRIOR_STEP_UNVERIFIED')
            try:
                with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'r') as handle:
                    require(os.fstat(handle.fileno()).st_size <= 65536, 'PRIOR_EVIDENCE_TOO_LARGE')
                    evidence = json.load(handle)
                require(isinstance(evidence, dict) and bool(evidence), 'PRIOR_EVIDENCE_INVALID')
                attempt_path = self.directory / (prior + '-attempt.json')
                require(attempt_path.is_file() and not attempt_path.is_symlink(), 'PRIOR_ATTEMPT_MISSING')
                attempt = json.loads(attempt_path.read_text())
                require(attempt.get('step') == prior, 'PRIOR_ATTEMPT_STEP_DRIFT')
            except (OSError, ValueError, TypeError, AttributeError):
                raise MaintenanceBlocked('PRIOR_EVIDENCE_UNREADABLE') from None
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
    return _run_sequence(backup_state=backup_state, evidence_directory=evidence_directory)


def run_current(*, task_id, backup_state, evidence_directory):
    read_maintenance_task(task_id)
    return _run_sequence(backup_state=backup_state, evidence_directory=evidence_directory, current_task_id=task_id)


def _run_sequence(*, backup_state, evidence_directory, current_task_id=None):
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
    code_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    require(subprocess.check_output(['git', 'branch', '--show-current'], cwd=root, text=True).strip() == 'm1', 'M1_REQUIRED')
    if current_task_id is not None:
        clean = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', 'scripts/a0v_current_142_maintenance.py',
                                'scripts/a0v_current_142_restore_gate.py', 'scripts/a0v_current_preview_http.py',
                                'services/aos-api/aos_api', 'services/aos-api/alembic'], cwd=root)
        require(clean.returncode == 0, 'CURRENT_EXECUTABLE_CODE_NOT_COMMITTED')
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
    if current_task_id is not None:
        state = root.parent / 'aos-recovery' / ('.aos-current142-' + current_task_id)
        try:
            state.mkdir(mode=0o700)
        except FileExistsError:
            raise MaintenanceBlocked('CURRENT_TASK_ATTEMPT_EXISTS_RECONCILE_ONLY') from None
    else:
        state = Path(tempfile.mkdtemp(prefix='.aos-maintenance142-', dir=root.parent / 'aos-recovery'))
    os.chmod(state, 0o700)
    journal = MaintenanceJournal(state)
    ctx = 'colima-aos-a0v-test-only'
    base = ['docker', '--context', ctx]
    names = ['aos-sequence142-' + secrets.token_hex(6) for _ in range(2)]
    if current_task_id is not None:
        read_maintenance_task(current_task_id)
        names[0] = g.SOURCE_CONTAINER
    tick = time.monotonic()

    def execute(args, data=None, check=True):
        current_source = current_task_id is not None and g.SOURCE_CONTAINER in args
        if current_source:
            read_maintenance_task(current_task_id)
            require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == code_head,
                    'CURRENT_CODE_HEAD_DRIFT')
            require(args[0] in ('exec', 'restart', 'inspect'), 'CURRENT_SOURCE_COMMAND_FORBIDDEN')
        command_base = ['docker', '--context', g.SOURCE_CONTEXT] if current_source else base
        result = subprocess.run(command_base + args, input=data, capture_output=True, timeout=180)
        require(not check or result.returncode == 0, 'ISOLATED_COMMAND_FAILED')
        return result

    image = json.loads(execute(['inspect', 'aos-e17-b17-acl-pg']).stdout)[0]['Image']
    g.save(state / 'intent.json', {'context': ctx, 'containers': names, 'image': image,
                                 'source_touched': current_task_id is not None, 'resource_task': current_task_id})
    services = None
    if current_task_id is not None:
        require_source(json.loads(execute(['inspect', g.SOURCE_CONTAINER]).stdout)[0])
        services = current_services()
        g.save(state / 'services-original.json', services)

    def ready(name):
        for _ in range(30):
            if execute(['exec', name, 'pg_isready', '-U', 'aos_app', '-d', 'postgres'], check=False).returncode == 0:
                return
            time.sleep(1)
        raise MaintenanceBlocked('ISOLATED_SERVER_NOT_READY')

    def pg(name, statement, database='postgres', tcp=False, check=True):
        if current_task_id is not None and name == g.SOURCE_CONTAINER and tcp:
            import psycopg
            from types import SimpleNamespace
            read_maintenance_task(current_task_id)
            require(database == g.SOURCE and statement in ('SELECT 1', 'SELECT version_num FROM alembic_version'),
                    'CURRENT_TCP_PROBE_NOT_READ_ONLY')
            spec_boot = importlib.util.spec_from_file_location('maintenance_current_bootstrap', root / 'scripts/a0v_current_preview_bootstrap.py')
            bootstrap = importlib.util.module_from_spec(spec_boot); spec_boot.loader.exec_module(bootstrap)
            try:
                with psycopg.connect(**bootstrap._connection_parameters(), connect_timeout=3) as conn:
                    conn.read_only = True
                    value = conn.execute(statement).fetchone()[0]
                return SimpleNamespace(returncode=0, stdout=(str(value) + '\n').encode())
            except psycopg.OperationalError:
                require(not check, 'CURRENT_TCP_PROBE_FAILED')
                return SimpleNamespace(returncode=2, stdout=b'')
        return execute(['exec', name, 'psql', '-U', 'aos_app', '-d', database, '-Atq', '-v', 'ON_ERROR_STOP=1']
                       + (['-h', '127.0.0.1'] if tcp else []) + ['-c', statement], check=check)

    def snapshot(name):
        def query(statement):
            return json.loads(pg(name, "BEGIN READ ONLY;SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public;"
                                 + statement + ';COMMIT', g.SOURCE).stdout)
        return g.snapshot(query, expected['role_names'])

    globals_data = g.prepare_globals((backup_state / 'globals-no-password.sql').read_bytes(), bootstrap='aos_app')
    for name in names:
        if current_task_id is not None and name == g.SOURCE_CONTAINER:
            continue
        execute(['run', '-d', '--pull', 'never', '--name', name, '--network', 'none',
                 '--label', 'aos.restore-gate=' + g.LABEL, '--mount',
                 'type=volume,source=' + name + '-data,target=/var/lib/postgresql/data',
                 '-e', 'POSTGRES_USER=aos_app', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image])
        ready(name)
        execute(['exec', '-i', name, 'psql', '-U', 'aos_app', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-q', '-f', '-'], globals_data)
    source, target = names
    if current_task_id is None:
        execute(['exec', '-i', source, 'pg_restore', '-U', 'aos_app', '-d', 'postgres', '--create', '--exit-on-error'],
                (backup_state / 'current-full.dump').read_bytes())
    require(snapshot(source) == expected, 'ISOLATED_INITIAL_RESTORE_MISMATCH')
    require(pg(source, 'SELECT 1', g.SOURCE, tcp=True).stdout.strip() == b'1', 'TCP_BASELINE_MISSING')
    listen_query = "SELECT json_agg(x) FROM (SELECT sourcefile,setting,applied,error FROM pg_file_settings WHERE name='listen_addresses') x"
    original_listen_rows = json.loads(pg(source, listen_query).stdout)
    original_listen = pg(source, 'SHOW listen_addresses').stdout.decode().strip()
    restore_statement = listen_restore_statement(original_listen_rows, effective=original_listen)
    g.save(state / 'listen-original.json', {'rows': original_listen_rows, 'effective': original_listen,
                                         'restore_statement': restore_statement})
    journal.perform('stop_clients', lambda: stop_current_services(services, current_task_id)
                    if current_task_id is not None else {'scope': 'ISOLATED_NO_APPLICATION_CLIENTS'})

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
        if current_task_id is not None:
            fresh_globals = execute(['exec', source, 'pg_dumpall', '-U', 'aos_app', '--globals-only', '--no-role-passwords']).stdout
            path_globals = state / 'maintenance-globals.sql'
            with os.fdopen(os.open(path_globals, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
                handle.write(fresh_globals); handle.flush(); os.fsync(handle.fileno())
            # The clone roles were restored before fencing; require the original
            # catalog to stay unchanged rather than silently accepting new roles.
            require(snapshot(source) == expected, 'SOURCE_GLOBALS_CHANGED')
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
        pg(source, restore_statement)
        execute(['restart', source]); ready(source)
        require(pg(source, 'SELECT 1', g.SOURCE, tcp=True).stdout.strip() == b'1', 'TCP_RESTORE_FAILED')
        require(json.loads(pg(source, listen_query).stdout) == original_listen_rows, 'LISTEN_CONFIGURATION_SOURCE_DRIFT')
        return {'tcp_available': True, 'original_configuration_source_restored': True}
    journal.perform('restore_tcp', restore_tcp)
    journal.perform('restart_clients', lambda: restart_current_services(services, current_task_id, state)
                    if current_task_id is not None else {'scope': 'ISOLATED_NO_APPLICATION_CLIENTS'})

    def acceptance():
        require(pg(source, 'SELECT version_num FROM alembic_version', g.SOURCE, tcp=True).stdout.strip() == b'a0v_142', 'FINAL_VERSION_DRIFT')
        after_restart = snapshot(source)
        g.require_old_rows(expected, after_restart); g.require_catalog_preserved(expected, after_restart)
        for name in names:
            item = json.loads(execute(['inspect', name]).stdout)[0]
            if current_task_id is not None and name == g.SOURCE_CONTAINER:
                require_source(item)
                continue
            require(item['HostConfig']['NetworkMode'] == 'none' and not any(item['NetworkSettings']['Ports'].values()), 'ISOLATION_DRIFT')
        return {'schema': 'a0v_142', 'isolated': True}
    journal.perform('acceptance', acceptance)
    result = {'outcome': ('CURRENT_135_TO_142_MAINTENANCE_GREEN' if current_task_id is not None
                          else 'ISOLATED_COMPLETE_MAINTENANCE_SEQUENCE_GREEN'), 'state': str(state),
              'containers': names, 'tables': len(expected['tables']), 'elapsed_seconds': round(time.monotonic()-tick, 3),
              'current_source_touched': current_task_id is not None,
              'formal_current_window_proven': current_task_id is not None}
    g.save(Path(evidence_directory) / ('current-sequence.json' if current_task_id else 'isolated-sequence.json'), result)
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


OWNER = 'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
MAINTENANCE_SCOPES = tuple('aos-platform/maintenance/current-preview-' + resource
                           for resource in ('database', 'api', 'web'))


def require_maintenance_task(task, live_leases, *, revision, delivered, now):
    from datetime import datetime, timezone
    require(revision == 'AOS-001329' and task.get('base_revision') == revision, 'MAINTENANCE_AUTHORITY_DRIFT')
    require(task.get('owner') == OWNER and task.get('status') == 'ACTIVE' and not delivered, 'MAINTENANCE_TASK_NOT_ACTIVE')
    require(set(MAINTENANCE_SCOPES) <= set(task.get('scope', [])), 'MAINTENANCE_RESOURCE_SCOPE_MISSING')
    matches = [lease for lease in live_leases if lease.get('task_id') == task.get('task_id')]
    require(len(matches) == 1 and matches[0] == task, 'MAINTENANCE_LIVE_LEASE_MISSING_OR_DRIFTED')
    try:
        expiry = datetime.fromisoformat(task['lease_expires_at'])
        require(expiry.tzinfo is not None and now.tzinfo is not None, 'MAINTENANCE_TIMEZONE_REQUIRED')
        require(expiry.astimezone(timezone.utc) > now.astimezone(timezone.utc), 'MAINTENANCE_LEASE_EXPIRED')
    except (KeyError, TypeError, ValueError):
        raise MaintenanceBlocked('MAINTENANCE_LEASE_INVALID') from None


def read_maintenance_task(task_id):
    """Read original authority/Receipt/live lease before each future mutation."""
    import re
    from datetime import datetime, timezone
    require(isinstance(task_id, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', task_id), 'MAINTENANCE_TASK_ID_INVALID')
    root = Path(__file__).resolve().parents[1]
    memory = root.parent / 'docs/palantier/AOS项目开发上下文/memory'
    authority = json.loads((memory / 'authority.json').read_text())
    task_path = memory / 'receipts/tasks' / (task_id + '.json')
    require(task_path.is_file(), 'MAINTENANCE_TASK_RECEIPT_MISSING')
    task = json.loads(task_path.read_text())
    require(task.get('task_id') == task_id, 'MAINTENANCE_TASK_ID_DRIFT')
    leases = json.loads((memory / 'leases.json').read_text())['leases']
    delivered = (memory / 'receipts/deliveries' / (task_id + '.json')).exists()
    require_maintenance_task(task, leases, revision=authority['project_revision'], delivered=delivered,
                             now=datetime.now(timezone.utc))
    return task


def listen_restore_statement(rows, *, effective):
    """Restore original override presence, not merely the effective value."""
    require(effective == '*' and rows, 'LISTEN_ORIGINAL_CONFIGURATION_DRIFT')
    require(all(row.get('error') is None for row in rows), 'LISTEN_CONFIGURATION_ERROR')
    active = [row for row in rows if row.get('applied')]
    require(len(active) == 1 and active[0].get('setting') == effective, 'LISTEN_SOURCE_AMBIGUOUS')
    files = {row.get('sourcefile') for row in rows}
    require(files <= {'/var/lib/postgresql/data/postgresql.conf',
                      '/var/lib/postgresql/data/postgresql.auto.conf'}, 'LISTEN_SOURCE_FILE_DRIFT')
    auto = [row for row in rows if row.get('sourcefile') == '/var/lib/postgresql/data/postgresql.auto.conf']
    if auto:
        require(len(auto) == 1 and auto[0].get('applied'), 'LISTEN_AUTO_OVERRIDE_AMBIGUOUS')
        return "ALTER SYSTEM SET listen_addresses = '*'"
    return 'ALTER SYSTEM RESET listen_addresses'


def current_services():
    import plistlib
    import subprocess
    root = Path(__file__).resolve().parents[1]
    services = []
    helper = [str(root / 'node_modules/.pnpm/@esbuild+darwin-arm64@0.21.5/node_modules/@esbuild/darwin-arm64/bin/esbuild'),
              '--service=0.21.5', '--ping']
    for label, port in [('com.aos.a0v-api-daily0900', 8080), ('com.aos.a0v-web-8434', 8434)]:
        agent = Path('/Users/ddt/Library/LaunchAgents') / (label + '.plist')
        data = plistlib.loads(agent.read_bytes())
        require(data['Label'] == label, 'SERVICE_LABEL_DRIFT')
        registered = subprocess.run(['launchctl', 'list', label], capture_output=True)
        require(registered.returncode != 0, 'REGISTERED_SERVICE_REQUIRES_DIFFERENT_CONTROL_PATH')
        result = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'], capture_output=True, text=True)
        pids = set(result.stdout.split())
        require(result.returncode == 0 and len(pids) == 1, 'SERVICE_LISTENER_NOT_UNIQUE')
        child_argv = helper if port == 8434 else None
        fingerprint = read_service_candidate(pid=int(next(iter(pids))), expected_argv=data['ProgramArguments'],
            expected_cwd=data['WorkingDirectory'], expected_port=port, expected_child_argv=child_argv)
        require(fingerprint['uid'] == os.getuid(), 'SERVICE_OWNER_DRIFT')
        environment = data.get('EnvironmentVariables', {})
        require(set(environment) <= {'PATH', 'PYTHONUNBUFFERED', 'VITE_AOS_API_PROXY_TARGET'}, 'SERVICE_ENVIRONMENT_REQUIRES_REVIEW')
        if port == 8080:
            require(data['ProgramArguments'][:2] == [str(root / 'services/aos-api/.venv/bin/python'),
                    str(root / 'scripts/a0v_current_preview_http.py')]
                    and data['ProgramArguments'][2] == '--signed-receipt'
                    and data['ProgramArguments'][4:] == ['--serve'], 'API_LAUNCH_COMMAND_DRIFT')
        else:
            require(data['ProgramArguments'][1:] == [str(root / 'node_modules/.pnpm/vite@5.4.21/node_modules/vite/bin/vite.js'),
                    '--host', '127.0.0.1', '--port', '8434'], 'WEB_LAUNCH_COMMAND_DRIFT')
        services.append({'label': label, 'port': port, 'argv': data['ProgramArguments'], 'cwd': data['WorkingDirectory'],
                         'environment': environment, 'helper_argv': child_argv, 'fingerprint': fingerprint})
    return services


def stop_current_services(services, task_id):
    import signal
    import subprocess
    import time
    for service in services:
        read_maintenance_task(task_id)
        original = service['fingerprint']
        observed = read_service_candidate(pid=original['pid'], expected_argv=service['argv'], expected_cwd=service['cwd'],
            expected_port=service['port'], expected_child_argv=service['helper_argv'])
        require_process(original, observed, executor_pid=os.getpid())
        os.kill(original['pid'], signal.SIGTERM)
        for _ in range(100):
            probe = subprocess.run(['ps', '-p', str(original['pid']), '-o', 'stat='], capture_output=True, text=True)
            listener = subprocess.run(['lsof', '-nP', f"-iTCP:{service['port']}", '-sTCP:LISTEN', '-t'], capture_output=True)
            if (probe.returncode != 0 or probe.stdout.strip().startswith('Z')) and not listener.stdout.strip():
                break
            time.sleep(.1)
        else:
            raise MaintenanceBlocked('SERVICE_STOP_UNKNOWN_RECONCILE_ONLY')
        for child in original['children']:
            probe = subprocess.run(['ps', '-p', str(child['pid']), '-o', 'stat='], capture_output=True, text=True)
            require(probe.returncode != 0 or probe.stdout.strip().startswith('Z'), 'WEB_HELPER_DID_NOT_EXIT')
    return {'services_stopped': [service['port'] for service in services], 'forced_signals': 0}


def restart_current_services(services, task_id, state):
    import subprocess
    import time
    import urllib.request
    restarted = []
    for service in services:
        read_maintenance_task(task_id)
        port = service['port']
        listener = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'], capture_output=True)
        require(not listener.stdout.strip(), 'RESTART_PORT_OCCUPIED_NO_DUPLICATE')
        if port == 8080:
            result = subprocess.run(service['argv'][:-1], cwd=service['cwd'], capture_output=True, timeout=90)
            require(result.returncode == 0, 'CURRENT_SIGNED_STARTUP_PREFLIGHT_FAILED')
            report = json.loads(result.stdout.strip().splitlines()[-1])
            require(report['outcome'] == 'CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN' and report['version'] == 'a0v_142',
                    'CURRENT_SIGNED_STARTUP_SCHEMA_DRIFT')
        environment = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'LANG') if k in os.environ}
        environment.update(service['environment'])
        log = state / f'service-{port}.log'
        with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            process = subprocess.Popen(service['argv'], cwd=service['cwd'], env=environment,
                                       stdout=handle, stderr=handle, start_new_session=True)
        for _ in range(100):
            require(process.poll() is None, 'RESTARTED_SERVICE_TERMINAL')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/' + ('v1/ready' if port == 8080 else ''), timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(.2)
        else:
            raise MaintenanceBlocked('RESTARTED_SERVICE_UNVERIFIED')
        read_service_candidate(pid=process.pid, expected_argv=service['argv'], expected_cwd=service['cwd'],
                               expected_port=port, expected_child_argv=service['helper_argv'])
        restarted.append({'port': port, 'pid': process.pid})
    return {'restarted': restarted, 'http_read_only_smoke': True, 'business_first_chain': False}
