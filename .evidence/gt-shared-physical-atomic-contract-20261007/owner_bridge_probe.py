"""Isolated dedicated Owner delegation to the untouched complete Source reader."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
from tests.aip._runtime_guard_history_fixture import isolated_owner

BASE=Path(__file__).resolve().parent
TARGET='test_occupation_source_consumption_uses_actual_business_caller'
SOURCE_OWNER='aos_capacity_publication_owner'

def probe(caller,source,command,sign,subject):
    suffix=uuid4().hex[:12]
    role='gt_physical_probe_'+suffix
    bridge='gt_source_bridge_'+suffix
    entry='gt_physical_reader_'+suffix
    original_signatures=['public.read_capacity_source_for_occupation(bytea,jsonb)',
        'public.require_capacity_occupation_source_installation()']
    original_query='''SELECT oid::regprocedure::text AS signature,prosrc,proacl::text,proowner,
        proconfig,prosecdef FROM pg_proc WHERE oid=ANY(%s::regprocedure[]) ORDER BY oid'''
    with isolated_owner() as admin:
        before=admin.execute(original_query,(original_signatures,)).fetchall()
        admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role)))
        admin.execute(sql.SQL("COMMENT ON ROLE {} IS 'Owned isolated Source bridge contract probe; no formal authority'").format(sql.Identifier(role)))
        admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
        # This trusted, fixed delegation body adds no permission to an original
        # function or table and never trusts a Python-provided Source object.
        returns='asset_id text,revision integer,content_hash text,source_raw bytea,signature bytea'
        admin.execute(sql.SQL('''CREATE FUNCTION public.{}(p_raw bytea,p_ref jsonb)
            RETURNS TABLE('''+returns+''') LANGUAGE plpgsql VOLATILE SECURITY DEFINER
            SET search_path=pg_catalog AS $probe$
            BEGIN
             RETURN QUERY SELECT * FROM public.read_capacity_source_for_occupation(p_raw,p_ref);
            END $probe$''').format(sql.Identifier(bridge)))
        admin.execute(sql.SQL('ALTER FUNCTION public.{}(bytea,jsonb) OWNER TO {}').format(sql.Identifier(bridge),sql.Identifier(SOURCE_OWNER)))
        admin.execute(sql.SQL('REVOKE ALL ON FUNCTION public.{}(bytea,jsonb) FROM PUBLIC').format(sql.Identifier(bridge)))
        admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION public.{}(bytea,jsonb) TO {}').format(sql.Identifier(bridge),sql.Identifier(role)))
        admin.execute(sql.SQL('''CREATE FUNCTION public.{}(p_raw bytea,p_ref jsonb)
            RETURNS TABLE('''+returns+''') LANGUAGE plpgsql VOLATILE SECURITY DEFINER
            SET search_path=pg_catalog AS $probe$
            BEGIN
             RETURN QUERY SELECT * FROM public.{}(p_raw,p_ref);
            END $probe$''').format(sql.Identifier(entry),sql.Identifier(bridge)))
        admin.execute(sql.SQL('ALTER FUNCTION public.{}(bytea,jsonb) OWNER TO {}').format(sql.Identifier(entry),sql.Identifier(role)))
        admin.execute(sql.SQL('REVOKE ALL ON FUNCTION public.{}(bytea,jsonb) FROM PUBLIC').format(sql.Identifier(entry)))
        admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION public.{}(bytea,jsonb) TO aos_runtime').format(sql.Identifier(entry)))
        # A Source-private/C-verifier/direct-RPC grant would invalidate the
        # proposed independent Owner separation, even if the positive read worked.
        privileges=admin.execute('''SELECT
            has_schema_privilege(%s,'aos_capacity_publication_private','USAGE') AS private_usage,
            has_table_privilege(%s,'aos_capacity_publication_private.source_publication','SELECT') AS private_read,
            has_function_privilege(%s,'public.read_capacity_source_for_occupation(bytea,jsonb)','EXECUTE') AS direct_source,
            has_function_privilege(%s,'aos_ed25519.verify(bytea,bytea,bytea)','EXECUTE') AS verifier,
            (SELECT count(*) FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole) AS memberships''',
            (role,role,role,role,role,role)).fetchone()
        assert privileges==dict(private_usage=False,private_read=False,direct_source=False,verifier=False,memberships=0)
        assert admin.execute(original_query,(original_signatures,)).fetchall()==before
    def read(item,packet_override=None):
        caller.execute("SET LOCAL TimeZone='UTC'")
        apply_transaction_scope(caller,TenantScope('org-org','dev-project'))
        packet=_consumption_packet(item) if packet_override is None else packet_override
        ref=Jsonb(item.source_ref.model_dump(mode='json',by_alias=True))
        return caller.execute(sql.SQL('SELECT * FROM public.{}(%s,%s::jsonb)').format(sql.Identifier(entry)),(packet,ref)).fetchone()
    result=None
    try:
        identity=caller.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid').fetchone()
        row=read(command.model_copy(update={'bearer_token':sign(subject)}))
        assert parse_signed_capacity_body(bytes(row['source_raw']),PublishedProviderCapacitySourceV2)==source
        assert row['content_hash']==command.source_ref.content_hash
        assert caller.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid').fetchone()==identity
        caller.rollback()
        denied=[]
        from aos_api.errors import ApiError
        from aos_api.asset_registry.canonical_json import canonical_json
        # The original packet carries verified claims, not a JWT signature.
        # Keep client JWT verification explicit; do not mislabel it SQL proof.
        try:
            _consumption_packet(command.model_copy(update={'bearer_token':sign(subject,wrong_key=True)}))
        except ApiError:
            denied.append(dict(case='wrong_signature',stage='original_client_JWT_guard'))
        else:raise AssertionError('Original JWT client admitted invalid signature')
        fresh=command.model_copy(update={'bearer_token':sign(subject)})
        expired=json.loads(_consumption_packet(fresh))
        expired['authentication']['authenticationExpiresAt']='1970-01-01T00:00:00Z'
        for label,item,packet in [
            ('expired_authentication_packet',fresh,canonical_json(expired)),
            ('wrong_ref',command.model_copy(update={'bearer_token':sign(subject),
                'source_ref':command.source_ref.model_copy(update={'content_hash':'0'*64})}),None)]:
            try:
                read(item,packet)
            except psycopg.Error as error:
                assert error.sqlstate in ('22023','42501')
                denied.append(dict(case=label,stage='native_SQL_bridge',sqlstate=error.sqlstate))
            else:raise AssertionError('Source bridge admitted '+label)
            finally:caller.rollback()
        with isolated_owner() as admin:
            admin.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            admin.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(admin,TenantScope('org-org','dev-project'))
            try:
                admin.execute(sql.SQL('SELECT * FROM public.{}(%s,%s::jsonb)').format(sql.Identifier(entry)),
                    (_consumption_packet(command.model_copy(update={'bearer_token':sign(subject)})),Jsonb(command.source_ref.model_dump(mode='json',by_alias=True))))
            except psycopg.Error as error:
                assert error.sqlstate=='42501'
                denied.append(dict(case='ordinary_admin_runtime_session',sqlstate=error.sqlstate))
            else:raise AssertionError('Ordinary runtime session admitted')
            finally:admin.rollback()
        result=dict(status='DEDICATED_OWNER_SOURCE_BRIDGE_NATIVE_VERIFIED',database=caller.info.dbname,
            source_hash=command.source_ref.content_hash,actual_caller=identity,role=role,
            private_privileges=privileges,denials=denied,original_source_definitions_unchanged=True,
            limitations=['Fixed test-owned delegation prototype only; no physical hold/budget/Intent or business execution',
                'Production needs exact bridge/Owner catalog audit and full joint locking/cutover; not authorized by this test'])
    finally:
        caller.rollback()
        with isolated_owner() as admin:
            admin.execute(sql.SQL('DROP FUNCTION public.{}(bytea,jsonb)').format(sql.Identifier(entry)))
            admin.execute(sql.SQL('DROP FUNCTION public.{}(bytea,jsonb)').format(sql.Identifier(bridge)))
            admin.execute(sql.SQL('REVOKE USAGE ON SCHEMA public FROM {}').format(sql.Identifier(role)))
            assert admin.execute(original_query,(original_signatures,)).fetchall()==before
            flags=admin.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
            assert flags and not any(flags.values())
            assert admin.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(role,role)).fetchone()['n']==0
    assert result is not None
    result['test_owned_functions_removed']=True
    (BASE/'owner-bridge-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],'same_xid_pid original_source_ACL_unchanged dedicated_private_grants0 clientJWT_and_3native_negativegates cleanup_complete',flush=True)

class ProbePlugin:
    module=None
    original=None
    def pytest_runtest_setup(self,item):
        if item.originalname==TARGET:
            self.module=item.module;self.original=item.module._assert_occupation_epoch_concurrency
            def wrapped(*args):
                probe(*args)
                return self.original(*args)
            item.module._assert_occupation_epoch_concurrency=wrapped
    def pytest_runtest_teardown(self,item,nextitem):
        if self.module is not None:
            self.module._assert_occupation_epoch_concurrency=self.original
            self.module=None
