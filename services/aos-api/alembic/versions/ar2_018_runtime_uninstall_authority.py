"""Bind runtime uninstall terminal state to exact released authority."""

from alembic import op


revision = "ar2_018"
down_revision = "ar2_017"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE extension_runtime_uninstall_receipt(
      org_id text NOT NULL,project_id text NOT NULL,receipt_id uuid NOT NULL,
      installation_id uuid NOT NULL,generation uuid NOT NULL,
      disable_operation_id uuid NOT NULL,activation_operation_id uuid NOT NULL,
      installation_revision bigint NOT NULL CHECK(installation_revision>0),
      binding_revision bigint NOT NULL CHECK(binding_revision>1),
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      authority_data jsonb NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,installation_id,generation),
      FOREIGN KEY(org_id,project_id,installation_id,generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
      FOREIGN KEY(org_id,project_id,disable_operation_id)
        REFERENCES extension_runtime_operation(org_id,project_id,operation_id),
      FOREIGN KEY(org_id,project_id,disable_operation_id)
        REFERENCES extension_dispatch_lifecycle_operation(org_id,project_id,runtime_operation_id),
      FOREIGN KEY(org_id,project_id,activation_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id)
    );
    ALTER TABLE extension_runtime_uninstall_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_uninstall_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_runtime_uninstall_receipt
      USING(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON extension_runtime_uninstall_receipt FROM PUBLIC,aos_app,aos_runtime,
      aos_extension_maintainer;
    GRANT SELECT ON extension_runtime_uninstall_receipt TO aos_app,aos_runtime,
      aos_extension_maintainer;

    CREATE FUNCTION extension_runtime_uninstall_receipt_hash_ar2_018() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
      BEGIN
        IF NEW.content_hash IS DISTINCT FROM
          'sha256:'||encode(sha256(convert_to(NEW.authority_data::text,'UTF8')),'hex')
        THEN RAISE EXCEPTION 'runtime uninstall Receipt hash differs'
          USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$;
    CREATE TRIGGER uninstall_receipt_hash BEFORE INSERT
      ON extension_runtime_uninstall_receipt FOR EACH ROW
      EXECUTE FUNCTION extension_runtime_uninstall_receipt_hash_ar2_018();
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE
      ON extension_runtime_uninstall_receipt FOR EACH ROW
      EXECUTE FUNCTION extension_reject_history_mutation();

    CREATE FUNCTION extension_runtime_uninstall_consistency_ar2_018() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_installation uuid;v_generation uuid;v_binding_revision bigint;
        v_binding record;v_receipt record;v_head record;
      BEGIN
        IF TG_TABLE_NAME='extension_runtime_binding' THEN
          IF NEW.desired_state<>'uninstalled' THEN RETURN NEW; END IF;
          v_installation:=NEW.installation_id;v_generation:=NEW.generation;
          v_binding_revision:=NEW.revision;
          IF OLD.desired_state='uninstalled'
            OR NEW.observed_state<>'stopped' OR NEW.enabled OR NOT NEW.operation_fence
            OR NEW.revision<>OLD.revision+1
            OR ROW(NEW.installation_revision,NEW.package_lock_ref,NEW.profile_ref,
                   NEW.config_ref,NEW.execution_epoch,NEW.resource_handle_ref)
               IS DISTINCT FROM
               ROW(OLD.installation_revision,OLD.package_lock_ref,OLD.profile_ref,
                   OLD.config_ref,OLD.execution_epoch,OLD.resource_handle_ref)
          THEN RAISE EXCEPTION 'invalid runtime uninstall binding transition'
            USING ERRCODE='23514'; END IF;
        ELSE
          v_installation:=NEW.installation_id;v_generation:=NEW.generation;
          v_binding_revision:=NEW.binding_revision;
        END IF;
        SELECT * INTO v_binding FROM public.extension_runtime_binding
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id
            AND installation_id=v_installation AND generation=v_generation;
        SELECT * INTO v_receipt FROM public.extension_runtime_uninstall_receipt
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id
            AND installation_id=v_installation AND generation=v_generation;
        SELECT i.current_revision,i.etag_version,r.state INTO v_head
          FROM public.bundle_installation i
          JOIN public.bundle_installation_revision r
            ON r.org_id=i.org_id AND r.project_id=i.project_id
           AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
          WHERE i.org_id=NEW.org_id AND i.project_id=NEW.project_id
            AND i.installation_id=v_installation;
        IF v_binding.desired_state<>'uninstalled' OR v_binding.observed_state<>'stopped'
          OR v_binding.enabled OR NOT v_binding.operation_fence
          OR v_binding.revision<>v_binding_revision
          OR v_receipt.binding_revision<>v_binding_revision
          OR v_receipt.installation_revision+1<>v_head.current_revision
          OR v_head.current_revision<>v_head.etag_version OR v_head.state<>'uninstalled'
        THEN RAISE EXCEPTION 'runtime uninstall requires matching terminal installation Receipt'
          USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$;
    CREATE CONSTRAINT TRIGGER runtime_uninstall_binding_guard
      AFTER UPDATE OF desired_state ON extension_runtime_binding
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
      EXECUTE FUNCTION extension_runtime_uninstall_consistency_ar2_018();
    CREATE CONSTRAINT TRIGGER runtime_uninstall_receipt_guard
      AFTER INSERT ON extension_runtime_uninstall_receipt
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
      EXECUTE FUNCTION extension_runtime_uninstall_consistency_ar2_018();

    CREATE FUNCTION extension_runtime_uninstall_commit_ar2_018(
      p_installation_id uuid,p_expected_installation_revision bigint,p_actor text)
      RETURNS TABLE(applied boolean,receipt_data jsonb,content_hash text)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_installation record;v_binding record;v_lifecycle record;
        v_binding_count bigint;v_lifecycle_count bigint;v_receipt_count bigint;
        v_resource_count bigint;v_unreleased_count bigint;v_dispatch_count bigint;
        v_claimed_occurrences bigint;v_open_dispatch_attempts bigint;v_running_attempts bigint;
        v_receipt_id uuid:=gen_random_uuid();v_authority jsonb;v_hash text;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR p_expected_installation_revision<1
          OR length(BTRIM(p_actor)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_app','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged application role is required'
          USING ERRCODE='42501'; END IF;
        SELECT i.installation_pk,i.current_revision,i.etag_version,r.state INTO v_installation
          FROM public.bundle_installation i
          JOIN public.bundle_installation_revision r
            ON r.org_id=i.org_id AND r.project_id=i.project_id
           AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
          WHERE i.org_id=v_org AND i.project_id=v_project
            AND i.installation_id=p_installation_id FOR UPDATE OF i,r;
        IF NOT FOUND OR v_installation.current_revision<>p_expected_installation_revision
          OR v_installation.etag_version<>p_expected_installation_revision
          OR v_installation.state<>'active'
        THEN RAISE EXCEPTION 'current active installation authority is required'
          USING ERRCODE='40001'; END IF;
        SELECT count(*) INTO v_binding_count FROM public.extension_runtime_binding
          WHERE org_id=v_org AND project_id=v_project AND installation_id=p_installation_id;
        IF v_binding_count=0 THEN
          RETURN QUERY SELECT false,NULL::jsonb,NULL::text;RETURN;
        ELSIF v_binding_count<>1 THEN
          RAISE EXCEPTION 'runtime uninstall generation is ambiguous' USING ERRCODE='55000';
        END IF;
        SELECT * INTO v_binding FROM public.extension_runtime_binding
          WHERE org_id=v_org AND project_id=v_project AND installation_id=p_installation_id
          FOR UPDATE;
        IF v_binding.desired_state<>'disabled' OR v_binding.observed_state<>'unknown'
          OR v_binding.enabled OR NOT v_binding.operation_fence
        THEN RAISE EXCEPTION 'runtime binding is not disabled for uninstall'
          USING ERRCODE='55000'; END IF;
        SELECT count(*) INTO v_lifecycle_count
          FROM public.extension_dispatch_lifecycle_operation l
          JOIN public.extension_runtime_operation d
            ON d.org_id=l.org_id AND d.project_id=l.project_id
           AND d.operation_id=l.runtime_operation_id
          JOIN public.extension_dispatch_cutover_operation c
            ON c.org_id=l.org_id AND c.project_id=l.project_id
           AND c.cutover_operation_id=l.activation_operation_id
          WHERE l.org_id=v_org AND l.project_id=v_project
            AND d.installation_id=p_installation_id
            AND c.target_generation=v_binding.generation
            AND d.kind='disable' AND d.status='succeeded' AND d.phase='succeeded'
            AND l.status='detached';
        IF v_lifecycle_count<>1 THEN
          RAISE EXCEPTION 'exact detached disable authority is required'
            USING ERRCODE='55000'; END IF;
        SELECT l.*,d.operation_id AS disable_operation_id,c.target_execution_epoch
          INTO v_lifecycle
          FROM public.extension_dispatch_lifecycle_operation l
          JOIN public.extension_runtime_operation d
            ON d.org_id=l.org_id AND d.project_id=l.project_id
           AND d.operation_id=l.runtime_operation_id
          JOIN public.extension_dispatch_cutover_operation c
            ON c.org_id=l.org_id AND c.project_id=l.project_id
           AND c.cutover_operation_id=l.activation_operation_id
          WHERE l.org_id=v_org AND l.project_id=v_project
            AND d.installation_id=p_installation_id
            AND c.target_generation=v_binding.generation
            AND d.kind='disable' AND d.status='succeeded' AND d.phase='succeeded'
            AND l.status='detached' FOR UPDATE OF l,d,c;
        SELECT count(*) INTO v_receipt_count
          FROM public.extension_dispatch_lifecycle_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.runtime_operation_id=v_lifecycle.disable_operation_id
            AND r.phase IN ('fence','detach');
        IF v_receipt_count<>2 THEN
          RAISE EXCEPTION 'disable lifecycle Receipts are incomplete' USING ERRCODE='55000';
        END IF;
        PERFORM 1 FROM public.extension_runtime_resource_lease r
          JOIN public.extension_runtime_operation o
            ON o.org_id=r.org_id AND o.project_id=r.project_id
           AND o.operation_id=r.operation_id
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND o.installation_id=p_installation_id AND r.generation=v_binding.generation
          ORDER BY r.resource_id FOR UPDATE OF r;
        SELECT count(*),count(*) FILTER(
          WHERE NOT r.observed_release OR r.cleanup_state<>'released')
          INTO v_resource_count,v_unreleased_count
          FROM public.extension_runtime_resource_lease r
          JOIN public.extension_runtime_operation o
            ON o.org_id=r.org_id AND o.project_id=r.project_id
           AND o.operation_id=r.operation_id
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND o.installation_id=p_installation_id AND r.generation=v_binding.generation;
        IF v_resource_count<1 OR v_unreleased_count<>0 THEN
          RAISE EXCEPTION 'runtime resources are not confirmed released'
            USING ERRCODE='55000'; END IF;
        SELECT count(*) INTO v_claimed_occurrences FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project
            AND o.installation_id=p_installation_id AND o.generation=v_binding.generation
            AND o.status='claimed';
        SELECT count(*) INTO v_open_dispatch_attempts
          FROM public.automation_occurrence_dispatch_attempt a
          JOIN public.automation_occurrence o
            ON o.org_id=a.org_id AND o.project_id=a.project_id
           AND o.occurrence_id=a.occurrence_id
          WHERE a.org_id=v_org AND a.project_id=v_project
            AND o.installation_id=p_installation_id AND o.generation=v_binding.generation
            AND a.status IN ('claimed','unknown');
        SELECT count(*) INTO v_running_attempts FROM public.extension_runtime_execution_attempt a
          WHERE a.org_id=v_org AND a.project_id=v_project
            AND a.installation_id=p_installation_id AND a.generation=v_binding.generation
            AND a.state='running';
        IF v_claimed_occurrences<>0 OR v_open_dispatch_attempts<>0 OR v_running_attempts<>0
        THEN RAISE EXCEPTION 'runtime uninstall obligations remain unresolved'
          USING ERRCODE='55000'; END IF;
        SELECT count(*) INTO v_dispatch_count FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id
            AND d.cutover_group_revision=v_lifecycle.fenced_group_revision+1
            AND d.handler_kind='legacy' AND d.installation_id IS NULL
            AND d.generation IS NULL AND d.execution_epoch IS NULL;
        IF v_dispatch_count<>9 OR EXISTS(
          SELECT 1 FROM public.extension_dispatch_claim_gate g
          WHERE g.org_id=v_org AND g.project_id=v_project
            AND g.cutover_group_id=v_lifecycle.cutover_group_id)
        THEN RAISE EXCEPTION 'runtime dispatch is not detached' USING ERRCODE='55000';
        END IF;
        v_authority:=jsonb_build_object(
          'schemaVersion','ar2-runtime-uninstall/v1','orgId',v_org,'projectId',v_project,
          'installationId',p_installation_id::text,
          'installationRevision',p_expected_installation_revision,
          'generation',v_binding.generation::text,
          'bindingFromRevision',v_binding.revision,'bindingToRevision',v_binding.revision+1,
          'disableOperationId',v_lifecycle.disable_operation_id::text,
          'activationOperationId',v_lifecycle.activation_operation_id::text,
          'cutoverGroupId',v_lifecycle.cutover_group_id::text,
          'releasedResourceCount',v_resource_count,'legacyDispatchCount',v_dispatch_count,
          'claimedOccurrenceCount',v_claimed_occurrences,
          'openDispatchAttemptCount',v_open_dispatch_attempts,
          'runningRuntimeAttemptCount',v_running_attempts,'actor',BTRIM(p_actor));
        v_hash:='sha256:'||encode(sha256(convert_to(v_authority::text,'UTF8')),'hex');
        INSERT INTO public.extension_runtime_uninstall_receipt(
          org_id,project_id,receipt_id,installation_id,generation,
          disable_operation_id,activation_operation_id,installation_revision,
          binding_revision,actor,authority_data,content_hash)
        VALUES(v_org,v_project,v_receipt_id,p_installation_id,v_binding.generation,
          v_lifecycle.disable_operation_id,v_lifecycle.activation_operation_id,
          p_expected_installation_revision,v_binding.revision+1,BTRIM(p_actor),v_authority,v_hash);
        UPDATE public.extension_runtime_binding SET desired_state='uninstalled',
          observed_state='stopped',enabled=false,operation_fence=true,revision=revision+1
          WHERE org_id=v_org AND project_id=v_project
            AND installation_id=p_installation_id AND generation=v_binding.generation
            AND revision=v_binding.revision AND desired_state='disabled'
            AND observed_state='unknown' AND NOT enabled AND operation_fence;
        IF NOT FOUND THEN RAISE EXCEPTION 'runtime uninstall binding CAS drifted'
          USING ERRCODE='40001'; END IF;
        RETURN QUERY SELECT true,jsonb_build_object(
          'receiptId',v_receipt_id::text,'authorityData',v_authority),v_hash;
      END $$;
    REVOKE ALL ON FUNCTION extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)
      FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)
      TO aos_app;
    """)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_runtime_uninstall_receipt)
      THEN RAISE EXCEPTION 'cannot downgrade ar2_018 with runtime uninstall authority'
        USING ERRCODE='55000'; END IF;
    END $$""")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION "
        "extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text) FROM aos_app"
    )
    op.execute("DROP FUNCTION extension_runtime_uninstall_commit_ar2_018(uuid,bigint,text)")
    op.execute("DROP FUNCTION extension_runtime_uninstall_consistency_ar2_018() CASCADE")
    op.execute("DROP FUNCTION extension_runtime_uninstall_receipt_hash_ar2_018() CASCADE")
    op.execute("DROP TABLE extension_runtime_uninstall_receipt")
