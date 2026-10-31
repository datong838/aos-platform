"""Keep configuration refresh revision chains within their actual activation.

Candidate forward migration. Offline tests do not qualify native deployment.
The original immutable receipts, wire bodies and global idempotency key remain.
"""
from hashlib import sha256

from alembic import op

revision = "a0v_166"
down_revision = "a0v_165"
branch_labels = depends_on = None

OLD_KEY = ["org_id", "project_id", "cutover_group_id", "revision"]
NEW_KEY = ["org_id", "project_id", "cutover_group_id", "activation_operation_id", "revision"]

# Exact a0v069 function, excluding its separate ACL statements.
ORIGINAL_REFRESH_SQL = r'''CREATE OR REPLACE FUNCTION public.extension_dispatch_configuration_refresh_a0v_068(
      p_request jsonb,p_actor text) RETURNS uuid
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_now timestamptz:=clock_timestamp(); v_hash text; v_existing record;
      v_root record; v_parent record; v_binding record; v_installation record;
      v_configure record; v_enable record; v_configure_target jsonb; v_enable_target jsonb;
      v_group uuid; v_installation_id uuid; v_generation uuid; v_receipt uuid:=gen_random_uuid();
      v_revision bigint; v_expected_group bigint; v_operations text[]; v_rows bigint;
      v_body jsonb; v_content_hash text; v_previous_id uuid; v_previous_hash text;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR p_actor IS NULL OR p_actor<>btrim(p_actor)
        OR length(p_actor) NOT BETWEEN 1 AND 240
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'dedicated non-privileged configuration maintainer is required'
        USING ERRCODE='42501'; END IF;
      IF p_request->>'schemaVersion'<>'aos.ecommerce.dispatch-configuration-refresh/v1'
        OR p_request->>'orgId' IS DISTINCT FROM v_org OR p_request->>'projectId' IS DISTINCT FROM v_project
        OR p_request->'externalEffectsAllowed'<>'false'::jsonb OR p_request->'resumeBusinessRuns'<>'false'::jsonb
      THEN RAISE EXCEPTION 'exact tenant-scoped configuration refresh request required'
        USING ERRCODE='23514'; END IF;
      v_hash:=public.canonical_bundle_control_sha256(p_request);
      SELECT * INTO v_existing FROM public.extension_dispatch_configuration_refresh_receipt
        WHERE org_id=v_org AND project_id=v_project
          AND cutover_group_id=(p_request->>'cutoverGroupId')::uuid
          AND idempotency_key=p_request->>'idempotencyKey';
      IF FOUND THEN
        IF v_existing.request_hash<>v_hash OR v_existing.actor<>p_actor OR v_existing.request<>p_request
          OR EXISTS(SELECT 1 FROM public.extension_dispatch_configuration_refresh_receipt newer
            WHERE newer.org_id=v_org AND newer.project_id=v_project
              AND newer.cutover_group_id=v_existing.cutover_group_id
              AND newer.revision>v_existing.revision)
        THEN RAISE EXCEPTION 'configuration refresh idempotency conflict' USING ERRCODE='23505'; END IF;
        RETURN v_existing.receipt_id;
      END IF;

      v_group:=(p_request->>'cutoverGroupId')::uuid;
      v_installation_id:=(p_request->'installationRef'->>'installationId')::uuid;
      v_generation:=(p_request->>'generation')::uuid;
      v_expected_group:=(p_request->>'expectedGroupRevision')::bigint;
      SELECT i.*,r.lock_hash,r.overlay_revision INTO v_installation
        FROM public.bundle_installation i JOIN public.bundle_installation_revision r
          ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk
         AND r.revision=i.active_revision
        WHERE i.org_id=v_org AND i.project_id=v_project AND i.installation_id=v_installation_id FOR UPDATE OF i;
      IF NOT FOUND OR v_installation.active_revision<>(p_request->'installationRef'->>'revision')::bigint
        OR v_installation.lock_hash<>p_request->'installationRef'->>'lockHash'
        OR v_installation.overlay_revision<>p_request->'installationRef'->>'overlayRevision'
      THEN RAISE EXCEPTION 'current installation authority drifted' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_root FROM public.extension_dispatch_cutover_operation
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
          AND kind='activate' AND status='resumed' AND target_installation_id=v_installation_id
          AND target_generation=v_generation FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'resumed activation root unavailable' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_parent FROM public.extension_dispatch_configuration_refresh_receipt
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
        ORDER BY revision DESC LIMIT 1 FOR UPDATE;
      IF FOUND THEN
        v_revision:=v_parent.revision+1;v_previous_id:=v_parent.receipt_id;v_previous_hash:=v_parent.content_hash;
        IF p_request->'sourceAuthorityRef' IS DISTINCT FROM jsonb_build_object(
          'resourceType','DispatchConfigurationRefreshReceipt','resourceId',v_parent.receipt_id::text,
          'revision',v_parent.revision,'contentHash',v_parent.content_hash)
        THEN RAISE EXCEPTION 'latest configuration refresh authority required' USING ERRCODE='40001'; END IF;
      ELSE
        v_revision:=1;
        PERFORM 1 FROM public.extension_dispatch_cutover_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.cutover_operation_id=v_root.cutover_operation_id
            AND r.phase='resume' AND p_request->'sourceAuthorityRef'=jsonb_build_object(
              'resourceType','CutoverResumeReceipt','resourceId',r.receipt_id::text,
              'revision',1,'contentHash',r.content_hash);
        IF NOT FOUND THEN RAISE EXCEPTION 'original resume authority required' USING ERRCODE='40001'; END IF;
      END IF;

      SELECT * INTO v_binding FROM public.extension_runtime_binding
        WHERE org_id=v_org AND project_id=v_project AND installation_id=v_installation_id
          AND generation=v_generation FOR UPDATE;
      IF NOT FOUND OR v_binding.revision<>(p_request->>'targetRuntimeRevision')::bigint
        OR v_binding.execution_epoch<>(p_request->>'targetExecutionEpoch')::bigint
        OR v_binding.config_ref IS DISTINCT FROM p_request->'targetConfigurationRef'
        OR NOT v_binding.enabled OR v_binding.operation_fence
        OR v_binding.desired_state<>'enabled' OR v_binding.observed_state<>'ready'
      THEN RAISE EXCEPTION 'target runtime binding is not exact and ready' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_configure FROM public.extension_runtime_operation
        WHERE org_id=v_org AND project_id=v_project
          AND operation_id=(p_request->>'configureOperationId')::uuid FOR UPDATE;
      SELECT payload->'configurationTarget' INTO v_configure_target FROM public.extension_runtime_event
        WHERE org_id=v_org AND project_id=v_project AND operation_id=v_configure.operation_id
          AND sequence=1 AND type='accepted';
      IF NOT FOUND OR v_configure.kind<>'configure' OR v_configure.status<>'succeeded' OR v_configure.phase<>'succeeded'
        OR v_configure.installation_id<>v_installation_id OR v_configure.requested_by<>p_actor
        OR v_configure.revision<>(p_request->>'configureOperationRevision')::bigint
        OR v_configure_target IS DISTINCT FROM jsonb_build_object('generation',v_generation::text,
          'bindingRevision',(p_request->>'sourceRuntimeRevision')::bigint,
          'configRef',p_request->'targetConfigurationRef')
      THEN RAISE EXCEPTION 'completed exact configure operation required' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_enable FROM public.extension_runtime_operation
        WHERE org_id=v_org AND project_id=v_project
          AND operation_id=(p_request->>'enableOperationId')::uuid FOR UPDATE;
      SELECT payload->'configurationTarget' INTO v_enable_target FROM public.extension_runtime_event
        WHERE org_id=v_org AND project_id=v_project AND operation_id=v_enable.operation_id
          AND sequence=1 AND type='accepted';
      IF NOT FOUND OR v_enable.kind<>'enable' OR v_enable.status<>'succeeded' OR v_enable.phase<>'succeeded'
        OR v_enable.installation_id<>v_installation_id OR v_enable.requested_by<>p_actor
        OR v_enable.revision<>(p_request->>'enableOperationRevision')::bigint
        OR v_enable_target IS DISTINCT FROM jsonb_build_object('generation',v_generation::text,
          'bindingRevision',(p_request->>'targetRuntimeRevision')::bigint-1,
          'configRef',p_request->'targetConfigurationRef')
      THEN RAISE EXCEPTION 'completed exact enable operation required' USING ERRCODE='40001'; END IF;

      SELECT array_agg(value ORDER BY value) INTO v_operations
        FROM jsonb_array_elements_text(p_request->'operationIds');
      PERFORM 1 FROM public.extension_operation_dispatch_binding d
        WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
          AND d.operation_id=ANY(v_operations) ORDER BY d.operation_id FOR UPDATE;
      IF v_operations IS DISTINCT FROM ARRAY(SELECT d.operation_id FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND d.operation_id=ANY(v_operations) ORDER BY d.operation_id)
        OR EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND d.operation_id=ANY(v_operations) AND (d.handler_kind<>'extension' OR d.installation_id<>v_installation_id OR d.generation<>v_generation
              OR d.execution_epoch<>(p_request->>'sourceExecutionEpoch')::bigint OR d.operation_fence
              OR d.cutover_group_revision<>v_expected_group))
      THEN RAISE EXCEPTION 'source dispatch group authority drifted' USING ERRCODE='40001'; END IF;
      UPDATE public.extension_operation_dispatch_binding SET
        execution_epoch=(p_request->>'targetExecutionEpoch')::bigint,revision=revision+1,
        cutover_group_revision=v_expected_group+1,updated_by=p_actor,updated_at=v_now
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
          AND operation_id=ANY(v_operations);
      GET DIAGNOSTICS v_rows=ROW_COUNT;
      IF v_rows<>cardinality(v_operations) THEN RAISE EXCEPTION 'dispatch refresh group update was not exact'
        USING ERRCODE='40001'; END IF;
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.dispatch-configuration-refresh-receipt/v1',
        'receiptId',v_receipt::text,'revision',v_revision,'activationOperationId',v_root.cutover_operation_id::text,
        'activationResumeReceiptId',CASE WHEN v_revision=1 THEN p_request->'sourceAuthorityRef'->>'resourceId'
          ELSE v_parent.activation_resume_receipt_id::text END,'actor',p_actor,'request',p_request,
        'requestHash',v_hash,'createdAt',to_char(v_now AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US+00:00'));
      v_content_hash:=public.canonical_bundle_control_sha256(v_body);
      INSERT INTO public.extension_dispatch_configuration_refresh_receipt(
        org_id,project_id,cutover_group_id,receipt_id,revision,activation_operation_id,
        activation_resume_receipt_id,installation_id,generation,previous_receipt_id,previous_hash,
        actor,idempotency_key,request,request_hash,body,content_hash,created_at)
      VALUES(v_org,v_project,v_group,v_receipt,v_revision,v_root.cutover_operation_id,
        CASE WHEN v_revision=1 THEN (p_request->'sourceAuthorityRef'->>'resourceId')::uuid
          ELSE v_parent.activation_resume_receipt_id END,v_installation_id,v_generation,
        v_previous_id,v_previous_hash,p_actor,p_request->>'idempotencyKey',p_request,v_hash,
        v_body,v_content_hash,v_now);
      RETURN v_receipt;
    END $$;'''
ORIGINAL_GUARD_SHA256 = 'cb4640dca92c23abec4ded64fb1fc9a3b82124134186701f718645fad865d968'



def _replace_once(value, old, new):
    if value.count(old) != 1:
        raise RuntimeError("REFRESH_ORIGINAL_SOURCE_ANCHOR_DRIFT")
    return value.replace(old, new, 1)


REFRESH_SQL = _replace_once(
    ORIGINAL_REFRESH_SQL,
    "AND newer.revision>v_existing.revision",
    "AND newer.activation_operation_id=v_existing.activation_operation_id\n"
    "              AND newer.revision>v_existing.revision",
)
REFRESH_SQL = _replace_once(
    REFRESH_SQL,
    "WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group\n"
    "        ORDER BY revision DESC LIMIT 1 FOR UPDATE;",
    "WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group\n"
    "          AND activation_operation_id=v_root.cutover_operation_id\n"
    "          AND installation_id=v_installation_id AND generation=v_generation\n"
    "        ORDER BY revision DESC LIMIT 1 FOR UPDATE;",
)

KEY_SQL = """
SELECT k.conname AS pk_name,
       ARRAY(SELECT a.attname::text FROM unnest(k.conkey) WITH ORDINALITY AS x(attnum,n)
             JOIN pg_catalog.pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=x.attnum
             ORDER BY x.n) AS pk_columns,
       EXISTS(SELECT 1 FROM pg_catalog.pg_constraint f
              WHERE f.contype='f' AND f.confrelid=k.conrelid AND f.conindid=k.conindid) AS incoming_pk_fks
FROM pg_catalog.pg_constraint k
WHERE k.conrelid='public.extension_dispatch_configuration_refresh_receipt'::regclass
  AND k.contype='p'
"""

# Exclude only the deliberately replaced primary key. All other authority is
# compared before/after, including the original immutable insertion guard.
SEAL_SQL = """
SELECT jsonb_build_object(
  'rls',c.relrowsecurity,'force_rls',c.relforcerowsecurity,
  'owner',c.relowner,'acl',c.relacl::text,
  'constraints',(SELECT jsonb_agg(jsonb_build_array(k.conname,pg_catalog.pg_get_constraintdef(k.oid,true))
                               ORDER BY k.conname)
                 FROM pg_catalog.pg_constraint k WHERE k.conrelid=c.oid AND k.contype<>'p'),
  'policies',(SELECT jsonb_agg(jsonb_build_array(p.polname,pg_catalog.pg_get_expr(p.polqual,p.polrelid),
                              pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid),p.polcmd,
                              p.polpermissive,p.polroles) ORDER BY p.polname)
              FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid),
  'triggers',(SELECT jsonb_agg(jsonb_build_array(t.tgname,t.tgenabled,
                               pg_catalog.pg_get_triggerdef(t.oid,true)) ORDER BY t.tgname)
              FROM pg_catalog.pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal),
  'guard_definition',pg_catalog.pg_get_functiondef(
                     'public.validate_dispatch_configuration_refresh_a0v_067()'::regprocedure)
 ) AS value,
 (SELECT prosrc FROM pg_catalog.pg_proc
   WHERE oid='public.validate_dispatch_configuration_refresh_a0v_067()'::regprocedure) AS guard_body
FROM pg_catalog.pg_class c
WHERE c.oid='public.extension_dispatch_configuration_refresh_receipt'::regclass AND c.relkind='r'
"""

WRITER_SQL = """
SELECT p.prosrc AS body,
       jsonb_build_object('owner',p.proowner,'acl',p.proacl::text,
         'security_definer',p.prosecdef,'config',p.proconfig,
         'language',p.prolang,'returns',p.prorettype,'arguments',p.proargtypes::text,
         'volatility',p.provolatile,'parallel',p.proparallel,'strict',p.proisstrict,
         'leakproof',p.proleakproof) AS shape,
       (NOT EXISTS(SELECT 1 FROM pg_catalog.aclexplode(
                       COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          WHERE a.privilege_type<>'EXECUTE'
             OR a.grantee NOT IN (p.proowner,'aos_extension_maintainer'::regrole::oid)
             OR (a.grantee<>p.proowner AND a.is_grantable))
        AND EXISTS(SELECT 1 FROM pg_catalog.aclexplode(
                        COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          WHERE a.grantee='aos_extension_maintainer'::regrole::oid
            AND a.privilege_type='EXECUTE' AND NOT a.is_grantable)) AS acl_valid
FROM pg_catalog.pg_proc p
WHERE p.oid='public.extension_dispatch_configuration_refresh_a0v_068(jsonb,text)'::regprocedure
"""


def _row(conn, query):
    return dict(conn.exec_driver_sql(query).mappings().one())


def _body(sql):
    return sql.split("AS $$", 1)[1].split("$$", 1)[0]


def upgrade():
    conn = op.get_bind()
    if (conn.dialect.name != "postgresql" or not conn.in_transaction()
            or conn.get_execution_options().get("isolation_level") == "AUTOCOMMIT"
            or conn.connection.driver_connection.autocommit is not False):
        raise RuntimeError("REFRESH_TRANSACTIONAL_POSTGRESQL_REQUIRED")
    conn.exec_driver_sql("LOCK TABLE public.extension_dispatch_configuration_refresh_receipt IN ACCESS EXCLUSIVE MODE")
    key = _row(conn, KEY_SQL)
    seal = _row(conn, SEAL_SQL)
    writer = _row(conn, WRITER_SQL)
    if (key["pk_columns"] != OLD_KEY or key["incoming_pk_fks"]
            or not seal["value"]["rls"] or not seal["value"]["force_rls"]
            or sha256(seal["guard_body"].encode("utf-8")).hexdigest() != ORIGINAL_GUARD_SHA256
            or writer["body"] != _body(ORIGINAL_REFRESH_SQL) or not writer["acl_valid"]
            or not writer["shape"]["security_definer"]
            or writer["shape"]["config"] != ["search_path=pg_catalog, public, pg_temp"]):
        raise RuntimeError("REFRESH_ACTIVATION_CHAIN_BASELINE_DRIFT")
    # No CASCADE: an unrecognised dependency also fails the containing migration
    # transaction instead of deleting another authority object.
    quoted_name = '"' + key["pk_name"].replace('"', '""') + '"'
    conn.exec_driver_sql("ALTER TABLE public.extension_dispatch_configuration_refresh_receipt DROP CONSTRAINT " + quoted_name)
    conn.exec_driver_sql("ALTER TABLE public.extension_dispatch_configuration_refresh_receipt "
                         "ADD PRIMARY KEY (org_id,project_id,cutover_group_id,activation_operation_id,revision)")
    conn.exec_driver_sql(REFRESH_SQL)
    after_key = _row(conn, KEY_SQL)
    after_seal = _row(conn, SEAL_SQL)
    after_writer = _row(conn, WRITER_SQL)
    if (after_key["pk_columns"] != NEW_KEY or after_key["incoming_pk_fks"]
            or after_seal != seal or after_writer["shape"] != writer["shape"]
            or not after_writer["acl_valid"] or after_writer["body"] != _body(REFRESH_SQL)):
        raise RuntimeError("REFRESH_ACTIVATION_CHAIN_POSTCONDITION_DRIFT")


def downgrade():
    raise RuntimeError("REFRESH_ACTIVATION_HISTORY_REQUIRES_FORWARD_RECOVERY")
