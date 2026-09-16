"""Clone-only a0v066 -> a0v068 rehearsal for dispatch configuration refresh."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260916/state/dispatch-configuration-refresh-clone'
CLONE = 'aos_dispatch_refresh_20260916_test'
TASK = 'SC4-5L6Y5F4-REFRESH-DEPLOY-20260916'
NEW_TABLE = 'extension_dispatch_configuration_refresh_receipt'
FILES = (
    'a0v_067_dispatch_configuration_refresh.py',
    'a0v_068_dispatch_configuration_refresh_owner.py',
)


def fingerprint(conn):
    from psycopg import sql
    rows = conn.execute("""SELECT tablename FROM pg_tables
        WHERE schemaname='public' AND tablename<>'alembic_version'
        ORDER BY tablename""").fetchall()
    result = {}
    for row in rows:
        name = row['tablename']
        summary = dict(conn.execute(sql.SQL(
            "SELECT count(*) AS count,"
            "md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text))) AS digest "
            "FROM {} t"
        ).format(sql.Identifier('public', name))).fetchone())
        if name == NEW_TABLE:
            if summary['count'] != 0:
                raise ValueError('new refresh receipt history must remain empty during migration')
        else:
            result[name] = summary
    return result


def verify(conn):
    table = 'public.' + NEW_TABLE
    acl = conn.execute("""SELECT relrowsecurity,relforcerowsecurity,
        has_table_privilege('aos_runtime',oid,'SELECT') AS runtime_select,
        has_table_privilege('aos_runtime',oid,'INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_write,
        has_table_privilege('aos_extension_maintainer',oid,'SELECT') AS maintainer_select,
        has_table_privilege('aos_extension_maintainer',oid,'INSERT,UPDATE,DELETE,TRUNCATE') AS maintainer_write
        FROM pg_class WHERE oid=to_regclass(%s)""", (table,)).fetchone()
    expected_acl = dict(
        relrowsecurity=True,
        relforcerowsecurity=True,
        runtime_select=True,
        runtime_write=False,
        maintainer_select=True,
        maintainer_write=False,
    )
    if acl is None or dict(acl) != expected_acl:
        raise ValueError('refresh receipt table ACL/RLS differs')
    triggers = [row['tgname'] for row in conn.execute("""SELECT tgname FROM pg_trigger
        WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal ORDER BY tgname""", (table,)).fetchall()]
    if triggers != ['immutable_refresh_history', 'validate_refresh_history']:
        raise ValueError('refresh receipt immutability/validation triggers differ')
    policies = conn.execute("""SELECT qual,with_check FROM pg_policies
        WHERE schemaname='public' AND tablename=%s""", (NEW_TABLE,)).fetchall()
    if len(policies) != 1 or any(
        value not in str(policies[0]) for value in ('aos.org_id', 'aos.project_id')
    ):
        raise ValueError('refresh receipt dual-tenant policy missing')
    owner = conn.execute("""SELECT p.prosecdef,p.proconfig,
        has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
        has_function_privilege('aos_extension_maintainer',p.oid,'EXECUTE') AS maintainer_execute,
        EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
          WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute
        FROM pg_proc p WHERE p.oid=to_regprocedure(
          'public.extension_dispatch_configuration_refresh_a0v_068(jsonb,text)')""").fetchone()
    if owner is None or dict(owner) != dict(
        prosecdef=True,
        proconfig=['search_path=pg_catalog, public, pg_temp'],
        runtime_execute=False,
        maintainer_execute=True,
        public_execute=False,
    ):
        raise ValueError('refresh owner function privilege/search_path differs')
    validator_public = conn.execute("""SELECT EXISTS(
        SELECT 1 FROM pg_proc p, LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
        WHERE p.oid=to_regprocedure('public.validate_dispatch_configuration_refresh_a0v_067()')
          AND a.grantee=0 AND a.privilege_type='EXECUTE') AS allowed""").fetchone()['allowed']
    if validator_public:
        raise ValueError('refresh validator executable by PUBLIC')
    return dict(
        tableAcl=expected_acl,
        triggers=triggers,
        dualTenantPolicy=True,
        ownerFunction=dict(owner),
        validatorPublicExecute=False,
        newRows=0,
    )


def profile():
    path = Path(__file__).with_name('a0v_installed_bootstrap_action_deploy.py')
    spec = importlib.util.spec_from_file_location('dispatch_refresh_clone_base', path)
    deployment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deployment)
    deployment.STATE = STATE
    deployment.CLONE = CLONE
    deployment.TASK = TASK
    deployment.SOURCE = 'a0v_066'
    deployment.TARGET = 'a0v_068'
    deployment.FILES = FILES
    deployment.CHAIN = ['a0v_068', 'a0v_067']
    deployment.storage.CLONE = CLONE
    deployment.storage.FILES = FILES
    deployment.fingerprint = deployment.storage.fingerprint = fingerprint
    deployment.verify = verify
    deployment.executor_hashes = lambda: {
        file.name: deployment.storage.digest(file)
        for file in (Path(__file__), path, Path(deployment.storage.__file__), ROOT / 'services/aos-api/alembic/env.py')
    }
    original_upgrade = deployment.upgrade

    def clone_only_upgrade(database):
        if database != CLONE:
            raise ValueError('clone-only refresh migration required')
        return original_upgrade(database)

    deployment.upgrade = clone_only_upgrade
    return deployment


def prepare():
    from psycopg import sql
    deployment = profile()
    deployment.require_lease()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    backup = STATE / 'aos_meta_head-before-a0v_068.dump'
    proof_path = STATE / 'prepare.json'
    if backup.exists() or proof_path.exists():
        raise ValueError('retained refresh clone preparation requires inspection')
    before, user, snapshot = deployment.snapshot_backup(backup)
    with deployment.storage.connect(deployment.storage.MAIN, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as handle:
        restored = subprocess.run([
            'docker', '--context', deployment.storage.CONTEXT, 'exec', '-i', deployment.storage.CONTAINER,
            'pg_restore', '-U', user, '-d', CLONE, '--exit-on-error',
        ], stdin=handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if restored.returncode:
        raise RuntimeError('refresh clone restore failed; retained for inspection')
    with deployment.storage.connect(CLONE) as conn:
        if deployment.storage.version(conn) != ['a0v_066'] or fingerprint(conn) != before:
            raise ValueError('refresh clone baseline differs')
    transaction = deployment.upgrade(CLONE)
    with deployment.storage.connect(CLONE) as conn:
        if deployment.storage.version(conn) != ['a0v_068'] or fingerprint(conn) != before:
            raise ValueError('refresh clone final data differs')
        schema = verify(conn)
    proof = dict(
        outcome='DISPATCH_CONFIGURATION_REFRESH_CLONE_RESTORE_VERIFIED',
        source='a0v_066',
        target='a0v_068',
        main=deployment.storage.MAIN,
        clone=CLONE,
        migrations=deployment.storage.migration_hashes(),
        executors=deployment.executor_hashes(),
        backup=dict(path=str(backup), sha256=deployment.storage.digest(backup), bytes=backup.stat().st_size),
        snapshot=snapshot,
        before=before,
        after=transaction['after'],
        schema=schema,
        mainMigrated=False,
        businessWrites=0,
        sourceCalls=0,
        at=datetime.now(timezone.utc).isoformat(),
    )
    deployment.protected_write(proof_path, proof)
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        if deployment.storage.version(conn) != ['a0v_066']:
            raise ValueError('main version unexpectedly changed')
    public = {key: value for key, value in proof.items() if key not in ('before', 'after', 'snapshot', 'backup')}
    public.update(
        preservedTableCount=len(before),
        oldDataUnchanged=True,
        backupSha256=proof['backup']['sha256'],
    )
    evidence = ROOT / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/y5f4-clone-migration-verification.json'
    evidence.write_text(json.dumps(public, ensure_ascii=False, indent=2) + '\n')
    return public


if __name__ == '__main__':
    result = prepare()
    print(json.dumps({key: result[key] for key in ('outcome', 'preservedTableCount', 'mainMigrated')}))
