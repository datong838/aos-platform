"""Clone-only 061 -> 066 rehearsal using the original retained-snapshot deployer."""
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260916/state/snapshot-schedule-clone'
CLONE='aos_snapshot_schedule_20260916_test'
TASK='SC4-5L6Y6A-CLONE-MIGRATION-20260916'
NEW_TABLES=(
    'pipeline_snapshot_schedule_claim','pipeline_snapshot_schedule_member',
    'pipeline_snapshot_schedule_definition_revision','pipeline_snapshot_schedule_definition_member',
    'pipeline_snapshot_schedule_definition_head','pipeline_snapshot_schedule_current_member',
    'pipeline_snapshot_group_recovery_receipt',
)
FILES=(
    'a0v_062_snapshot_schedule_claim.py','a0v_063_snapshot_schedule_definition.py',
    'a0v_064_defined_snapshot_schedule_claim.py','a0v_065_snapshot_group_recovery_receipt.py',
    'a0v_066_snapshot_recovery_only_fence.py',
)


def fingerprint(conn):
    from psycopg import sql
    tables=conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version' ORDER BY tablename").fetchall()
    result={}
    for row in tables:
        name=row['tablename']
        counts=dict(conn.execute(sql.SQL("SELECT count(*) AS count,md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text))) AS digest FROM {} t").format(sql.Identifier('public',name))).fetchone())
        if name in NEW_TABLES:
            if counts['count']!=0:raise ValueError('new snapshot ledger must remain empty in migration rehearsal')
        else:result[name]=counts
    return result


def verify(conn):
    result={}
    for table in NEW_TABLES:
        row=conn.execute('''SELECT relrowsecurity,relforcerowsecurity,
            has_table_privilege('aos_runtime',oid,'SELECT') AS read,
            has_table_privilege('aos_runtime',oid,'INSERT') AS insert,
            has_table_privilege('aos_runtime',oid,'UPDATE') AS update,
            has_table_privilege('aos_runtime',oid,'DELETE') AS delete,
            has_table_privilege('aos_runtime',oid,'TRUNCATE') AS truncate
            FROM pg_class WHERE oid=to_regclass(%s)''',('public.'+table,)).fetchone()
        expected=dict(relrowsecurity=True,relforcerowsecurity=True,read=True,insert=True,
                      update=table=='pipeline_snapshot_schedule_definition_head',
                      delete=table=='pipeline_snapshot_schedule_current_member',truncate=False)
        if row is None or dict(row)!=expected:raise ValueError('snapshot table privileges differ: '+table)
        triggers=[dict(r) for r in conn.execute('''SELECT tgname,tgenabled,tgdeferrable,tginitdeferred
            FROM pg_trigger WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal ORDER BY tgname''',('public.'+table,)).fetchall()]
        if not triggers or any(r['tgenabled']!='O' for r in triggers):raise ValueError('snapshot triggers unavailable')
        if not any(r['tgdeferrable'] and r['tginitdeferred'] for r in triggers):raise ValueError('snapshot deferred integrity missing')
        policies=conn.execute('SELECT qual,with_check FROM pg_policies WHERE schemaname=%s AND tablename=%s',('public',table)).fetchall()
        if len(policies)!=1 or any(key not in str(policies[0]) for key in ('aos.org_id','aos.project_id')):
            raise ValueError('snapshot dual tenant policy missing')
        result[table]=dict(privileges=expected,triggers=triggers,dualTenantPolicy=True)
    fence=conn.execute("SELECT pg_get_functiondef('public.reject_recovery_only_schedule_claim_a0v_066()'::regprocedure) AS body").fetchone()['body']
    if 'renew_saved_group' not in fence or 'pg_catalog' not in fence:
        raise ValueError('recovery-only fixed fence missing')
    if 'snapshot_recovery_only_claim_fence' not in {t['tgname'] for t in result[NEW_TABLES[0]]['triggers']}:
        raise ValueError('recovery-only claim trigger missing')
    return result


def profile():
    path=Path(__file__).with_name('a0v_installed_bootstrap_action_deploy.py')
    spec=importlib.util.spec_from_file_location('snapshot_schedule_clone_base',path)
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.STATE=STATE;p.CLONE=CLONE;p.TASK=TASK;p.SOURCE='a0v_061';p.TARGET='a0v_066'
    p.FILES=FILES;p.CHAIN=['a0v_066','a0v_065','a0v_064','a0v_063','a0v_062']
    p.storage.CLONE=CLONE;p.storage.FILES=FILES
    p.fingerprint=p.storage.fingerprint=fingerprint;p.verify=verify
    p.executor_hashes=lambda:{x.name:p.storage.digest(x) for x in
        (Path(__file__),path,Path(p.storage.__file__),ROOT/'services/aos-api/alembic/env.py')}
    original=p.upgrade
    def clone_upgrade(database):
        if database!=CLONE:raise ValueError('clone only migration required')
        return original(database)
    p.upgrade=clone_upgrade
    return p


def prepare():
    from psycopg import sql
    p=profile();p.require_lease()
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(STATE,0o700)
    backup=STATE/'aos_meta_head-before-a0v_066.dump'
    if backup.exists() or (STATE/'prepare.json').exists():raise ValueError('retained clone preparation requires inspection')
    before,user,snapshot=p.snapshot_backup(backup)
    print('Consistent backup retained; restoring isolated clone',flush=True)
    with p.storage.connect(p.storage.MAIN,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as handle:
        restored=subprocess.run(['docker','--context',p.storage.CONTEXT,'exec','-i',p.storage.CONTAINER,
            'pg_restore','-U',user,'-d',CLONE,'--exit-on-error'],stdin=handle,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if restored.returncode:raise RuntimeError('clone restore failed; retained for inspection')
    with p.storage.connect(CLONE) as conn:
        if p.storage.version(conn)!=[p.SOURCE] or fingerprint(conn)!=before:raise ValueError('restored snapshot differs')
    print('Restored old data matches; upgrading clone only',flush=True)
    transaction=p.upgrade(CLONE)
    with p.storage.connect(CLONE) as conn:
        if p.storage.version(conn)!=[p.TARGET] or fingerprint(conn)!=before:raise ValueError('clone final data differs')
        schema=verify(conn)
    proof=dict(outcome='SNAPSHOT_SCHEDULE_CLONE_RESTORE_VERIFIED',source=p.SOURCE,target=p.TARGET,
        main=p.storage.MAIN,clone=CLONE,migrations=p.storage.migration_hashes(),executors=p.executor_hashes(),
        backup=dict(path=str(backup),sha256=p.storage.digest(backup),bytes=backup.stat().st_size),
        snapshot=snapshot,before=before,after=transaction['after'],schema=schema,
        mainMigrated=False,sourceCalls=0,at=datetime.now(timezone.utc).isoformat())
    p.protected_write(STATE/'prepare.json',proof)
    with p.storage.connect(p.storage.MAIN) as conn:
        if p.storage.version(conn)!=[p.SOURCE]:raise ValueError('main version unexpectedly changed')
    public={k:v for k,v in proof.items() if k not in ('before','after','snapshot','backup')}
    public.update(preservedTableCount=len(before),oldDataUnchanged=True,backupSha256=proof['backup']['sha256'])
    (ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/y6a-clone-migration-verification.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(outcome=proof['outcome'],preservedTableCount=len(before),mainMigrated=False)),flush=True)
    return proof


if __name__=='__main__':prepare()
