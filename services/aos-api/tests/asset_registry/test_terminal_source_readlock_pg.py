"""Future native tests: explicit new PG16 lab only, no bootstrap or fallback.

The separately admitted N runner owns cluster/schema/roles/fixture provenance,
source pins and its persistent once/unknown journal. A Lab object or stash entry
is not admission. This module never discovers credentials or creates resources.
Run with --noconftest; its local autouse fixture prevents inherited DB bootstrap.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from aos_api.asset_registry.composition_contracts import InstallationResponse
from aos_api.asset_registry.control_policy import REINSTALL_INSTALLATION_OPERATION
from aos_api.asset_registry.installation_store import CommandReceipt
from aos_api.asset_registry.reinstall_origin_transaction import (
    ReinstallOriginExecutor, _BoundedReinstallConnection,
)
from aos_api.asset_registry.terminal_source_reader import (
    PostgresTerminalSourceReader, _decode_packet, _WorkLedger,
)
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope

NATIVE_LAB = pytest.StashKey()
DATABASE = 'aos_terminal_source_native'
SCOPE = ('org-org', 'dev-project')
SIX_BRANCHES = ('content', 'approved_failed', 'never_enabled',
                'configured_unactivated', 'enabled_undispatched', 'detached')
COMPLEX_CASES = ('old_shared', 'same_group_new_active', 'dormant_successor',
                 'retained_schedule', 'retained_occurrence', 'event_control', 'business_history')
FUNCTIONS = {
    'public.reinstall_terminal_source_facts_v1(text,text,uuid,bigint)':
        ('terminal_source_readlock_authority.sql', '$terminal_source$', True,
         'aos_terminal_source_reader_owner'),
    'public.automation_schedule_binding_projection_guard_v1()':
        ('../automation_occurrence_projection_authority.sql', '$projection$', True,
         'aos_terminal_source_projection_owner'),
    'public.automation_occurrence_projection_guard_v1()':
        ('../automation_occurrence_projection_authority.sql', '$projection$', True,
         'aos_terminal_source_projection_owner'),
    'public.automation_occurrence_dispatch_attempt_projection_guard_v1()':
        ('../automation_occurrence_projection_authority.sql', '$projection$', True,
         'aos_terminal_source_projection_owner'),
    'public.extension_runtime_resource_origin_guard_v1()':
        ('../extension_runtime_resource_origin_authority.sql', '$resource_origin$', False,
         'aos_terminal_source_projection_owner'),
}
TRIGGERS = {
    'public.automation_schedule_binding_projection_guard_v1()': ('automation_schedule_binding',31),
    'public.automation_occurrence_projection_guard_v1()': ('automation_occurrence',31),
    'public.automation_occurrence_dispatch_attempt_projection_guard_v1()':
        ('automation_occurrence_dispatch_attempt',31),
    'public.extension_runtime_resource_origin_guard_v1()': ('extension_runtime_resource_lease',27),
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class NativeSQLFailure(RuntimeError):
    """Only SQLSTATE is printable; never emit row values or driver diagnostics."""
    def __init__(self, state):
        self.state = state
        super().__init__('native SQLSTATE ' + (state or 'unavailable'))


def execute(conn, statement, params=None):
    try:
        return conn.execute(statement, params)
    except psycopg.Error as error:
        raise NativeSQLFailure(error.sqlstate) from None


def require_native_handle(conn):
    require(type(conn) in (psycopg.Connection, _BoundedReinstallConnection),
            'real qualified psycopg connection required')
    require(conn.autocommit is False and conn.closed is False and conn.row_factory is dict_row,
            'native transaction and dictionary rows required')


ROW_COLUMNS = {
    'automation_schedule_binding': ('org_id','project_id','policy_id','policy_revision','policy_hash',
        'operation_id','installation_id','generation','execution_epoch','timezone','cadence','weekly_day',
        'local_time','effective_from','effective_until','approved','enabled','watermark','revision'),
    'automation_occurrence': ('org_id','project_id','occurrence_id','policy_id','policy_revision','policy_hash',
        'operation_id','installation_id','generation','execution_epoch','scheduled_at','local_slot',
        'trigger_source','source_event_id','status','deadline','claim_owner','claim_until','receipt_ref',
        'created_at','updated_at'),
    'automation_occurrence_dispatch_attempt': ('org_id','project_id','attempt_id','occurrence_id','claim_owner',
        'target_idempotency_key','status','claimed_at','claim_until','receipt_ref','resolved_at'),
    'extension_runtime_resource_lease': ('org_id','project_id','resource_id','operation_id','generation',
        'package_id','package_hash','engine_context','resource_name','owner_token_ref','create_claimed_at',
        'container_id','cleanup_state','observed_release','expires_at'),
}
ROW_KEYS = {
    'automation_schedule_binding': ('org_id','project_id','policy_id','policy_revision'),
    'automation_occurrence': ('org_id','project_id','occurrence_id'),
    'automation_occurrence_dispatch_attempt': ('org_id','project_id','attempt_id'),
    'extension_runtime_resource_lease': ('org_id','project_id','resource_id'),
}
ROW_MUTABLE = {
    'automation_schedule_binding': ('enabled','watermark','revision'),
    'automation_occurrence': ('status','claim_owner','claim_until','receipt_ref','updated_at'),
    'automation_occurrence_dispatch_attempt': ('status','receipt_ref','resolved_at'),
    'extension_runtime_resource_lease': ('create_claimed_at','container_id','cleanup_state','observed_release','expires_at'),
}


@dataclass(frozen=True, repr=False)
class NativeRowCase:
    """Prepared legal values and real parents; no action/SQLSTATE callbacks."""
    table: str
    row: dict = field(repr=False)
    identity_changes: dict = field(repr=False)
    mutable_changes: dict = field(repr=False)

    def __post_init__(self):
        require(self.table in ROW_COLUMNS and type(self.row) is dict
                and set(self.row)==set(ROW_COLUMNS[self.table])
                and (self.row['org_id'],self.row['project_id'])==SCOPE,
                'exact native positive row columns and tenant required')
        identity = set(ROW_COLUMNS[self.table])-set(ROW_MUTABLE[self.table])
        require(set(self.identity_changes)==identity
                and all(value!=self.row[key] for key,value in self.identity_changes.items()),
                'each native identity mutation must actually differ')
        require(set(self.mutable_changes)==set(ROW_MUTABLE[self.table])
                and any(value!=self.row[key] for key,value in self.mutable_changes.items()),
                'legal nonempty native mutable transition required')
        for name in ('row','identity_changes','mutable_changes'):
            object.__setattr__(self,name,MappingProxyType(dict(getattr(self,name))))


def _adapt(value):
    return Jsonb(value) if type(value) in (dict,list) else value


def insert_row(conn, case, changes=None):
    require(type(case) is NativeRowCase, 'exact native data case required')
    columns = ROW_COLUMNS[case.table]
    require(changes is None or (type(changes) is dict and set(changes)<=set(columns)),
            'fixed native negative insertion columns required')
    values = dict(case.row)
    if changes is not None:
        values.update(changes)
    statement = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
        sql.Identifier('public',case.table),
        sql.SQL(',').join(sql.Identifier(column) for column in columns),
        sql.SQL(',').join(sql.Placeholder() for _ in columns))
    result = execute(conn,statement,tuple(_adapt(values[column]) for column in columns))
    require(result.rowcount==1, 'one fresh legal native row required')


def update_row(conn, case, changes):
    require(type(case) is NativeRowCase and type(changes) is dict and bool(changes)
            and set(changes)<=set(ROW_COLUMNS[case.table]), 'fixed native update columns required')
    keys = ROW_KEYS[case.table]
    statement = sql.SQL('UPDATE {} SET {} WHERE {}').format(
        sql.Identifier('public',case.table),
        sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(column)) for column in changes),
        sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(column)) for column in keys))
    params = tuple(_adapt(value) for value in changes.values())+tuple(case.row[key] for key in keys)
    result = execute(conn,statement,params)
    require(result.rowcount==1, 'one exact native row transition required')


def delete_row(conn, case):
    require(type(case) is NativeRowCase, 'exact native delete target required')
    keys = ROW_KEYS[case.table]
    statement = sql.SQL('DELETE FROM {} WHERE {}').format(sql.Identifier('public',case.table),
        sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(column)) for column in keys))
    execute(conn,statement,tuple(case.row[key] for key in keys))


@dataclass(frozen=True, repr=False)
class TerminalNativeCase:
    branch: str
    source_id: UUID
    terminal_revision: int
    port: PostgresTerminalSourceReader
    check_kwargs: dict = field(repr=False)
    executor: ReinstallOriginExecutor = field(repr=False)
    command_kwargs: dict = field(repr=False)

    def __post_init__(self):
        require(self.branch in SIX_BRANCHES and type(self.source_id) is UUID
                and type(self.terminal_revision) is int and self.terminal_revision > 0,
                'native terminal case identity required')
        require(type(self.port) is PostgresTerminalSourceReader
                and type(self.executor) is ReinstallOriginExecutor
                and self.executor._service._origin_store is self.port,
                'original concrete reader and executor required')
        require('conn' not in self.check_kwargs and set(self.check_kwargs) == {
            'org_id','project_id','actor','markings','source','locked_source','source_lock','target','target_lock'},
            'exact original current-check arguments required')
        require((self.check_kwargs['org_id'], self.check_kwargs['project_id']) == SCOPE
                and self.check_kwargs['source'].installation_id == str(self.source_id)
                and self.check_kwargs['source'].terminal_revision == self.terminal_revision,
                'actual source and positive scope required')
        require((self.command_kwargs.get('org_id'), self.command_kwargs.get('project_id')) == SCOPE
                and self.command_kwargs.get('installation_id') == str(self.source_id),
                'original same-source command required')
        object.__setattr__(self, 'check_kwargs', MappingProxyType(dict(self.check_kwargs)))
        object.__setattr__(self, 'command_kwargs', MappingProxyType(dict(self.command_kwargs)))


class TerminalNativeLab:
    """Only transports and prepared native data, no setup/action callbacks."""
    def __init__(self, *, database_oid, reader_connect, probe_connect,
                 cases, projections, resource, source_hashes):
        require(type(database_oid) is int and database_oid > 0
                and callable(reader_connect) and callable(probe_connect),
                'explicit admitted native transports and database OID required')
        require(type(cases) is dict and bool(cases) and set(cases) <= set(SIX_BRANCHES + COMPLEX_CASES)
                and all(type(case) is TerminalNativeCase for case in cases.values()),
                'explicit known native diagnostic sources required')
        require(all(cases[name].branch==name for name in SIX_BRANCHES if name in cases)
                and all(cases[name].branch=='detached' for name in COMPLEX_CASES if name in cases),
                'native scenario labels must retain the original branch')
        require(len({case.source_id for case in cases.values()}) == len(cases),
                'each native source must be fresh and distinct')
        require(type(projections) is dict and set(projections)<=set(ROW_COLUMNS)-{'extension_runtime_resource_lease'}
                and all(type(case) is NativeRowCase and key==case.table for key,case in projections.items())
                and (resource is None or (type(resource) is NativeRowCase and resource.table=='extension_runtime_resource_lease')),
                'exact native projection/resource rows with actual parents required')
        self.database_oid = database_oid
        self.reader_connect, self.probe_connect = reader_connect, probe_connect
        self.cases = MappingProxyType(dict(cases))
        self.projections, self.resource = projections, resource
        self.source_hashes = MappingProxyType(dict(source_hashes))
        self._attempted = set()
        self._sources = self._source_bodies()

    def _source_bodies(self):
        directory = Path(__file__).resolve().parents[2] / 'aos_api' / 'asset_registry'
        found = {}
        for signature, (relative, delimiter, _, _) in FUNCTIONS.items():
            path = (directory / relative).resolve()
            raw = path.read_bytes()
            require(self.source_hashes.get(path.name) == hashlib.sha256(raw).hexdigest(),
                    'independently admitted SQL source pin required')
            text = raw.decode('utf-8')
            start = text.index('CREATE FUNCTION ' + signature.split('(')[0])
            body = text[start:].split(delimiter, 2)[1]
            found[signature] = hashlib.sha256(body.encode('utf-8')).hexdigest()
        return found

    @contextmanager
    def open(self, kind):
        require(kind in ('reader','probe'), 'fixed native transport required')
        factory = self.reader_connect if kind == 'reader' else self.probe_connect
        role = 'aos_terminal_source_native_' + kind
        with factory() as conn:
            require_native_handle(conn)
            try:
                # Only this connection's transaction settings; no DB/schema mutation.
                execute(conn, "SELECT pg_catalog.set_config('statement_timeout','10000ms',true), "
                              "pg_catalog.set_config('lock_timeout','1000ms',true)")
                row = execute(conn, '''SELECT current_database() AS db, d.oid AS db_oid,
                    current_user AS current_role, session_user AS session_role,
                    r.rolsuper, r.rolbypassrls, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolcanlogin,
                    current_setting('server_version_num')::int AS version,
                    current_setting('session_replication_role') AS replication
                    FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r
                      ON r.rolname=session_user WHERE d.datname=current_database()''').fetchone()
                require(row is not None and row['db'] == DATABASE and row['db_oid'] == self.database_oid
                        and row['current_role'] == role and row['session_role'] == role
                        and row['rolcanlogin'] is True
                        and 160000 <= row['version'] < 170000 and row['replication'] == 'origin'
                        and all(row[x] is False for x in ('rolsuper','rolbypassrls','rolcreatedb','rolcreaterole','rolreplication')),
                        'new PG16 non-bypass LOGIN lab identity differs')
                require(conn.info.transaction_status is TransactionStatus.INTRANS,
                        'native transaction required')
                for signature, (_, _, security, owner) in FUNCTIONS.items():
                    stored = execute(conn, '''SELECT p.prosrc,p.prosecdef,p.proconfig,
                        pg_catalog.pg_get_userbyid(p.proowner) AS owner
                        FROM pg_catalog.pg_proc p WHERE p.oid=pg_catalog.to_regprocedure(%s)''',
                        (signature,)).fetchone()
                    require(stored is not None and stored['prosecdef'] is security
                            and stored['owner'] == owner and len(stored['proconfig'] or ()) == 1
                            and stored['proconfig'][0].replace(' ','') == 'search_path=pg_catalog,pg_temp'
                            and hashlib.sha256(stored['prosrc'].encode('utf-8')).hexdigest() == self._sources[signature],
                            'native SQL definition differs from admitted candidate')
                    if signature in TRIGGERS:
                        table,row_type = TRIGGERS[signature]
                        prefix = signature.split('.')[1].split('(')[0].removesuffix('_guard_v1')
                        attached = execute(conn, '''SELECT c.relname AS table_name,t.tgname,
                            t.tgtype,t.tgenabled,t.tgnargs FROM pg_catalog.pg_trigger t
                            JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
                            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                            WHERE t.tgfoid=pg_catalog.to_regprocedure(%s) AND n.nspname='public'
                            ORDER BY t.tgname''',(signature,)).fetchall()
                        observed = {(r['table_name'],r['tgname'],r['tgtype'],r['tgenabled'],r['tgnargs'])
                                    for r in attached}
                        require(observed=={
                            (table,prefix+'_row_v1',row_type,'O',0),
                            (table,prefix+'_truncate_v1',34,'O',0)},
                            'actual candidate triggers must be attached and enabled on exact native tables')
                refresh_key = execute(conn, '''SELECT array_agg(a.attname ORDER BY k.ordinality) AS columns
                    FROM pg_catalog.pg_constraint c
                    CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum,ordinality)
                    JOIN pg_catalog.pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
                    WHERE c.conrelid='public.extension_dispatch_configuration_refresh_receipt'::regclass
                      AND c.contype='p' ''').fetchone()
                require(refresh_key is not None and refresh_key['columns']==[
                    'org_id','project_id','cutover_group_id','activation_operation_id','revision'],
                    'actual activation-scoped native refresh key required')
                apply_asset_transaction_scope(conn, org_id=SCOPE[0], project_id=SCOPE[1])
                yield conn
            finally:
                # Probe/guard tests never inherit context-manager auto-commit.
                conn.rollback()

    def case(self, name):
        require(name in self.cases, 'native case is not prepared; no fallback or skip')
        return self.cases[name]

    def projection_case(self, table):
        require(table in self.projections, 'native projection case is not prepared; no fallback or skip')
        return self.projections[table]

    def resource_case(self):
        require(type(self.resource) is NativeRowCase, 'native resource case is not prepared; no fallback or skip')
        return self.resource

    def require_complete_matrix(self):
        require(set(self.cases)==set(SIX_BRANCHES+COMPLEX_CASES)
                and set(self.projections)==set(ROW_COLUMNS)-{'extension_runtime_resource_lease'}
                and type(self.resource) is NativeRowCase,
                'complete native acceptance requires every source, projection, and resource case')

    def claim(self, label):
        require(label not in self._attempted, 'native attempt already used; reconcile unknown externally')
        self._attempted.add(label)


@pytest.fixture(scope='module', autouse=True)
def _isolated_postgres_database(pytestconfig):
    # Shadow only the unsafe inherited bootstrap fixture for these native files.
    require(pytestconfig.option.noconftest is True and not pytestconfig.option.showlocals,
            'fixed native runner with no conftest/bootstrap/showlocals required')
    lab = pytestconfig.stash.get(NATIVE_LAB, None)
    require(type(lab) is TerminalNativeLab,
            'explicit independently qualified native Lab required; no default database')
    return lab


@pytest.fixture(scope='module')
def terminal_native_lab(_isolated_postgres_database):
    return _isolated_postgres_database


def facts(conn, case, *, org_id=SCOPE[0], revision=None):
    row = execute(conn, '''SELECT public.reinstall_terminal_source_facts_v1(%s,%s,%s,%s) AS facts''',
                  (org_id, SCOPE[1], case.source_id,
                   case.terminal_revision if revision is None else revision)).fetchone()
    require(type(row) is dict and set(row) == {'facts'}, 'one native fact column required')
    packet = row['facts']
    _decode_packet(packet, _WorkLedger())
    receipts = packet['relations']['public.extension_runtime_uninstall_receipt']
    bindings = packet['relations']['public.extension_runtime_binding']
    if case.branch in ('content','approved_failed'):
        tail = [event for event in packet['relations']['public.bundle_installation_event']
                if event['to_revision']==case.terminal_revision and event['to_state']=='uninstalled']
        require(not receipts and not bindings and len(tail)==1
                and tail[0]['from_state']==('active' if case.branch=='content' else 'approved'),
                'native rows must prove the declared unbound branch')
        if case.branch=='approved_failed':
            require(any(operation['status']=='failed'
                        for operation in packet['relations']['public.extension_runtime_operation']),
                    'actual failed preparation history required')
    else:
        require(len(receipts)==len(bindings)==1 and receipts[0]['retirement_kind']==case.branch,
                'actual native retirement kind must prove the declared branch')
    return packet


@pytest.mark.parametrize('case_name', SIX_BRANCHES + COMPLEX_CASES)
def test_real_facts_and_original_current_check_same_transaction(terminal_native_lab, case_name):
    case = terminal_native_lab.case(case_name)
    with terminal_native_lab.open('reader') as conn:
        pid = conn.info.backend_pid
        packet = facts(conn, case)
        if case_name in ('retained_schedule','retained_occurrence','event_control','business_history'):
            family = dict(retained_schedule='automation_schedule_binding',retained_occurrence='automation_occurrence',
                          event_control='extension_event_control_dispatch_receipt',
                          business_history='ecommerce_growth_runtime_command_receipt')[case_name]
            require(bool(packet['relations']['public.'+family]), 'nonempty native historical positive required')
        if case_name == 'same_group_new_active':
            groups = {row['cutover_group_id']
                      for row in packet['relations']['public.extension_dispatch_lifecycle_operation']}
            require(any(r['installation_id'] not in (None,str(case.source_id)) and r['handler_kind']=='extension'
                        and r['cutover_group_id'] in groups
                        for r in packet['relations']['public.extension_operation_dispatch_binding']),
                    'actual new active same-group native target required')
        if case_name == 'dormant_successor':
            parents = {r['receipt_id'] for r in packet['relations']['public.extension_dispatch_lifecycle_receipt']
                       if r['phase']=='detach'}
            active = {r['installation_id'] for r in packet['relations']['public.extension_operation_dispatch_binding']
                      if r['handler_kind']=='extension'}
            require(any(r['payload']['request']['predecessorDetachReceiptRef']['resourceId'] in parents
                        and r['installation_id'] not in active
                        for r in packet['predecessors']['public.extension_dispatch_successor_registration_receipt']),
                    'actual dormant native successor receipt required')
        if case_name == 'old_shared':
            successors = (packet['relations']['public.extension_dispatch_successor_registration_receipt']+
                          packet['predecessors']['public.extension_dispatch_successor_registration_receipt'])
            children = {}
            for row in successors:
                parent = row['payload']['request']['predecessorDetachReceiptRef']['resourceId']
                children.setdefault(parent,set()).add((row['installation_id'],row['generation']))
            require(any(len(targets)>=2 for targets in children.values()),
                    'nonempty shared ancestor graph required')
        require(PostgresTerminalSourceReader.check_current(case.port, conn, **case.check_kwargs) is True,
                'original full concrete current check must succeed')
        require(conn.info.backend_pid == pid and conn.info.transaction_status is TransactionStatus.INTRANS,
                'same original transaction must retain native locks')


@pytest.mark.parametrize('branch', SIX_BRANCHES)
def test_original_executor_commit_origin_command_and_known_replay(terminal_native_lab, branch):
    case = terminal_native_lab.case(branch)
    settings = case.executor._owner._settings
    with terminal_native_lab.open('reader') as checked:
        require(settings.dbname == DATABASE and settings.user == 'aos_terminal_source_native_reader'
                and settings.host == checked.info.host and settings.port == checked.info.port,
                'original purpose executor must use exactly the admitted native endpoint')
        facts(checked,case)
    key = case.command_kwargs['idempotency_key']
    require(case.executor._service._origin_store is case.port,
            'original executor must still call the exact concrete reader')
    terminal_native_lab.claim(('reinstall',case.source_id,key))
    receipt = case.executor.reinstall(**case.command_kwargs)
    require(type(receipt) is CommandReceipt and receipt.status_code == 201 and receipt.replayed is False,
            'new original committed command receipt required')
    target = InstallationResponse.model_validate(receipt.response_json)
    require(target.installation_id != str(case.source_id) and target.state == 'draft',
            'new original target draft required')
    with terminal_native_lab.open('probe') as observer:
        origin = execute(observer, '''SELECT o.target_revision,o.source_terminal_revision,o.actor,
            s.installation_id AS source_id,t.installation_id AS target_id
            FROM public.bundle_installation_reinstall_origin o
            JOIN public.bundle_installation s ON (s.org_id,s.project_id,s.installation_pk)=
              (o.org_id,o.project_id,o.source_installation_pk)
            JOIN public.bundle_installation t ON (t.org_id,t.project_id,t.installation_pk)=
              (o.org_id,o.project_id,o.target_installation_pk)
            WHERE o.org_id=%s AND o.project_id=%s AND s.installation_id=%s AND t.installation_id=%s''',
            (*SCOPE,case.source_id,UUID(target.installation_id))).fetchall()
        command = execute(observer, '''SELECT response_json FROM public.bundle_installation_command
            WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s''',
            (*SCOPE,REINSTALL_INSTALLATION_OPERATION,key)).fetchall()
        require(len(origin)==1 and origin[0]['target_revision']==1
                and origin[0]['source_terminal_revision']==case.terminal_revision
                and origin[0]['actor']==case.command_kwargs['actor']
                and len(command)==1 and command[0]['response_json']==receipt.response_json,
                'same native database must visibly contain exact committed origin and command')
    # Allowed only after the actual first commit was independently visible above.
    replay = case.executor.reinstall(**case.command_kwargs)
    require(type(replay) is CommandReceipt and replay.replayed is True
            and replay.response_json==receipt.response_json, 'known original idempotent replay differs')


@pytest.mark.parametrize('mode', ('tenant','revision'))
def test_actual_scope_and_revision_rejected(terminal_native_lab, mode):
    case = terminal_native_lab.case('content')
    with terminal_native_lab.open('reader') as conn:
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():
                facts(conn,case,org_id='dev-org' if mode=='tenant' else SCOPE[0],
                      revision=case.terminal_revision+1 if mode=='revision' else None)
        require(observed.value.state in (('42501',) if mode=='tenant' else ('P0002','40001')),
                'native denial SQLSTATE differs')


def test_root_lock_survives_function_return_until_original_transaction_ends(terminal_native_lab):
    case = terminal_native_lab.case('content')
    with terminal_native_lab.open('reader') as reader:
        facts(reader,case)
        with terminal_native_lab.open('probe') as writer:
            with pytest.raises(NativeSQLFailure) as observed:
                with writer.transaction():
                    execute(writer, '''SELECT installation_pk FROM public.bundle_installation
                        WHERE org_id=%s AND project_id=%s AND installation_id=%s
                        FOR KEY SHARE NOWAIT''',(*SCOPE,case.source_id))
            require(observed.value.state=='55P03', 'native root parent barrier must remain held')
    with terminal_native_lab.open('probe') as writer:
        row = execute(writer, '''SELECT installation_pk FROM public.bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE NOWAIT''',
            (*SCOPE,case.source_id)).fetchone()
        require(row is not None, 'original transaction cleanup must release root lock')


def _parent_lock(packet, case, kind, mode):
    require(mode in ('FOR KEY SHARE NOWAIT','FOR UPDATE NOWAIT'), 'fixed native lock mode required')
    if kind == 'head':
        return ('SELECT installation_pk FROM public.bundle_installation WHERE org_id=%s '
                'AND project_id=%s AND installation_id=%s '+mode, (*SCOPE,case.source_id))
    if kind == 'runtime_event':
        rows = packet['relations']['public.extension_runtime_event']
        require(bool(rows), 'actual nonempty runtime event parent required')
        row = rows[0]
        return ('SELECT event_id FROM public.extension_runtime_event WHERE org_id=%s AND project_id=%s '
                'AND operation_id=%s AND sequence=%s '+mode,
                (*SCOPE,UUID(row['operation_id']),row['sequence']))
    require(kind=='bundle_version', 'fixed native parent kind required')
    rows = packet['registry']['public.asset_bundle_version']
    require(bool(rows), 'actual selected Registry version required')
    return ('SELECT version_pk FROM public.asset_bundle_version WHERE version_pk=%s '+mode,
            (UUID(rows[0]['version_pk']),))


@pytest.mark.parametrize('kind',('runtime_event','bundle_version'))
def test_native_child_parent_barrier_held_after_function_returns(terminal_native_lab, kind):
    case = terminal_native_lab.case('detached')
    with terminal_native_lab.open('reader') as reader:
        packet = facts(reader,case)
        statement,params = _parent_lock(packet,case,kind,'FOR KEY SHARE NOWAIT')
        with terminal_native_lab.open('probe') as writer:
            require(reader.info.backend_pid!=writer.info.backend_pid, 'independent native backends required')
            with pytest.raises(NativeSQLFailure) as observed:
                with writer.transaction():execute(writer,statement,params)
            require(observed.value.state=='55P03', 'native selected parent barrier is missing')
    with terminal_native_lab.open('probe') as writer:
        require(execute(writer,statement,params).fetchone() is not None,
                'selected parent must become available after original cleanup')


@pytest.mark.parametrize('kind',('head','runtime_event','bundle_version'))
def test_native_reader_refuses_preexisting_parent_writer_lock(terminal_native_lab, kind):
    case = terminal_native_lab.case('detached')
    with terminal_native_lab.open('reader') as discovery:
        packet = facts(discovery,case)
    statement,params = _parent_lock(packet,case,kind,'FOR UPDATE NOWAIT')
    with terminal_native_lab.open('probe') as writer:
        require(execute(writer,statement,params).fetchone() is not None,
                'real original parent row required before native contention')
        with terminal_native_lab.open('reader') as reader:
            require(reader.info.backend_pid!=writer.info.backend_pid, 'independent native backends required')
            with pytest.raises(NativeSQLFailure) as observed:
                with reader.transaction():facts(reader,case)
            require(observed.value.state=='55P03', 'native reader must refuse a held parent without late retry')


def test_complete_native_fixture_matrix_is_present(terminal_native_lab):
    terminal_native_lab.require_complete_matrix()
