"""Prospective dedicated original Source reader; never automatic installation.

The new fixed native caller uses the complete trusted original consumer. No old
LOGIN, Source definition, private privilege or permission claim is substituted.
This module alone is not a qualified native Guard or formal Source authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from psycopg.types.json import Jsonb

from aos_api.aip_model_route_eval_manifest import _alias_input
from aos_api.aip_provider_capacity_catalog_audit_profile import catalog_occupation_statements
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
from aos_api.aip_provider_capacity_publication_contracts import (
    PublishedProviderCapacitySourceV2,parse_signed_capacity_body,
)

SESSION='aos_model_route_eval'
OWNER='aos_capacity_publication_owner'
READER='public.read_capacity_source_for_model_route_eval(bytea,jsonb)'
AUDITOR='public.require_model_route_eval_source_installation()'
_LEGACY_HASHES=(
    '170238e1cbd2fd1fc010f43bf3887c7d49a2eb53d6b6aba53b14505dc1e82260',
    '9437df2ab2c2c2d8eae0511e43a68c2e8796600b8d3230e874a1ea2125979cbd',
    '90150bf23d3c651268953fbf01757aeb18a3c0aa95152445c427953b84d0f918',
    '75f36e4f880a27c331d2a511190c911b35d1f9b985dd095af818524d7c2a77ab',
    'bd7edcd0057f4e2bce4d838da44bf7fd5cc3b50045689425566d11b9d66b91a3',
    '11079ec293dff3e9edfa06d5df8c8b9f760a442c6104202278f1a2a45d01fa19',
    '4d56898ce894b10a26e73ca82fbc64f3cf2d2588a79b04d60b8b0aa144742272',
)


class ModelRouteSourceRejected(ValueError):
    """Fixed safe category; never includes commands, JWTs or Source packets."""


def _body(statement,delimiter):
    matches=re.findall(r'AS \$'+delimiter+r'\$(.*?)\$'+delimiter+r'\$;',statement,re.S)
    if len(matches)!=1:raise ValueError('one exact trusted SQL body required')
    return matches[0]


def source_bridge_statements():
    """Compile two NEW functions only; no connection, role creation or grants to data.

    The existing publication NOLOGIN Owner retains its original privileges.
    Installing a new function owned by it is a separately reviewed deployment
    action, never performed by this compiler or the runtime reader.
    """
    try:
        old=catalog_occupation_statements()
        if tuple(hashlib.sha256(s.encode()).hexdigest() for s in old)!=_LEGACY_HASHES:
            raise ValueError('trusted original compiler drift')
        replacements=(
            ('aos_provider_capacity_occupation',SESSION,(20,0,0,0,16,0,0)),
            # Include bare proname literals in the overload-count audit too.
            ('read_capacity_source_for_occupation',READER.split('(')[0].split('.')[1],(1,1,1,1,2,0,0)),
            ('require_capacity_occupation_source_installation',AUDITOR.split('(')[0].split('.')[1],(1,0,0,0,3,1,1)),
        )
        result=list(old)
        for before,after,counts in replacements:
            for index,count in enumerate(counts):
                if result[index].count(before)!=count:raise ValueError('exact substitution count required')
                result[index]=result[index].replace(before,after)
        before=hashlib.sha256(_body(old[0],'consumer').encode()).hexdigest()
        after=hashlib.sha256(_body(result[0],'consumer').encode()).hexdigest()
        if result[4].count(before)!=1:raise ValueError('one self-audit digest required')
        result[4]=result[4].replace(before,after)
        return tuple(result)
    except (ValueError,TypeError,IndexError,AttributeError):
        raise ModelRouteSourceRejected('MODEL_ROUTE_SOURCE_COMPILER_DRIFTED') from None


def _context(conn):
    from aos_api.aip_model_route_eval_owner import _require_native_connection
    _require_native_connection(conn)
    row=conn.execute("""SELECT pg_catalog.current_database() AS database,
        (SELECT oid FROM pg_catalog.pg_database WHERE datname=pg_catalog.current_database()) AS database_oid,
        session_user AS login,current_user AS role,
        pg_catalog.current_setting('aos.org_id',true) AS org_id,
        pg_catalog.current_setting('aos.project_id',true) AS project_id,
        pg_catalog.current_setting('transaction_isolation') AS isolation,
        pg_catalog.current_setting('transaction_read_only') AS readonly,
        pg_catalog.current_setting('TimeZone') AS time_zone,
        pg_catalog.current_setting('session_replication_role') AS replication,
        pg_catalog.pg_current_xact_id()::text AS xid,pg_catalog.pg_backend_pid() AS pid,
        pg_catalog.clock_timestamp() AS now""").fetchone()
    if (type(row) is not dict
        or (row.get('login'),row.get('role'),row.get('org_id'),row.get('project_id'),
            row.get('isolation'),row.get('readonly'),row.get('time_zone'),row.get('replication'))
            !=(SESSION,'aos_runtime','org-org','dev-project','serializable','off','UTC','origin')
        or type(row.get('database')) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',row['database']) is None
        or type(row.get('database_oid')) is not int or row['database_oid']<1
        or type(row.get('pid')) is not int or row['pid']<1
        or type(row.get('xid')) is not str or re.fullmatch(r'[1-9][0-9]*',row['xid']) is None
        or type(row.get('now')) is not datetime or row['now'].utcoffset() is None):
        raise ValueError('same dedicated native caller required')
    return row


def _require_definitions(conn):
    statements=source_bridge_statements()
    for signature,index,delimiter,secdef,result_type in (
            (READER,0,'consumer',True,2249),(AUDITOR,4,'occupation',False,2278)):
        row=conn.execute("""SELECT p.prosrc,r.rolname,p.prosecdef,p.proconfig,
            p.proisstrict,p.provolatile,p.proparallel,p.prokind,p.proretset,p.prorettype,
            p.proargtypes::text AS args,p.pronargdefaults,p.provariadic,p.proleakproof,
            p.prosupport::oid AS support,l.lanname
            FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
            JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=pg_catalog.to_regprocedure(%s)""",(signature,)).fetchone()
        if (type(row) is not dict or row.get('prosrc')!=_body(statements[index],delimiter)
            or row.get('rolname')!=OWNER or row.get('prosecdef') is not secdef
            or row.get('proconfig')!=['search_path=pg_catalog']
            or row.get('proisstrict') is not False or row.get('provolatile')!='v'
            or row.get('proparallel')!='u' or row.get('prokind')!='f'
            or row.get('proretset') is not secdef or row.get('prorettype')!=result_type
            or row.get('args')!=('17 3802' if secdef else '')
            or row.get('pronargdefaults')!=0 or row.get('provariadic')!=0
            or row.get('proleakproof') is not False or row.get('support')!=0
            or row.get('lanname')!='plpgsql'):
            raise ValueError('exact original bridge definition required')
        # The SQL auditor additionally checks complete argument names/modes,
        # Owner role/edges, original installation, function ACLs and overloads.
        acl=conn.execute("""SELECT coalesce(r.rolname,'PUBLIC') AS grantee,
            g.rolname AS grantor,a.privilege_type,a.is_grantable
            FROM pg_catalog.pg_proc p CROSS JOIN LATERAL
            pg_catalog.aclexplode(coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
            LEFT JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
            JOIN pg_catalog.pg_roles g ON g.oid=a.grantor
            WHERE p.oid=pg_catalog.to_regprocedure(%s)""",(signature,)).fetchall()
        expected={OWNER,'aos_runtime'} if secdef else {OWNER}
        if (len(acl)!=len(expected) or {r['grantee'] for r in acl}!=expected
            or any(r['grantor']!=OWNER or r['privilege_type']!='EXECUTE'
                or r['is_grantable'] is not False for r in acl)):
            raise ValueError('exact bridge execute privilege required')


def consume_route_eval_capacity_source(conn,command):
    """Read current signed Source on one retained new native caller; no permission.

    The complete original SQL consumer performs Source/provenance/physical/
    signature/current Owner checks. Its input is the original verified current
    OIDC packet; this function never trusts a supplied principal or facts dict.
    Actual Source use requires the separately qualified native bridge and Guard.
    """
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    try:
        before=_context(conn)
        if type(command) is not ProviderCapacityConsumptionCommand:
            raise ValueError('original typed command required')
        command=ProviderCapacityConsumptionCommand.model_validate(_alias_input(command)).model_copy(deep=True)
        _require_definitions(conn)
        packet=_consumption_packet(command);ref=command.source_ref
        if type(packet) is not bytes:
            raise ValueError('original verified authentication packet required')
        auth=json.loads(packet)
        deadline=datetime.fromisoformat(auth['authentication']['authenticationExpiresAt'].replace('Z','+00:00'))
        if (auth.get('protocol')!='aos-provider-capacity-source-consumption/v1'
            or auth.get('tenant')!={'orgId':'org-org','projectId':'dev-project'}
            or auth.get('sourceRef')!=ref.model_dump(mode='json',by_alias=True)
            or deadline.utcoffset() is None or deadline<=before['now']):
            raise ValueError('current original authentication window required')
        row=conn.execute('SELECT * FROM public.read_capacity_source_for_model_route_eval(%s,%s::jsonb)',
            (packet,Jsonb(ref.model_dump(mode='json',by_alias=True)))).fetchone()
        if type(row) is not dict or _consumption_packet(command)!=packet:
            raise ValueError('original current Source and authentication required')
        raw=bytes(row['source_raw']);source=parse_signed_capacity_body(raw,PublishedProviderCapacitySourceV2)
        after=_context(conn);at=after['now']
        if (any(after[k]!=v for k,v in before.items() if k!='now') or at<before['now'] or at>=deadline
            or (row['asset_id'],row['revision'],row['content_hash'])!=(ref.asset_id,ref.revision,ref.content_hash)
            or type(row['revision']) is not int or row['revision']!=1
            or hashlib.sha256(raw).hexdigest()!=ref.content_hash
            or (source.asset_id,source.revision)!=(ref.asset_id,ref.revision)
            or (source.tenant.org_id,source.tenant.project_id)!=('org-org','dev-project')
            or source.execution_allowed is not False
            or source.deployment_target.database!=after['database']
            or source.deployment_target.database_oid!=after['database_oid']
            or not source.valid_from<=at<source.valid_until or source.issued_at>at):
            raise ValueError('same caller and exact current Source required')
        return source
    except Exception:
        raise ModelRouteSourceRejected('MODEL_ROUTE_CURRENT_SOURCE_REQUIRED') from None
