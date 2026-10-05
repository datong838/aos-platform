"""Full current-135 backup/restore/142 rehearsal; never migrates the source.

No production service control or Host/Provider invocation exists in this tool.
Raw rows and credentials are never written to shared evidence.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import traceback

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'aos_current_preview_20260927'
SOURCE_CONTEXT = 'colima-aos-extension'
SOURCE_CONTAINER = 'aos-a0v-recovery-pg'
SOURCE_VOLUME = 'aos-a0v-recovery-pg-data'
DEST_CONTEXT = 'colima-aos-a0v-test-only'
LABEL = '20261005-142'
ADDITIONS = {'meta_object_type': {'SourceLicenseRequest'},
             'meta_action_type': {'aip_issue_source_license'}}


class RestoreGateBlocked(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise RestoreGateBlocked(reason)


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def prepare_globals(data, *, bootstrap):
    require(bootstrap == 'aos_app', 'EXACT_BOOTSTRAP_REQUIRED')
    lines = data.splitlines(keepends=True)
    existing = [index for index, line in enumerate(lines) if line.rstrip(b'\r\n') == b'CREATE ROLE aos_app;']
    require(len(existing) == 1, 'EXACT_BOOTSTRAP_CREATE_REQUIRED')
    return b''.join(line for index, line in enumerate(lines) if index != existing[0])


def validate_destination(item, *, container, volume, image):
    require(container.startswith('aos-daily142-') and volume == container + '-data', 'DESTINATION_NAME_REQUIRED')
    require(item['Name'] == '/' + container and item['State']['Running'], 'DESTINATION_IDENTITY_DRIFT')
    require(item['Image'] == image and item['Config']['Labels'].get('aos.restore-gate') == LABEL,
            'DESTINATION_IMAGE_OR_LABEL_DRIFT')
    require(item['HostConfig']['NetworkMode'] == 'none' and not item['HostConfig']['Privileged'],
            'DESTINATION_NETWORK_OR_PRIVILEGE_DRIFT')
    require(not any(item['NetworkSettings']['Ports'].values()), 'DESTINATION_PORTS_FORBIDDEN')
    mounts = item['Mounts']
    require(len(mounts) == 1 and mounts[0]['Type'] == 'volume'
            and mounts[0]['Name'] == volume and mounts[0]['Name'] != SOURCE_VOLUME
            and mounts[0]['Destination'] == '/var/lib/postgresql/data', 'DESTINATION_MOUNTS_FORBIDDEN')


def require_old_rows(before, after):
    for name, digest in before['tables'].items():
        require(name in after['tables'], 'OLD_TABLE_MISSING')
        if name == 'alembic_version':
            continue
        if name in ADDITIONS:
            original = before['metadata'][name]
            current = after['metadata'][name]
            require(all(current.get(key) == value for key, value in original.items()), 'OLD_METADATA_CHANGED')
            require(set(current) - set(original) <= ADDITIONS[name], 'UNEXPECTED_METADATA_ADDITION')
            require(after['tables'][name]['count'] == len(current), 'METADATA_COUNT_DRIFT')
        else:
            require(digest == after['tables'][name], 'OLD_ROWS_CHANGED')


def literal(value):
    return sql.Literal(value).as_string()


def identifier(value):
    return sql.Identifier(value).as_string()


def public(value):
    return sql.Identifier('public', value).as_string()


def snapshot(query, roles=None):
    tables = query("SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]') AS value "
                   "FROM pg_tables WHERE schemaname='public'")
    if roles is None:
        roles = query("SELECT json_agg(rolname ORDER BY rolname) AS value FROM pg_roles WHERE left(rolname,3)<>'pg_'")
    role_array = literal(roles) + '::text[]'
    digests = {}
    for index in range(0, len(tables), 40):
        statements = []
        for table in tables[index:index + 40]:
            statements.append(f"SELECT {literal(table)} AS name,count(*) AS count,"
                "encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS sha256 "
                f"FROM (SELECT encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') AS h FROM {public(table)} t) hashes")
        rows = query('SELECT json_agg(x ORDER BY name) AS value FROM (' + ' UNION ALL '.join(statements) + ') x')
        digests.update({row['name']: {'count': row['count'], 'sha256': row['sha256']} for row in rows})
    metadata = {}
    for table in ADDITIONS:
        metadata[table] = query("SELECT coalesce(json_object_agg(id,h),'{}') AS value FROM "
            f"(SELECT id,encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') AS h FROM {public(table)} t) x")
    relation_rows = query("SELECT json_agg(x ORDER BY name) AS value FROM (SELECT c.relname AS name,"
        "c.relkind,pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity,c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
        "AND c.relkind IN ('r','p','v','m')) x")
    privileges = ",".join(f"has_table_privilege(r.oid,c.oid,'{name}')" for name in
                          ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'))
    acl_rows = query("SELECT json_agg(x ORDER BY role,relation) AS value FROM ("
        f"SELECT r.rolname AS role,c.relname AS relation,ARRAY[{privileges}] AS privileges "
        "FROM pg_roles r CROSS JOIN pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        f"WHERE r.rolname=ANY({role_array}) AND n.nspname='public' AND c.relkind IN ('r','p','v','m')) x")
    policies = query("SELECT json_agg(x ORDER BY tablename,policyname) AS value FROM ("
                     "SELECT * FROM pg_policies WHERE schemaname='public') x") or []
    for policy in policies:
        policy['roles'].sort()
    functions = query("SELECT json_agg(x ORDER BY name) AS value FROM (SELECT "
        "p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS name,"
        "pg_get_userbyid(p.proowner) AS owner,"
        "encode(sha256(convert_to(pg_get_functiondef(p.oid),'UTF8')),'hex') AS sha256 "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.prokind IN ('f','p')) x") or []
    function_acl = query("SELECT json_agg(x ORDER BY role,name) AS value FROM (SELECT r.rolname AS role,"
        "p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS name,"
        "has_function_privilege(r.oid,p.oid,'EXECUTE') AS allowed FROM pg_roles r CROSS JOIN pg_proc p "
        f"JOIN pg_namespace n ON n.oid=p.pronamespace WHERE r.rolname=ANY({role_array}) "
        "AND n.nspname='public' AND p.prokind IN ('f','p')) x") or []
    sequences = {}
    for name in query("SELECT coalesce(json_agg(c.relname ORDER BY c.relname),'[]') AS value "
                      "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                      "WHERE n.nspname='public' AND c.relkind='S'"):
        sequences[name] = query(f"SELECT row_to_json(x) AS value FROM (SELECT last_value,is_called FROM {public(name)}) x")
    attrs = query("SELECT json_agg(x ORDER BY rolname) AS value FROM (SELECT rolname,rolcanlogin,rolinherit,"
        "rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil,"
        "encode(sha256(convert_to(coalesce(rolconfig::text,''),'UTF8')),'hex') AS config_hash "
        f"FROM pg_roles WHERE rolname=ANY({role_array})) x")
    memberships = query("SELECT coalesce(json_agg(x ORDER BY role,member),'[]') AS value FROM ("
        "SELECT r.rolname AS role,s.rolname AS member,g.rolname AS grantor,m.admin_option,m.inherit_option,m.set_option "
        "FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles s ON s.oid=m.member "
        "JOIN pg_roles g ON g.oid=m.grantor "
        f"WHERE r.rolname=ANY({role_array}) OR s.rolname=ANY({role_array})) x")
    database_permissions = query("SELECT json_agg(x ORDER BY role) AS value FROM (SELECT r.rolname AS role,"
        "has_database_privilege(r.oid,current_database(),'CONNECT') AS connect,"
        "has_database_privilege(r.oid,current_database(),'CREATE') AS create,"
        "has_database_privilege(r.oid,current_database(),'TEMP') AS temp,"
        "has_schema_privilege(r.oid,'public','CREATE') AS schema_create,"
        "has_schema_privilege(r.oid,'public','USAGE') AS schema_usage FROM pg_roles r "
        f"WHERE r.rolname=ANY({role_array})) x")
    database_properties = query("SELECT row_to_json(x) AS value FROM (SELECT datname,"
        "pg_get_userbyid(datdba) AS owner,encoding,datlocprovider,datcollate,datctype,daticulocale,"
        "datcollversion,datistemplate,datallowconn,datconnlimit,"
        "(SELECT json_agg(a ORDER BY grantor,grantee,privilege_type,is_grantable) FROM "
        "(SELECT pg_get_userbyid(e.grantor) AS grantor,CASE WHEN e.grantee=0 THEN 'PUBLIC' "
        "ELSE pg_get_userbyid(e.grantee) END AS grantee,e.privilege_type,e.is_grantable "
        "FROM aclexplode(coalesce(d.datacl,acldefault('d',d.datdba))) e) a) AS acl "
        "FROM pg_database d WHERE datname=current_database()) x")
    database_settings = query("SELECT coalesce(json_agg(x ORDER BY role),'[]') AS value FROM (SELECT "
        "CASE WHEN s.setrole=0 THEN 'PUBLIC' ELSE pg_get_userbyid(s.setrole) END AS role,"
        "encode(sha256(convert_to(s.setconfig::text,'UTF8')),'hex') AS config_hash "
        "FROM pg_db_role_setting s JOIN pg_database d ON d.oid=s.setdatabase "
        "WHERE d.datname=current_database()) x")
    return {'version': query('SELECT to_json(version_num) AS value FROM public.alembic_version'),
            'role_names': roles, 'tables': digests, 'metadata': metadata, 'sequences': sequences,
            'relations': relation_rows, 'acl': acl_rows, 'policies': policies,
            'functions': functions, 'function_acl': function_acl, 'roles': attrs, 'memberships': memberships,
            'database_permissions': database_permissions, 'database_properties': database_properties,
            'database_settings': database_settings}


def require_catalog_preserved(before, after):
    for key in ('relations', 'acl', 'policies', 'functions', 'function_acl'):
        def identity(row):
            if key == 'policies':
                return (row['tablename'], row['policyname'])
            if key in ('acl', 'function_acl'):
                return (row['role'], row.get('relation', row.get('name')))
            return row['name']
        current = {identity(row): row for row in after[key]}
        require(all(current.get(identity(row)) == row for row in before[key]), 'OLD_CATALOG_CHANGED_' + key)
    for key in ('sequences', 'roles', 'memberships', 'database_permissions', 'database_properties', 'database_settings'):
        require(before[key] == after[key], 'OLD_CATALOG_CHANGED_' + key)


def run():
    os.environ['AOS_DOTENV_DISABLED'] = '1'
    require(not os.environ.get('AOS_DATABASE_URL'), 'AMBIENT_DATABASE_FORBIDDEN')
    state = Path(tempfile.mkdtemp(prefix='.aos-current-backup-20261005-142-gate-', dir=ROOT.parent / 'aos-recovery'))
    os.chmod(state, 0o700)
    stage = 'preflight'
    started = time.monotonic()
    def command_run(args, *, input_bytes=None, binary_path=None, stage_name):
        tick = time.monotonic()
        if binary_path is None:
            result = subprocess.run(args, input=input_bytes, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=300)
        else:
            with os.fdopen(os.open(binary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
                result = subprocess.run(args, stdout=handle, stderr=subprocess.PIPE, timeout=300)
                handle.flush(); os.fsync(handle.fileno())
        with os.fdopen(os.open(state / (stage_name + '.stderr'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(result.stderr)
        save(state / (stage_name + '.result.json'), {'exit_code': result.returncode,
                                                  'elapsed_seconds': round(time.monotonic() - tick, 3)})
        require(result.returncode == 0, 'COMMAND_FAILED_' + stage_name)
        return result.stdout
    def inspect(context, container):
        return json.loads(subprocess.check_output(['docker', '--context', context, 'inspect', container],
                                                  stderr=subprocess.DEVNULL))[0]
    try:
        require(subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() == 'm1', 'M1_REQUIRED')
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        config = Config(str(ROOT / 'services/aos-api/alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'services/aos-api/alembic'))
        require(ScriptDirectory.from_config(config).get_heads() == ['a0v_142'], 'EXACT_CODE_142_REQUIRED')
        source_item = inspect(SOURCE_CONTEXT, SOURCE_CONTAINER)
        require(source_item['State']['Running'] and any(m.get('Name') == SOURCE_VOLUME
            and m['Destination'] == '/var/lib/postgresql/data' for m in source_item['Mounts']), 'SOURCE_VOLUME_DRIFT')
        image = inspect(DEST_CONTEXT, 'aos-e17-b17-acl-pg')['Image']
        nonce = secrets.token_hex(6)
        container, volume = 'aos-daily142-' + nonce, 'aos-daily142-' + nonce + '-data'
        admin, clone = 'aos_app', SOURCE
        spec = importlib.util.spec_from_file_location('restore142_bootstrap', ROOT / 'scripts/a0v_current_preview_bootstrap.py')
        bootstrap = importlib.util.module_from_spec(spec); spec.loader.exec_module(bootstrap)
        parameters = bootstrap._connection_parameters()
        require((parameters['host'], parameters['port'], parameters['dbname'], parameters['user']) ==
                ('127.0.0.1', 18435, SOURCE, 'aos_app'), 'EXACT_SOURCE_REQUIRED')
        save(state / 'intent.json', {'head': head, 'source': SOURCE, 'source_volume': SOURCE_VOLUME,
            'container': container, 'volume': volume, 'image': image, 'admin': admin, 'clone': clone,
            'source_context': SOURCE_CONTEXT, 'destination_context': DEST_CONTEXT,
            'authorization': 'ISOLATED_RESTORE_ONLY_NO_CURRENT_MIGRATION'})
        src = ['docker', '--context', SOURCE_CONTEXT, 'exec', SOURCE_CONTAINER]
        stage = 'snapshot_dump'
        with psycopg.connect(**parameters, row_factory=dict_row) as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            conn.read_only = True
            conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
            source = snapshot(lambda statement: conn.execute(statement).fetchone()['value'])
            require(source['version'] == 'a0v_135'
                    and conn.execute('SELECT rolname FROM pg_roles WHERE oid=10').fetchone()['rolname'] == admin,
                    'EXACT_SOURCE_135_BOOTSTRAP_REQUIRED')
            snapshot_id = conn.execute('SELECT pg_export_snapshot() AS value').fetchone()['value']
            command_run(src + ['pg_dump', '-U', 'aos_app', '-d', SOURCE, '-Fc', '--snapshot', snapshot_id],
                        binary_path=state / 'current-full.dump', stage_name='dump')
        save(state / 'source.json', source)
        command_run(src + ['pg_dumpall', '-U', 'aos_app', '--globals-only', '--no-role-passwords'],
                    binary_path=state / 'globals-no-password.sql', stage_name='globals')
        globals_data = (state / 'globals-no-password.sql').read_bytes()
        require(b'CREATE TABLESPACE' not in globals_data, 'CUSTOM_TABLESPACE_REQUIRES_SEPARATE_PLAN')
        restored_globals = prepare_globals(globals_data, bootstrap=admin)
        with os.fdopen(os.open(state / 'globals-restore-input.sql', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(restored_globals)
        toc = subprocess.run(
            src[:-1] + ['-i', SOURCE_CONTAINER, 'pg_restore', '--list'],
            input=(state / 'current-full.dump').read_bytes(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        require(toc.returncode == 0 and b'TABLE DATA' in toc.stdout, 'BACKUP_TOC_INVALID')
        with os.fdopen(os.open(state / 'toc.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(toc.stdout)
        backup = {'state': str(state), 'bytes': (state / 'current-full.dump').stat().st_size,
                  'sha256': sha(state / 'current-full.dump'), 'globals_sha256': sha(state / 'globals-no-password.sql'),
                  'toc_lines': len(toc.stdout.splitlines())}
        save(state / 'backup.json', backup)
        stage = 'create_isolated_target'
        command_run(['docker', '--context', DEST_CONTEXT, 'run', '-d', '--pull', 'never', '--name', container,
            '--label', 'aos.restore-gate=' + LABEL, '--network', 'none', '--cpus', '1', '--memory', '768m',
            '--mount', 'type=volume,source=' + volume + ',target=/var/lib/postgresql/data',
            '-e', 'POSTGRES_USER=' + admin, '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image], stage_name='create')
        validate_destination(inspect(DEST_CONTEXT, container), container=container, volume=volume, image=image)
        dst = ['docker', '--context', DEST_CONTEXT, 'exec', '-i', container]
        ready = False
        for _ in range(30):
            probe = subprocess.run(dst + ['pg_isready', '-U', admin, '-d', 'postgres'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if probe.returncode == 0:
                ready = True; break
            time.sleep(1)
        require(ready, 'ISOLATED_TARGET_NOT_READY')
        stage = 'restore_globals_and_database'
        command_run(dst + ['psql', '-U', admin, '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-q', '-f', '-'],
                    input_bytes=restored_globals, stage_name='restore_globals')
        command_run(dst + ['pg_restore', '-U', admin, '-d', 'postgres', '--create', '--exit-on-error'],
                    input_bytes=(state / 'current-full.dump').read_bytes(), stage_name='restore')
        def query(statement):
            result = subprocess.run(dst + ['psql', '-U', admin, '-d', clone, '-v', 'ON_ERROR_STOP=1', '-Atq', '-c',
                "BEGIN READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public; " + statement + '; COMMIT'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            require(result.returncode == 0, 'CLONE_READ_FAILED')
            return json.loads(result.stdout)
        stage = 'exact_restore_compare'
        restored = snapshot(query, source['role_names'])
        require(restored == source, 'RESTORE_FULL_STATE_MISMATCH')
        save(state / 'restored.json', restored)
        print(json.dumps({'stage': 'FULL_RESTORE_EXACT', 'tables': len(source['tables']), 'state': str(state)}), flush=True)
        stage = 'rehearse_136_to_142'
        config.set_main_option('sqlalchemy.url', 'postgresql://offline/offline')
        for number in range(136, 143):
            config.output_buffer = io.StringIO()
            command.upgrade(config, f'a0v_{number-1}:a0v_{number}', sql=True)
            migration_sql = config.output_buffer.getvalue().encode()
            with os.fdopen(os.open(state / f'a0v_{number}.sql', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
                handle.write(migration_sql)
            save(state / f'a0v_{number}-intent.json', {'from': f'a0v_{number-1}', 'to': f'a0v_{number}',
                                                    'sql_sha256': sha(state / f'a0v_{number}.sql')})
            command_run(dst + ['psql', '-U', admin, '-d', clone, '-v', 'ON_ERROR_STOP=1', '-q', '-f', '-'],
                        input_bytes=migration_sql, stage_name=f'upgrade-{number}')
            require(query('SELECT to_json(version_num) AS value FROM public.alembic_version') == f'a0v_{number}', 'STEP_VERSION_DRIFT')
            save(state / f'a0v_{number}-done.json', {'version': f'a0v_{number}'})
        after = snapshot(query, source['role_names'])
        require_old_rows(source, after); require_catalog_preserved(source, after)
        for table, additions in ADDITIONS.items():
            require(set(after['metadata'][table]) - set(source['metadata'][table]) == additions, 'EXPECTED_METADATA_MISSING')
        new_tables = set(after['tables']) - set(source['tables'])
        require(all(after['tables'][table]['count'] == 0 for table in new_tables), 'UNEXPECTED_BACKFILL')
        added_roles = query("SELECT json_agg(x ORDER BY rolname) AS value FROM (SELECT rolname,rolcanlogin,rolinherit,"
            "rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,EXISTS(SELECT 1 FROM pg_auth_members m "
            "WHERE m.roleid=r.oid OR m.member=r.oid) AS members FROM pg_roles r WHERE rolname IN "
            "('aos_license_source_fence_owner','aos_source_license_approval_issuer','aos_source_license_issuer')) x")
        require(len(added_roles) == 3 and all(not value for row in added_roles for key,value in row.items() if key != 'rolname'), 'ADDED_ROLE_DRIFT')
        stage = 'source_unchanged'
        with psycopg.connect(**parameters, row_factory=dict_row) as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ; conn.read_only = True
            conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
            require(snapshot(lambda statement: conn.execute(statement).fetchone()['value']) == source, 'SOURCE_CHANGED_DURING_REHEARSAL')
        require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == head, 'CODE_HEAD_DRIFT')
        validate_destination(inspect(DEST_CONTEXT, container), container=container, volume=volume, image=image)
        save(state / 'after.json', after)
        result = {'outcome': 'FULL_RESTORE_135_TO_142_REHEARSAL_GREEN', 'source': SOURCE, 'source_version': 'a0v_135',
            'clone_version': 'a0v_142', 'head': head, 'backup': backup, 'container': container, 'volume': volume,
            'clone': clone, 'source_context': SOURCE_CONTEXT, 'destination_context': DEST_CONTEXT,
            'old_tables': len(source['tables']), 'new_tables': sorted(new_tables), 'added_roles': added_roles,
            'database_permissions_properties_settings_unchanged': True,
            'old_rows_acl_rls_functions_sequences_unchanged': True, 'source_unchanged': True,
            'elapsed_seconds': round(time.monotonic() - started, 3), 'current_migration_performed': False}
        save(state / 'verification.json', result)
        print(json.dumps(result), flush=True)
    except BaseException as exc:
        save(state / 'failure.json', {'stage': stage, 'type': type(exc).__name__, 'source_never_migrated': True})
        with os.fdopen(os.open(state / 'failure-private.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
            handle.write(traceback.format_exc())
        print(json.dumps({'outcome': 'FAILED_RETAINED', 'state': str(state), 'stage': stage,
                          'error_type': type(exc).__name__}), flush=True)
        raise SystemExit(2) from None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', required=True)
    parser.parse_args()
    run()
