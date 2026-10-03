"""Original Plan Store under a disposable, nonowner signed-source issuer."""

import secrets
import tempfile
from contextlib import nullcontext
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractConflict,
    ProductionContractDependencyBlocked, ProductionContractIdempotencyConflict,
    ProductionContractNotFound, SignedBIPlanReceiptReader,
    SignedBIPlanRebindReceiptReader,
)
from aos_api.aip_production_contracts import ReviseResponsibilityPlanRequest
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_assignment import CreateResponsibilitySuccessorRequest
from aos_api.aip_responsibility_assignment_store import (
    AipResponsibilityAssignmentStore, ResponsibilityAssignmentBlocked,
)
from aos_api.ecommerce_business_investigation_aip_authority import (
    build_responsibility_plan_request,
)
from aos_api.aip_responsibility_template_authority import ApprovedBIPreparationResolver
from aos_api.aip_business_investigation_responsibility_template import BI_ROLE_BLUEPRINTS
from aos_api.auth import Principal
from aos_api.aip_bi_plan_issuer_connection import (
    BIIssuerDatabaseConfig, connect_bi_issuer_read_only, connect_bi_issuer_write,
)
from aos_api.db import connect, connect_read_only, get_dsn
from aos_api.ecommerce_business_investigation_aip_authority import (
    SignedBIPlanActiveRebindService, SignedBIPlanPreparationService,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope('org-org', 'dev-project')


def assert_original_plan_store_with_restricted_login(selected_template, signed, trust, installed):
    dbname = conninfo_to_dict(get_dsn())['dbname']
    assert dbname.startswith('aos_test_') and dbname.endswith('_ti4_test')
    issuer = 'aos_bi_plan_issuer'
    password = secrets.token_urlsafe(24)
    resolver = ApprovedBIPreparationResolver(
        connect_factory=connect, registry_connect_factory=connect,
        release_root=signed['signed_tree'], trust_roots=trust,
        source_alias=signed['source_alias'],
    )
    request = build_responsibility_plan_request(
        {instance_id: 1 for _, _, instance_id, _, _ in BI_ROLE_BLUEPRINTS},
        template_ref=selected_template.template_ref,
    )
    assert resolver.resolve(SCOPE, selected_template.template_ref) is True
    prepared_reader_resolver = ApprovedBIPreparationResolver(
        connect_factory=connect_read_only,
        registry_connect_factory=lambda: connect_read_only(SCOPE),
        release_root=signed['signed_tree'], trust_roots=trust,
        source_alias=signed['source_alias'],
        registry_prepared_transaction=True,
    )
    assert prepared_reader_resolver.resolve(SCOPE, selected_template.template_ref) is True
    assert resolver.resolve(TenantScope('dev-org', 'dev-project'),
                            selected_template.template_ref) is False
    assert resolver.resolve(SCOPE, selected_template.template_ref.model_copy(
        update={'content_hash': '0' * 64})) is False
    with psycopg.connect(get_dsn(), autocommit=True) as admin:
        admin.execute(sql.SQL('''CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
            PASSWORD {}''').format(sql.Identifier(issuer), sql.Literal(password)))
        private_context = None
        try:
            for table, privileges in (
                ('bundle_installation', 'SELECT'),
                ('bundle_installation_revision', 'SELECT'),
                ('bundle_installation_event', 'SELECT'),
                ('bundle_installation_decision', 'SELECT'),
                ('bundle_composition', 'SELECT'),
                ('bundle_composition_lock', 'SELECT'),
                ('aip_responsibility_plan_head', 'SELECT,INSERT,UPDATE'),
                ('aip_responsibility_plan_revision', 'SELECT,INSERT'),
                ('aip_production_contract_receipt', 'SELECT,INSERT'),
                ('aip_agent_instance', 'SELECT'),
                ('aip_skill_binding', 'SELECT'),
                ('aip_skill_template_revision', 'SELECT'),
                ('aip_agent_registry_receipt', 'SELECT'),
                ('aip_responsibility_successor', 'SELECT'),
            ):
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(
                    sql.SQL(privileges), sql.Identifier(table), sql.Identifier(issuer)))
            for table in (
                'bundle_installation', 'bundle_installation_revision',
                'bundle_installation_event', 'bundle_installation_decision',
                'bundle_composition', 'bundle_composition_lock',
                'aip_responsibility_plan_head', 'aip_responsibility_plan_revision',
                'aip_production_contract_receipt', 'aip_agent_instance',
                'aip_skill_binding', 'aip_agent_registry_receipt',
                'aip_responsibility_successor',
            ):
                admin.execute(sql.SQL('''CREATE POLICY {} ON {} TO {}
                    USING(org_id=current_setting('aos.org_id',true)
                      AND project_id=current_setting('aos.project_id',true))
                    WITH CHECK(org_id=current_setting('aos.org_id',true)
                      AND project_id=current_setting('aos.project_id',true))''').format(
                          sql.Identifier('s3owi_' + table), sql.Identifier(table),
                          sql.Identifier(issuer)))
            admin.execute(sql.SQL('''CREATE FUNCTION s3owi_plan_receipt_guard() RETURNS trigger
                LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
                BEGIN
                  IF session_user<>{} OR current_user<>{}
                     OR NEW.operation NOT IN ('responsibility_plan.create',
                                             'responsibility_plan.revise',
                                             'responsibility_plan.freeze',
                                             'bi_responsibility_plan.prepare')
                     OR NEW.result_ref->>'resourceType'<>'ResponsibilityPlanRevision'
                     OR NOT EXISTS (
                       SELECT 1 FROM aip_responsibility_plan_head h
                       JOIN aip_responsibility_plan_revision r
                         ON r.org_id=h.org_id AND r.project_id=h.project_id
                        AND r.plan_id=h.plan_id AND r.revision=h.current_revision
                       WHERE h.org_id=NEW.org_id AND h.project_id=NEW.project_id
                         AND h.plan_id=NEW.result_ref->>'resourceId'
                         AND r.revision=(NEW.result_ref->>'revision')::bigint
                         AND r.content_hash=NEW.result_ref->>'contentHash') THEN
                    RAISE EXCEPTION 'PLAN_RECEIPT_UNPAIRED' USING ERRCODE='42501';
                  END IF;
                  IF NEW.idempotency_key='s3owi-forced-rollback' THEN
                    RAISE EXCEPTION 'PLAN_FORCED_ROLLBACK';
                  END IF;
                  RETURN NEW;
                END $$''').format(sql.Literal(issuer), sql.Literal(issuer)))
            admin.execute('''CREATE TRIGGER s3owi_plan_receipt_guard BEFORE INSERT
                ON aip_production_contract_receipt FOR EACH ROW
                EXECUTE FUNCTION s3owi_plan_receipt_guard()''')
            admin.execute(sql.SQL('''CREATE FUNCTION public.aos_bi_plan_installation_lock_a0v_136(
                p_org text,p_project text,p_installation uuid,p_etag bigint) RETURNS uuid
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                DECLARE found_pk uuid; found_etag bigint;
                BEGIN
                  IF session_user<>{} OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
                    RAISE EXCEPTION 'installation unavailable' USING ERRCODE='42501';
                  END IF;
                  SELECT installation_pk,etag_version INTO found_pk,found_etag
                    FROM public.bundle_installation
                   WHERE org_id=p_org AND project_id=p_project
                     AND installation_id=p_installation FOR UPDATE;
                  IF found_pk IS NULL OR found_etag IS DISTINCT FROM p_etag THEN
                    RAISE EXCEPTION 'installation unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN found_pk;
                END $$''').format(sql.Literal(issuer)))
            admin.execute('''REVOKE ALL ON FUNCTION public.aos_bi_plan_installation_lock_a0v_136(
                text,text,uuid,bigint) FROM PUBLIC''')
            admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                public.aos_bi_plan_installation_lock_a0v_136(text,text,uuid,bigint) TO {}''').format(
                    sql.Identifier(issuer)))
            admin.execute(sql.SQL('''CREATE FUNCTION public.aos_bi_plan_membership_lock_a0v_136(
                p_org text,p_project text,p_subject text) RETURNS TABLE(role text)
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user<>{} OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
                    RAISE EXCEPTION 'membership unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN QUERY SELECT m.role::text FROM public.meta_membership m
                    WHERE m.org_id=p_org AND m.project_id=p_project AND m.subject=p_subject
                    FOR SHARE OF m;
                END $$''').format(sql.Literal(issuer)))
            admin.execute('''REVOKE ALL ON FUNCTION public.aos_bi_plan_membership_lock_a0v_136(
                text,text,text) FROM PUBLIC''')
            admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                public.aos_bi_plan_membership_lock_a0v_136(text,text,text) TO {}''').format(
                    sql.Identifier(issuer)))
            admin.execute(sql.SQL('''CREATE FUNCTION public.aos_bi_plan_membership_read_a0v_138(
                p_org text,p_project text,p_subject text) RETURNS TABLE(role text)
                LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user<>{} OR p_org<>'org-org' OR p_project<>'dev-project'
                     OR p_subject<>'test-author'
                     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
                    RAISE EXCEPTION 'membership unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN QUERY SELECT m.role::text FROM public.meta_membership m
                    WHERE m.org_id=p_org AND m.project_id=p_project AND m.subject=p_subject;
                END $$''').format(sql.Literal(issuer)))
            admin.execute('''REVOKE ALL ON FUNCTION
                public.aos_bi_plan_membership_read_a0v_138(text,text,text) FROM PUBLIC''')
            admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                public.aos_bi_plan_membership_read_a0v_138(text,text,text) TO {}''').format(
                    sql.Identifier(issuer)))
            assert admin.execute('''SELECT p.prosecdef,p.proconfig,p.provolatile,
                EXISTS(SELECT 1 FROM aclexplode(p.proacl) acl
                       WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE')
                FROM pg_proc p WHERE p.oid=
                    'public.aos_bi_plan_membership_read_a0v_138(text,text,text)'::regprocedure'''
            ).fetchone() == (True, ['search_path=pg_catalog'], 's', False)
            admin.execute(sql.SQL('''CREATE FUNCTION public.aos_bi_plan_release_lock_a0v_139(
                p_org text,p_project text) RETURNS TABLE(version_pk uuid)
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user<>{} OR p_org<>'org-org' OR p_project<>'dev-project'
                     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
                    RAISE EXCEPTION 'release unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN QUERY SELECT v.version_pk FROM public.asset_bundle_version v
                    JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk
                    WHERE b.publisher='aos' AND b.bundle_id='solution.ecommerce.growth'
                      AND v.version IN ('1.12.0','1.13.0')
                    ORDER BY v.version_pk FOR SHARE OF v;
                END $$''').format(sql.Literal(issuer)))
            admin.execute('''REVOKE ALL ON FUNCTION
                public.aos_bi_plan_release_lock_a0v_139(text,text) FROM PUBLIC''')
            admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                public.aos_bi_plan_release_lock_a0v_139(text,text) TO {}''').format(
                    sql.Identifier(issuer)))
            assert admin.execute('''SELECT p.prosecdef,p.proconfig,p.provolatile,
                EXISTS(SELECT 1 FROM aclexplode(p.proacl) acl
                       WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE')
                FROM pg_proc p WHERE p.oid=
                    'public.aos_bi_plan_release_lock_a0v_139(text,text)'::regprocedure'''
            ).fetchone() == (True, ['search_path=pg_catalog'], 'v', False)
            assert admin.execute('''SELECT has_function_privilege(
                'aos_runtime','public.aos_bi_plan_release_lock_a0v_139(text,text)',
                'EXECUTE')''').fetchone()[0] is False
            admin.execute(sql.SQL('''CREATE FUNCTION public.aos_bi_plan_marking_lock_a0v_136(
                p_org text,p_project text,p_user_key text,p_object_key text)
                RETURNS TABLE(object_key text)
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user<>{} OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
                    RAISE EXCEPTION 'marking unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN QUERY SELECT t.object_key::text FROM public.authz_tuple t
                    WHERE t.org_id=p_org AND t.project_id=p_project
                      AND t.user_key=p_user_key AND t.relation='bearer'
                      AND t.object_key=p_object_key FOR SHARE OF t;
                END $$''').format(sql.Literal(issuer)))
            admin.execute('''REVOKE ALL ON FUNCTION public.aos_bi_plan_marking_lock_a0v_136(
                text,text,text,text) FROM PUBLIC''')
            admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                public.aos_bi_plan_marking_lock_a0v_136(text,text,text,text) TO {}''').format(
                    sql.Identifier(issuer)))
            admin.execute(sql.SQL('''CREATE FUNCTION public.aos_bi_plan_agents_lock_a0v_136(
                p_org text,p_project text,p_ids text[])
                RETURNS TABLE(instance_id text,version bigint)
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user<>{} OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
                     OR cardinality(p_ids)<>6
                     OR (SELECT count(DISTINCT id) FROM unnest(p_ids) AS id)<>6
                     OR (SELECT array_agg(id ORDER BY id) FROM unnest(p_ids) AS id)
                        IS DISTINCT FROM {} THEN
                    RAISE EXCEPTION 'agents unavailable' USING ERRCODE='42501';
                  END IF;
                  RETURN QUERY SELECT a.instance_id,a.version FROM public.aip_agent_instance a
                    WHERE a.org_id=p_org AND a.project_id=p_project AND a.status='active'
                      AND a.instance_id=ANY(p_ids)
                    ORDER BY a.instance_id FOR SHARE OF a;
                END $$''').format(
                    sql.Literal(issuer),
                    sql.SQL('ARRAY[{}]::text[]').format(sql.SQL(',').join(
                        sql.Literal(instance_id)
                        for instance_id in sorted(item[2] for item in BI_ROLE_BLUEPRINTS))),
                ))
            admin.execute('''REVOKE ALL ON FUNCTION public.aos_bi_plan_agents_lock_a0v_136(
                text,text,text[]) FROM PUBLIC''')
            admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                public.aos_bi_plan_agents_lock_a0v_136(text,text,text[]) TO {}''').format(
                    sql.Identifier(issuer)))
            admin.execute('''INSERT INTO authz_tuple(org_id,project_id,user_key,relation,object_key)
                VALUES(%s,%s,'user:test-author','bearer','marking:s3owq-test')
                ON CONFLICT DO NOTHING''', SCOPE.key)
            admin.execute('''INSERT INTO aip_agent_instance
                (org_id,project_id,instance_id,template_id,template_revision,
                 status,overlay,version,created_by)
                VALUES(%s,%s,'s3ows-unlisted-agent','test-bi-plan-active-handoff',1,
                       'active','{}',1,'test-author')''', SCOPE.key)
            # Test-only fixed Growth projection. Formal tenant/role mapping and
            # migration remain separate; never grant global Registry tables.
            with admin.transaction():
                admin.execute('''CREATE FUNCTION public.aos_bi_growth_registry_a0v_137(
                    p_org text,p_project text,p_kind text)
                    RETURNS TABLE(payload jsonb) LANGUAGE plpgsql STABLE SECURITY DEFINER
                    SET search_path=pg_catalog AS $$
                BEGIN
                  IF session_user <> 'aos_bi_plan_issuer'
                     OR p_org <> 'org-org' OR p_project <> 'dev-project'
                     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
                     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
                     OR p_kind IS NULL OR p_kind NOT IN ('approved','active','snapshot') THEN
                    RAISE EXCEPTION 'BI_GROWTH_SOURCE_DENIED' USING ERRCODE='42501';
                  END IF;
                  IF p_kind IN ('approved','active') THEN
                    RETURN QUERY SELECT jsonb_build_object(
                      'installation_id',i.installation_id::text,
                      'current_revision',i.current_revision,
                      'lock_payload',cl.lock_payload,
                      'publisher',b.publisher,'bundle_id',b.bundle_id,
                      'version',v.version,'bundle_content_hash',v.content_hash,
                      'artifact_ref',a.artifact_ref,'artifact_digest',a.digest)
                    FROM public.bundle_installation i
                    JOIN public.bundle_installation_revision r
                      ON r.org_id=i.org_id AND r.project_id=i.project_id
                     AND r.installation_pk=i.installation_pk
                     AND r.revision=i.current_revision
                    JOIN public.bundle_composition_lock cl
                      ON cl.org_id=r.org_id AND cl.project_id=r.project_id
                     AND cl.composition_pk=r.composition_pk AND cl.revision=r.lock_revision
                    JOIN public.asset_bundle_artifact a
                      ON a.relative_path='content/responsibility-templates/business-investigation.readonly.json'
                    JOIN public.asset_bundle_version v ON v.version_pk=a.version_pk
                    JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk
                    WHERE i.org_id=p_org AND i.project_id=p_project
                      AND b.publisher='aos' AND b.bundle_id='solution.ecommerce.growth'
                      AND v.version='1.13.0' AND v.status='published'
                      AND cl.lock_payload->'resolved' @> jsonb_build_array(
                        jsonb_build_object('publisher',b.publisher,'id',b.bundle_id,
                                           'version',v.version,'contentHash',v.content_hash))
                      AND ((p_kind='approved' AND i.active_revision IS NULL AND r.state='approved')
                        OR (p_kind='active' AND i.active_revision=i.current_revision
                            AND r.state='active'));
                  ELSE
                    RETURN QUERY SELECT jsonb_build_object(
                      'version_pk',v.version_pk,'publisher',b.publisher,
                      'bundle_id',b.bundle_id,'kind',b.kind,'version',v.version,
                      'manifest_json',v.manifest_json,'content_hash',v.content_hash,
                      'signature',v.signature,'status',v.status,
                      'artifacts',COALESCE((SELECT jsonb_agg(jsonb_build_object(
                        'relativePath',a.relative_path,'digest',a.digest,
                        'size',a.size,'mediaType',a.media_type) ORDER BY a.relative_path)
                        FROM public.asset_bundle_artifact a WHERE a.version_pk=v.version_pk),
                        '[]'::jsonb),
                      'evidence',COALESCE((SELECT jsonb_agg(jsonb_build_object(
                        'type',e.evidence_type,'artifactRef',e.artifact_ref,
                        'artifactHash',e.artifact_hash,'status',e.status,
                        'observedAt',e.observed_at,'expiresAt',e.expires_at,
                        'revokedAt',e.revoked_at,'metadata',e.metadata)
                        ORDER BY e.evidence_type,e.artifact_hash,e.observed_at,
                                 e.expires_at NULLS FIRST,e.artifact_ref)
                        FROM public.asset_bundle_evidence e WHERE e.version_pk=v.version_pk),
                        '[]'::jsonb))
                    FROM public.asset_bundle_version v
                    JOIN public.asset_bundle b ON b.bundle_pk=v.bundle_pk
                    WHERE b.publisher='aos' AND b.bundle_id='solution.ecommerce.growth'
                      AND v.version='1.13.0' AND v.status='published'
                      AND EXISTS (SELECT 1 FROM public.bundle_installation i
                        JOIN public.bundle_installation_revision r
                          ON r.org_id=i.org_id AND r.project_id=i.project_id
                         AND r.installation_pk=i.installation_pk
                         AND r.revision=i.current_revision
                        JOIN public.bundle_composition_lock cl
                          ON cl.org_id=r.org_id AND cl.project_id=r.project_id
                         AND cl.composition_pk=r.composition_pk
                         AND cl.revision=r.lock_revision
                        WHERE i.org_id=p_org AND i.project_id=p_project
                          AND cl.lock_payload->'resolved' @> jsonb_build_array(
                            jsonb_build_object('publisher',b.publisher,'id',b.bundle_id,
                                               'version',v.version,'contentHash',v.content_hash))
                          AND ((i.active_revision IS NULL AND r.state='approved')
                            OR (i.active_revision=i.current_revision AND r.state='active')));
                  END IF;
                END $$''')
                admin.execute('''REVOKE ALL ON FUNCTION
                    public.aos_bi_growth_registry_a0v_137(text,text,text) FROM PUBLIC''')
                admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                    public.aos_bi_growth_registry_a0v_137(text,text,text) TO {}''').format(
                        sql.Identifier(issuer)))
            function_guard = admin.execute('''SELECT p.prosecdef,p.proconfig,p.provolatile,
                EXISTS(SELECT 1 FROM aclexplode(p.proacl) acl
                       WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE')
                FROM pg_proc p WHERE p.oid=
                    'public.aos_bi_growth_registry_a0v_137(text,text,text)'::regprocedure''').fetchone()
            assert function_guard == (True, ['search_path=pg_catalog'], 's', False)
            parts = conninfo_to_dict(get_dsn())
            private_context = tempfile.TemporaryDirectory(prefix='aos-bi-issuer-')
            with nullcontext(private_context.name) as private_dir:
                private = Path(private_dir)
                private.chmod(0o700)
                passfile = private / 'issuer.pgpass'
                passfile.write_text(
                    f"{parts['host']}:{parts['port']}:{dbname}:{issuer}:{password}\n")
                passfile.chmod(0o600)
                issuer_config = BIIssuerDatabaseConfig(
                    parts['host'], int(parts['port']), dbname, passfile)
                with connect_bi_issuer_read_only(issuer_config, SCOPE) as guarded:
                    assert guarded.execute('''SELECT session_user,current_user,
                        current_setting('aos.org_id') AS org_id,
                        current_setting('aos.project_id') AS project_id,
                        current_setting('transaction_read_only') AS read_only''').fetchone() == {
                            'session_user': issuer, 'current_user': issuer,
                            'org_id': SCOPE.org_id, 'project_id': SCOPE.project_id,
                            'read_only': 'on'}
                    registry_reads = {
                        table: guarded.execute('SELECT has_table_privilege(current_user,%s,\'SELECT\') AS allowed',
                                               (table,)).fetchone()['allowed']
                        for table in ('asset_bundle', 'asset_bundle_version',
                                      'asset_bundle_artifact', 'asset_bundle_evidence')
                    }
                    assert registry_reads == {
                        'asset_bundle': False,
                        'asset_bundle_version': False,
                        'asset_bundle_artifact': False,
                        'asset_bundle_evidence': False,
                    }
                restricted_resolver = ApprovedBIPreparationResolver(
                    connect_factory=lambda scope: connect_bi_issuer_read_only(
                        issuer_config, scope),
                    registry_connect_factory=lambda: connect_bi_issuer_read_only(
                        issuer_config, SCOPE),
                    release_root=signed['signed_tree'], trust_roots=trust,
                    source_alias=signed['source_alias'],
                    registry_prepared_transaction=True,
                    restricted_bi_scope=SCOPE,
                )
                assert restricted_resolver.resolve(SCOPE, selected_template.template_ref) is True
                assert restricted_resolver.resolve(
                    SCOPE, selected_template.template_ref.model_copy(
                        update={'content_hash': '0' * 64})) is False
                assert restricted_resolver.resolve(
                    TenantScope('dev-org', 'dev-project'),
                    selected_template.template_ref) is False
                with connect_bi_issuer_read_only(issuer_config, SCOPE) as guarded:
                    rows = guarded.execute('''SELECT payload FROM
                        public.aos_bi_growth_registry_a0v_137(%s,%s,'snapshot')''',
                        SCOPE.key).fetchall()
                    assert [(row['payload']['bundle_id'], row['payload']['version'])
                            for row in rows] == [('solution.ecommerce.growth', '1.13.0')]
                    assert guarded.execute('''SELECT payload FROM
                        public.aos_bi_growth_registry_a0v_137(%s,%s,'active')''',
                        SCOPE.key).fetchall() == []
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connect_bi_issuer_read_only(issuer_config, SCOPE) as guarded:
                        guarded.execute('''SELECT payload FROM
                            public.aos_bi_growth_registry_a0v_137(
                                'dev-org','dev-project','snapshot')''').fetchall()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connect_bi_issuer_read_only(issuer_config, SCOPE) as guarded:
                        guarded.execute('''SELECT payload FROM
                            public.aos_bi_growth_registry_a0v_137(%s,%s,NULL)''',
                            SCOPE.key).fetchall()
                assert admin.execute('''SELECT has_function_privilege(
                    'aos_runtime','public.aos_bi_growth_registry_a0v_137(text,text,text)',
                    'EXECUTE') AS allowed''').fetchone()[0] is False
                admin.execute(sql.SQL('''REVOKE EXECUTE ON FUNCTION
                    public.aos_bi_growth_registry_a0v_137(text,text,text) FROM {}''').format(
                        sql.Identifier(issuer)))
                assert restricted_resolver.resolve(SCOPE, selected_template.template_ref) is False
                admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                    public.aos_bi_growth_registry_a0v_137(text,text,text) TO {}''').format(
                        sql.Identifier(issuer)))
                with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                    with connect_bi_issuer_read_only(issuer_config, SCOPE) as guarded:
                        guarded.execute('CREATE TEMP TABLE s3oww_read_only_denied (id int)')
                with connect_bi_issuer_write(issuer_config, SCOPE) as guarded:
                    guarded.rollback()
                    assert guarded.execute('''SELECT session_user,current_user,
                        current_setting('aos.org_id') AS org_id,
                        current_setting('aos.project_id') AS project_id''').fetchone() == {
                            'session_user': issuer, 'current_user': issuer,
                            'org_id': SCOPE.org_id, 'project_id': SCOPE.project_id}
            with psycopg.connect(host=parts['host'], port=parts['port'], dbname=dbname,
                                 user=issuer, password=password, row_factory=dict_row) as writer:
                writer.execute("SELECT set_config('aos.org_id',%s,false)", (SCOPE.org_id,))
                writer.execute("SELECT set_config('aos.project_id',%s,false)", (SCOPE.project_id,))
                writer.commit()
                assert writer.execute('SELECT session_user,current_user').fetchone() == {
                    'session_user': issuer, 'current_user': issuer}
                assert writer.execute(
                    "SELECT pg_has_role(current_user,'aos_runtime','member') AS member"
                ).fetchone()['member'] is False
                before_bi = writer.execute(
                    'SELECT count(*) AS n FROM aip_responsibility_plan_head').fetchone()['n']
                service = SignedBIPlanPreparationService(
                    connect_factory=lambda _: nullcontext(writer),
                    preparation_resolver=restricted_resolver,
                )
                prepare_args = dict(
                    installation_id=installed['installationId'],
                    expected_etag_version=installed['installationEtag'],
                    principal=Principal(subject='test-author', org_id=SCOPE.org_id,
                                        project_id=SCOPE.project_id, roles=['admin'],
                                        token_kind='oidc'),
                    idempotency_key='s3owj-restricted-bi-prepare',
                )
                prepared = service.prepare(SCOPE, **prepare_args)
                assert prepared.plan_id
                assert service.prepare(SCOPE, **prepare_args).plan_id == prepared.plan_id
                assert writer.execute(
                    'SELECT count(*) AS n FROM aip_responsibility_plan_head').fetchone()['n'] == before_bi + 1
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE operation='bi_responsibility_plan.prepare'
                      AND idempotency_key='s3owj-restricted-bi-prepare' ''').fetchone()['n'] == 1
                receipt_reader = SignedBIPlanReceiptReader(
                    connect_factory=lambda scope: connect_bi_issuer_read_only(
                        issuer_config, scope), restricted_bi_scope=SCOPE)
                readback = receipt_reader.read(
                    SCOPE, principal=prepare_args['principal'],
                    idempotency_key=prepare_args['idempotency_key'])
                assert readback.result_ref.resource_id == prepared.plan_id
                assert readback.installation_binding_verified is True
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    writer.execute(
                        """SELECT version.version_pk FROM asset_bundle_version AS version
                           JOIN asset_bundle AS bundle ON bundle.bundle_pk=version.bundle_pk
                           WHERE bundle.publisher='aos'
                             AND bundle.bundle_id='solution.ecommerce.growth'
                             AND version.version IN ('1.12.0','1.13.0')
                           ORDER BY version.version_pk FOR SHARE OF version"""
                    ).fetchall()
                writer.rollback()
                with writer.transaction():
                    release_rows = SignedBIPlanActiveRebindService._lock_growth_release(
                        writer, SCOPE)
                    assert release_rows
                    admin.execute("SET lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute('''UPDATE asset_bundle_version SET status=status
                            WHERE version_pk=%s''', (release_rows[0]['version_pk'],))
                    admin.execute('RESET lock_timeout')
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    writer.execute('''SELECT version_pk FROM
                        public.aos_bi_plan_release_lock_a0v_139(
                            'dev-org','dev-project')''').fetchall()
                writer.rollback()
                admin.execute(sql.SQL('''REVOKE EXECUTE ON FUNCTION
                    public.aos_bi_plan_release_lock_a0v_139(text,text) FROM {}''').format(
                        sql.Identifier(issuer)))
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    SignedBIPlanActiveRebindService._lock_growth_release(writer, SCOPE)
                writer.rollback()
                admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                    public.aos_bi_plan_release_lock_a0v_139(text,text) TO {}''').format(
                        sql.Identifier(issuer)))
                with pytest.raises(ProductionContractNotFound):
                    SignedBIPlanRebindReceiptReader(
                        connect_factory=lambda scope: connect_bi_issuer_read_only(
                            issuer_config, scope), restricted_bi_scope=SCOPE).read(
                                SCOPE, principal=prepare_args['principal'],
                                idempotency_key='s3owab-no-rebind')
                assert admin.execute('''SELECT has_table_privilege(
                    'aos_bi_plan_issuer','meta_membership','SELECT')''').fetchone()[0] is False
                with pytest.raises(PermissionError, match='tenant mismatch'):
                    receipt_reader.read(TenantScope('dev-org','dev-project'),
                        principal=Principal(subject='test-author', org_id='dev-org',
                                            project_id='dev-project', roles=['admin'],
                                            token_kind='oidc'),
                        idempotency_key=prepare_args['idempotency_key'])
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with connect_bi_issuer_read_only(issuer_config, SCOPE) as guarded:
                        guarded.execute('''SELECT role FROM
                            public.aos_bi_plan_membership_read_a0v_138(
                                %s,%s,'other-subject')''', SCOPE.key).fetchall()
                admin.execute(sql.SQL('''REVOKE EXECUTE ON FUNCTION
                    public.aos_bi_plan_membership_read_a0v_138(text,text,text)
                    FROM {}''').format(sql.Identifier(issuer)))
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    receipt_reader.read(SCOPE, principal=prepare_args['principal'],
                                        idempotency_key=prepare_args['idempotency_key'])
                admin.execute(sql.SQL('''GRANT EXECUTE ON FUNCTION
                    public.aos_bi_plan_membership_read_a0v_138(text,text,text)
                    TO {}''').format(sql.Identifier(issuer)))
                with writer.transaction():
                    assert writer.execute('''SELECT role FROM
                        public.aos_bi_plan_membership_lock_a0v_136(%s,%s,%s)''',
                        (*SCOPE.key, 'test-author')).fetchone()['role'] == 'admin'
                    assert writer.execute('''SELECT role FROM
                        public.aos_bi_plan_membership_lock_a0v_136(%s,%s,%s)''',
                        (*SCOPE.key, 'absent-author')).fetchall() == []
                    assert writer.execute('''SELECT object_key FROM
                        public.aos_bi_plan_marking_lock_a0v_136(%s,%s,%s,%s)''',
                        (*SCOPE.key, 'user:test-author', 'marking:s3owq-test')
                    ).fetchone()['object_key'] == 'marking:s3owq-test'
                    admin.execute("SET lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute('''UPDATE meta_membership SET role=role
                            WHERE org_id=%s AND project_id=%s AND subject=%s''',
                            (*SCOPE.key, 'test-author'))
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute('''DELETE FROM authz_tuple WHERE org_id=%s
                            AND project_id=%s AND user_key='user:test-author'
                            AND relation='bearer' AND object_key='marking:s3owq-test' ''',
                            SCOPE.key)
                    admin.execute('RESET lock_timeout')
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    writer.execute('''SELECT role FROM
                        public.aos_bi_plan_membership_lock_a0v_136(%s,%s,%s)''',
                        ('dev-org', SCOPE.project_id, 'test-author'))
                writer.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    writer.execute('''SELECT object_key FROM
                        public.aos_bi_plan_marking_lock_a0v_136(%s,%s,%s,%s)''',
                        ('dev-org', SCOPE.project_id, 'user:test-author', 'marking:public'))
                writer.rollback()
                agent_ids = [item[2] for item in BI_ROLE_BLUEPRINTS]
                with writer.transaction():
                    rows = writer.execute('''SELECT instance_id,version FROM
                        public.aos_bi_plan_agents_lock_a0v_136(%s,%s,%s)''',
                        (*SCOPE.key, agent_ids)).fetchall()
                    assert {row['instance_id'] for row in rows} == set(agent_ids)
                    assert {row['version'] for row in rows} == {1}
                    admin.execute("SET lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute('''UPDATE aip_agent_instance SET status='suspended'
                            WHERE org_id=%s AND project_id=%s AND instance_id=%s''',
                            (*SCOPE.key, agent_ids[0]))
                    admin.execute('RESET lock_timeout')
                for ids in (agent_ids[:5], [agent_ids[0]] * 6,
                            agent_ids[:5] + ['s3ows-unlisted-agent']):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        writer.execute('''SELECT instance_id FROM
                            public.aos_bi_plan_agents_lock_a0v_136(%s,%s,%s)''',
                            (*SCOPE.key, ids))
                    writer.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    writer.execute('''SELECT instance_id FROM
                        public.aos_bi_plan_agents_lock_a0v_136(%s,%s,%s)''',
                        ('dev-org', SCOPE.project_id, agent_ids))
                writer.rollback()
                admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(issuer)))
                try:
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        admin.execute('''SELECT instance_id FROM
                            public.aos_bi_plan_agents_lock_a0v_136(%s,%s,%s)''',
                            (*SCOPE.key, agent_ids))
                finally:
                    admin.execute('RESET ROLE')
                admin.execute('''UPDATE aip_agent_instance SET status='suspended'
                    WHERE org_id=%s AND project_id=%s AND instance_id=%s''',
                    (*SCOPE.key, agent_ids[0]))
                with pytest.raises(ValueError, match='six current digital coworker instances required'):
                    service.prepare(SCOPE, **{**prepare_args,
                        'idempotency_key': 's3owr-inactive-agent-rejected'})
                writer.rollback()
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE operation='bi_responsibility_plan.prepare'
                      AND idempotency_key='s3owr-inactive-agent-rejected' ''').fetchone()['n'] == 0
                writer.rollback()
                admin.execute('''UPDATE aip_agent_instance SET status='active'
                    WHERE org_id=%s AND project_id=%s AND instance_id=%s''',
                    (*SCOPE.key, agent_ids[0]))
                admin.execute('''UPDATE aip_agent_instance SET version=2
                    WHERE org_id=%s AND project_id=%s AND instance_id=%s''',
                    (*SCOPE.key, agent_ids[0]))
                with pytest.raises(ProductionContractIdempotencyConflict):
                    service.prepare(SCOPE, **prepare_args)
                writer.rollback()
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE operation='bi_responsibility_plan.prepare'
                      AND idempotency_key='s3owj-restricted-bi-prepare' ''').fetchone()['n'] == 1
                writer.rollback()
                admin.execute('''UPDATE aip_agent_instance SET version=1
                    WHERE org_id=%s AND project_id=%s AND instance_id=%s''',
                    (*SCOPE.key, agent_ids[0]))
                lock_args = (*SCOPE.key, installed['installationId'],
                             installed['installationEtag'])
                for args in (("dev-org", *lock_args[1:]),
                             (*lock_args[:3], lock_args[3] + 1)):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        writer.execute('''SELECT public.aos_bi_plan_installation_lock_a0v_136(
                            %s,%s,%s,%s)''', args)
                    writer.rollback()
                with writer.transaction():
                    row = writer.execute('''SELECT public.aos_bi_plan_installation_lock_a0v_136(
                        %s,%s,%s,%s) AS installation_pk''', lock_args).fetchone()
                    assert row['installation_pk'] is not None
                    admin.execute("SET lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute('''UPDATE bundle_installation
                            SET etag_version=etag_version+1
                            WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
                            lock_args[:3])
                    admin.execute('RESET lock_timeout')
                assert admin.execute('''SELECT etag_version FROM bundle_installation
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
                    lock_args[:3]).fetchone()[0] == installed['installationEtag']
                store = AipProductionContractStore(
                    connect_factory=lambda _: nullcontext(writer),
                    responsibility_template_resolver=resolver.resolve,
                )
                issued = store.create_responsibility_plan(
                    SCOPE, 'test-author', 's3owi-original-create', request)
                assert issued.readiness.value == 'blocked'
                assert store.create_responsibility_plan(
                    SCOPE, 'test-author', 's3owi-original-create', request).plan_id == issued.plan_id
                with pytest.raises(ProductionContractIdempotencyConflict):
                    store.create_responsibility_plan(
                        SCOPE, 'test-author', 's3owi-original-create',
                        request.model_copy(update={'profile': 'other-isolated-profile'}))
                row = writer.execute('''SELECT h.current_revision,r.content_hash,p.result_ref
                    FROM aip_responsibility_plan_head h
                    JOIN aip_responsibility_plan_revision r USING(org_id,project_id,plan_id)
                    JOIN aip_production_contract_receipt p
                      ON p.org_id=h.org_id AND p.project_id=h.project_id
                     AND p.operation='responsibility_plan.create'
                     AND p.idempotency_key='s3owi-original-create'
                    WHERE h.org_id=%s AND h.project_id=%s AND h.plan_id=%s''',
                    (*SCOPE.key, issued.plan_id)).fetchone()
                assert row['current_revision'] == 1
                assert row['result_ref']['resourceId'] == issued.plan_id
                assert row['result_ref']['contentHash'] == row['content_hash']
                revised_request = ReviseResponsibilityPlanRequest(
                    **request.model_dump(mode='json', by_alias=True),
                    expectedVersion=issued.version,
                )
                revised = store.revise_responsibility_plan(
                    SCOPE, 'test-author', issued.plan_id, 's3owi-original-revise',
                    revised_request)
                assert revised.revision == 2 and revised.version == 2
                with pytest.raises(ResponsibilityAssignmentBlocked,
                                   match='SOURCE_PLAN_NOT_EXACT_FROZEN'):
                    AipResponsibilityAssignmentStore(
                        connect_factory=lambda _: nullcontext(writer),
                    ).create_successor(
                        SCOPE,
                        CreateResponsibilitySuccessorRequest(
                            task_id='s3owk-isolated-task',
                            source_plan_ref=ExactRevisionRef(
                                resource_type='ResponsibilityPlanRevision',
                                resource_id=issued.plan_id, revision=revised.revision,
                                content_hash=revised.content_hash,
                            ),
                            expected_source_version=revised.version,
                            slot_id=request.slots[0].slot_id,
                            target_assignee=request.slots[0].assignee,
                            resolution_receipt_id='s3owk-unissued-resolution',
                            reason_code='OPERATOR_REASSIGNED',
                        ),
                        actor='test-author', idempotency_key='s3owk-successor',
                    )
                assert writer.execute('''SELECT count(*) AS n FROM aip_responsibility_successor
                    WHERE idempotency_key='s3owk-successor' ''').fetchone()['n'] == 0
                assert store.revise_responsibility_plan(
                    SCOPE, 'test-author', issued.plan_id, 's3owi-original-revise',
                    revised_request).revision == 2
                with pytest.raises(ProductionContractConflict,
                                   match='stale responsibility plan version'):
                    store.revise_responsibility_plan(
                        SCOPE, 'test-author', issued.plan_id, 's3owi-stale-revise',
                        revised_request)
                with pytest.raises(ProductionContractDependencyBlocked,
                                   match='RESPONSIBILITY_PLAN_NOT_READY'):
                    store.freeze_responsibility_plan(
                        SCOPE, 'test-author', issued.plan_id, revised.version,
                        's3owi-closed-freeze')
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE operation='responsibility_plan.freeze'
                      AND idempotency_key='s3owi-closed-freeze' ''').fetchone()['n'] == 0
                before = writer.execute('SELECT count(*) AS n FROM aip_responsibility_plan_head').fetchone()['n']
                revisions_before = writer.execute(
                    'SELECT count(*) AS n FROM aip_responsibility_plan_revision').fetchone()['n']
                with pytest.raises(psycopg.Error, match='PLAN_FORCED_ROLLBACK'):
                    store.create_responsibility_plan(
                        SCOPE, 'test-author', 's3owi-forced-rollback', request)
                writer.rollback()
                assert writer.execute('SELECT count(*) AS n FROM aip_responsibility_plan_head').fetchone()['n'] == before
                assert writer.execute(
                    'SELECT count(*) AS n FROM aip_responsibility_plan_revision').fetchone()['n'] == revisions_before
                assert writer.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                    WHERE idempotency_key='s3owi-forced-rollback' ''').fetchone()['n'] == 0
                with pytest.raises(psycopg.errors.InsufficientPrivilege), writer.transaction():
                    writer.execute('''INSERT INTO aip_responsibility_plan_head
                        (org_id,project_id,plan_id,current_revision,version)
                        VALUES('dev-org','dev-project','s3owi-cross-tenant',1,1)''')
                with pytest.raises(psycopg.errors.InsufficientPrivilege,
                                   match='PLAN_RECEIPT_UNPAIRED'), writer.transaction():
                    writer.execute('''INSERT INTO aip_production_contract_receipt
                        (org_id,project_id,receipt_id,operation,idempotency_key,
                         request_hash,result_ref,created_by)
                        VALUES(%s,%s,'s3owi-unpaired','responsibility_plan.create',
                          's3owi-unpaired',%s,%s::jsonb,'test-author')''',
                        (*SCOPE.key, 'a' * 64,
                         '{"resourceType":"ResponsibilityPlanRevision",'
                         '"resourceId":"missing","revision":1,"contentHash":"' + 'b' * 64 + '"}'))
        finally:
            if private_context is not None:
                private_context.cleanup()
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_plan_release_lock_a0v_139(text,text)''')
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_plan_membership_read_a0v_138(text,text,text)''')
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_growth_registry_a0v_137(text,text,text)''')
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_plan_agents_lock_a0v_136(text,text,text[])''')
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_plan_marking_lock_a0v_136(text,text,text,text)''')
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_plan_membership_lock_a0v_136(text,text,text)''')
            admin.execute('''DROP FUNCTION IF EXISTS
                public.aos_bi_plan_installation_lock_a0v_136(text,text,uuid,bigint)''')
            admin.execute('''DROP TRIGGER IF EXISTS s3owi_plan_receipt_guard
                ON aip_production_contract_receipt''')
            admin.execute('DROP FUNCTION IF EXISTS s3owi_plan_receipt_guard()')
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(issuer)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(issuer)))
