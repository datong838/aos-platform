#!/usr/bin/env python3
"""Read-only Store/metadata physical identity audit; never calls a Host fence or Store effect."""

from __future__ import annotations

import json

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from aos_api.ecom_consistency_store import _apply_transaction_scope
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection, runtime_worker_dsn


IDENTITY_SQL = """SELECT current_database() AS db,
    (SELECT oid FROM pg_database WHERE datname=current_database()) AS db_oid,
    inet_server_addr()::text AS server_addr, inet_server_port() AS server_port,
    pg_postmaster_start_time()::text AS postmaster_start,
    session_user AS login_role, current_user AS active_role,
    to_regprocedure('public.extension_runtime_host_lease_worker_fence_a0v_094(text,text,uuid,bigint)')
        IS NOT NULL AS fence_present,
    coalesce(has_function_privilege('aos_runtime',
        to_regprocedure('public.extension_runtime_host_lease_worker_fence_a0v_094(text,text,uuid,bigint)'),
        'EXECUTE'),false) AS fence_executable"""


def _physical(row):
    return tuple(row[key] for key in ('db', 'db_oid', 'server_addr',
                                      'server_port', 'postmaster_start'))


def classify(metadata, store):
    """Only a candidate, never authorization to wire or execute a Store effect."""
    if type(metadata) is not dict or type(store) is not dict:
        return {'outcome': 'FROZEN_STORE_IDENTITY_AUDIT', 'reason': 'OBSERVATION_SHAPE',
                'automaticAction': False, 'storeEffectAuthorized': False}
    try:
        meta_identity, store_identity = _physical(metadata), _physical(store)
        if any(value is None or value == '' for value in (*meta_identity, *store_identity)):
            return {'outcome': 'FROZEN_STORE_IDENTITY_AUDIT', 'reason': 'PHYSICAL_IDENTITY_UNKNOWN',
                    'automaticAction': False, 'storeEffectAuthorized': False}
        same_database = meta_identity == store_identity
        same_login = metadata['login_role'] == store['login_role']
        if not metadata['login_role'] or not store['login_role']:
            return {'outcome': 'FROZEN_STORE_IDENTITY_AUDIT', 'reason': 'LOGIN_IDENTITY_UNKNOWN',
                    'automaticAction': False, 'storeEffectAuthorized': False}
        runtime_role = store['active_role'] == 'aos_runtime'
        function_present = store['fence_present'] is True
        can_execute = store['fence_executable'] is True
    except KeyError:
        return {'outcome': 'FROZEN_STORE_IDENTITY_AUDIT', 'reason': 'OBSERVATION_INCOMPLETE',
                'automaticAction': False, 'storeEffectAuthorized': False}
    candidate = all((same_database, same_login, runtime_role, function_present, can_execute))
    return {'outcome': ('STORE_LOCAL_FENCE_CANDIDATE_ONLY' if candidate
                        else 'STORE_LOCAL_FENCE_NOT_READY'),
            'samePhysicalDatabase': same_database, 'sameRuntimeLogin': same_login,
            'storeRuntimeRole': runtime_role, 'fenceFunctionPresent': function_present,
            'fenceExecutable': can_execute,
            'automaticAction': False, 'storeEffectAuthorized': False}


def observe():
    with runtime_worker_connection() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        metadata = dict(conn.execute(IDENTITY_SQL).fetchone())
    dsn = runtime_worker_dsn()
    engine = create_engine('postgresql+psycopg://', creator=lambda: psycopg.connect(dsn), poolclass=NullPool)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            _apply_transaction_scope(conn, org_id='dev-org', workspace_id='dev-project')
            store = dict(conn.exec_driver_sql(IDENTITY_SQL).mappings().one())
    finally:
        engine.dispose()
    return metadata, store


if __name__ == '__main__':
    try:
        result = classify(*observe())
    except Exception as error:
        result = {'outcome': 'FROZEN_STORE_IDENTITY_AUDIT',
                  'reason': 'OBSERVATION_' + type(error).__name__,
                  'automaticAction': False, 'storeEffectAuthorized': False}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result['outcome'] == 'FROZEN_STORE_IDENTITY_AUDIT' else 0)
