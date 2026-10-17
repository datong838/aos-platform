"""Read-only catalog comparison shared by purpose and runtime adapters.

Observation alone supplies no identity, approval or execution authority. Callers
must establish their actual database identity and independent pins first.
"""
import hashlib
import json

from aos_api.aip_budget_policy_renewal_store import (
    _SEALED_FUNCTIONS as LEGACY_FUNCTIONS, _SEALED_RELATIONS as LEGACY_RELATIONS,
)


class WindowCatalogBlocked(ValueError):
    pass


_NATIVE = ('command(jsonb,text)', 'relation_shape(oid)', 'profile(text)', 'parent(jsonb,boolean)',
           'expected(jsonb,text)', 'history(jsonb,text,text)', 'proposal_fact(text,text,boolean)',
           'propose(jsonb)', 'decide(jsonb,text)', 'revoke(jsonb,text)', 'consume(jsonb)',
           'reconcile(jsonb,text,text)', 'guard_journal()', 'guard_fence()', 'complete_consume()')
FUNCTIONS = {'public.aip_policy_window_'+s.split('(', 1)[0]+'_v1('+s.split('(', 1)[1] for s in _NATIVE} | {
    'public.aip_budget_cost_hash_a0v_126(jsonb)', 'public.canonical_asset_registry_jsonb(jsonb)',
    'public.guard_aip4_append_only()',
    'public.aip_budget_consumption_fact_a0v_128(text,text,text,text,text,text)',
    'public.aip_budget_cost_actor_a0v_127(text,text,text,text,text)',
    'public.aip_cost_configuration_write_guard_a0v_128()', 'public.aip_renewal_profile_a0v_162(text)'}
TABLES = {'aip_budget_policy_window_'+s for s in ('proposal', 'decision', 'receipt', 'binding', 'fence')}
RELATIONS = TABLES | {'aip_budget_cost_proposal', 'aip_budget_cost_decision', 'aip_budget_cost_revocation',
    'aip_budget_receipt', 'aip_budget_cost_runtime_fence', 'aip_budget_head', 'aip_budget_revision',
    'aip_provider_instance_head', 'aip_provider_instance_revision', 'meta_membership',
    'aip_model_governance_policy_head', 'aip_model_governance_policy_revision',
    'aip_model_price_snapshot_head', 'aip_model_price_snapshot_revision'}

def verify_window_catalog(cursor, *, manifest_sha256, legacy_manifest_sha256):
    row = cursor.execute("SELECT pg_catalog.obj_description('public.aip_budget_policy_window_proposal'"
                         "::regclass,'pg_class') AS seal").fetchone()
    try:
        raw = row['seal']
        if type(raw) is not str or hashlib.sha256(raw.encode()).hexdigest() != manifest_sha256:
            raise ValueError()
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError()
                result[key] = value
            return result
        seal = json.loads(raw, object_pairs_hook=unique)
        if (set(seal) != {'schema', 'functions', 'relations'}
                or seal['schema'] != 'aos-policy-window-native-seal/v1'
                or type(seal['functions']) is not list or len(seal['functions']) != len(FUNCTIONS)
                or {f['signature'] for f in seal['functions']} != FUNCTIONS
                or type(seal['relations']) is not list or len(seal['relations']) != len(RELATIONS)
                or {r['name'] for r in seal['relations']} != RELATIONS):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise WindowCatalogBlocked('POLICY_WINDOW_PINNED_MANIFEST_REQUIRED') from None
    verify_functions(cursor, seal['functions'])
    for expected in seal['relations']:
        row = cursor.execute(_RELATION_METADATA, ('public.'+expected['name'],)).fetchone()
        if not row or row['metadata'] != expected:
            raise WindowCatalogBlocked('POLICY_WINDOW_RELATION_SEAL_DRIFT')
    # The checker-member dependency is in the independently pinned old seal.
    row = cursor.execute("SELECT pg_catalog.obj_description('public.aip_budget_policy_renewal_proposal'"
                         "::regclass,'pg_class') AS seal").fetchone()
    try:
        raw = row['seal']
        if type(raw) is not str or hashlib.sha256(raw.encode()).hexdigest() != legacy_manifest_sha256:
            raise ValueError()
        legacy = json.loads(raw, object_pairs_hook=unique)
        if (set(legacy) != {'schema', 'functions', 'relations'}
                or legacy['schema'] != 'aos-renewal-schema-seal/v1'
                or type(legacy['functions']) is not list or len(legacy['functions']) != len(LEGACY_FUNCTIONS)
                or {f['signature'] for f in legacy['functions']} != LEGACY_FUNCTIONS
                or type(legacy['relations']) is not list or len(legacy['relations']) != len(LEGACY_RELATIONS)
                or {r['name'] for r in legacy['relations']} != LEGACY_RELATIONS):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise WindowCatalogBlocked('POLICY_WINDOW_PINNED_LEGACY_MANIFEST_REQUIRED') from None
    verify_functions(cursor, legacy['functions'])
    legacy_fields = {'name', 'owner', 'rls', 'forceRls', 'acl', 'columns', 'policies'}
    for expected in legacy['relations']:
        row = cursor.execute(_RELATION_METADATA, ('public.'+expected['name'],)).fetchone()
        if (set(expected) != legacy_fields or not row
                or {k: row['metadata'][k] for k in legacy_fields} != expected):
            raise WindowCatalogBlocked('POLICY_WINDOW_LEGACY_RELATION_SEAL_DRIFT')


def verify_functions(cursor, entries):
    for expected in entries:
        row = cursor.execute("""SELECT jsonb_build_object('signature',%s::text,
            'owner',pg_get_userbyid(p.proowner),'definer',p.prosecdef,'config',to_jsonb(p.proconfig),
            'acl',p.proacl::text,'definition',pg_get_functiondef(p.oid)) AS metadata
            FROM pg_catalog.pg_proc p WHERE p.oid=pg_catalog.to_regprocedure(%s)""",
            (expected['signature'], expected['signature'])).fetchone()
        actual = row['metadata'] if row else None
        if actual is not None:
            actual['bodySha256'] = hashlib.sha256(actual.pop('definition').encode()).hexdigest()
        if actual != expected:
            raise WindowCatalogBlocked('POLICY_WINDOW_FUNCTION_SEAL_DRIFT')


# Catalog-only observation: never execute the sealed relation helper.
_RELATION_METADATA = """ SELECT jsonb_build_object('name',c.relname,'owner',pg_get_userbyid(c.relowner),
  'rls',c.relrowsecurity,'forceRls',c.relforcerowsecurity,'acl',c.relacl::text,
  'columns',(SELECT jsonb_agg(jsonb_build_object('name',a.attname,'acl',a.attacl::text) ORDER BY a.attnum)
   FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped),
  'policies',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',p.polname,'roles',to_jsonb(p.polroles),
   'permissive',p.polpermissive,'command',p.polcmd,'using',pg_get_expr(p.polqual,p.polrelid),
   'check',pg_get_expr(p.polwithcheck,p.polrelid)) ORDER BY p.polname)
   FROM pg_policy p WHERE p.polrelid=c.oid),'[]'::jsonb),
  'triggers',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',t.tgname,'enabled',t.tgenabled,
    'definition',pg_get_triggerdef(t.oid)) ORDER BY t.tgname)
   FROM pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal),'[]'::jsonb),
  'indexes',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',ic.relname,
    'definition',pg_get_indexdef(i.indexrelid),'valid',i.indisvalid,'ready',i.indisready)
    ORDER BY ic.relname) FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid
    WHERE i.indrelid=c.oid),'[]'::jsonb),
  'constraints',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',co.conname,
    'type',co.contype,'deferrable',co.condeferrable,'deferred',co.condeferred,
    'definition',pg_get_constraintdef(co.oid)) ORDER BY co.conname)
    FROM pg_constraint co WHERE co.conrelid=c.oid),'[]'::jsonb)) AS metadata
 FROM pg_class c WHERE c.oid=pg_catalog.to_regclass(%s) AND c.relnamespace='public'::regnamespace"""
