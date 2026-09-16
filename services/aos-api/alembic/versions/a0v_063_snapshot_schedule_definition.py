"""Versioned installed snapshot schedule configuration and exclusive membership."""
from alembic import op
revision='a0v_063'
down_revision='a0v_062'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    CREATE TABLE pipeline_snapshot_schedule_definition_revision(
        org_id text NOT NULL,project_id text NOT NULL,definition_id uuid NOT NULL,
        revision bigint NOT NULL CHECK(revision>0),previous_revision bigint,previous_hash text,
        installation_id uuid NOT NULL,generation uuid NOT NULL,
        state text NOT NULL CHECK(state IN ('disabled','enabled','retired')),
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        request jsonb NOT NULL CHECK(jsonb_typeof(request)='object' AND octet_length(request::text)<=65536),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        body jsonb NOT NULL CHECK(jsonb_typeof(body)='object' AND octet_length(body::text)<=65536),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,definition_id,revision),
        UNIQUE(org_id,project_id,definition_id,revision,content_hash),
        UNIQUE(org_id,project_id,definition_id,idempotency_key),
        FOREIGN KEY(org_id,project_id,definition_id,previous_revision,previous_hash)
            REFERENCES pipeline_snapshot_schedule_definition_revision(org_id,project_id,definition_id,revision,content_hash),
        CHECK((revision=1 AND previous_revision IS NULL AND previous_hash IS NULL)
            OR (revision>1 AND previous_revision=revision-1 AND previous_hash IS NOT NULL))
    );
    CREATE TABLE pipeline_snapshot_schedule_definition_member(
        org_id text NOT NULL,project_id text NOT NULL,definition_id uuid NOT NULL,revision bigint NOT NULL,
        ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 12),schedule_id text NOT NULL,
        binding_id uuid NOT NULL,binding_revision bigint NOT NULL,binding_hash text NOT NULL,
        PRIMARY KEY(org_id,project_id,definition_id,revision,ordinal),
        UNIQUE(org_id,project_id,definition_id,revision,schedule_id),
        FOREIGN KEY(org_id,project_id,definition_id,revision)
            REFERENCES pipeline_snapshot_schedule_definition_revision(org_id,project_id,definition_id,revision),
        FOREIGN KEY(org_id,project_id,schedule_id,binding_id,binding_revision,binding_hash)
            REFERENCES pipeline_schedule_control_binding(org_id,project_id,schedule_id,binding_id,revision,content_hash)
    );
    CREATE TABLE pipeline_snapshot_schedule_definition_head(
        org_id text NOT NULL,project_id text NOT NULL,definition_id uuid NOT NULL,
        revision bigint NOT NULL,content_hash text NOT NULL,state text NOT NULL,
        installation_id uuid NOT NULL,generation uuid NOT NULL,
        PRIMARY KEY(org_id,project_id,definition_id),
        UNIQUE(org_id,project_id,definition_id,revision),
        FOREIGN KEY(org_id,project_id,definition_id,revision,content_hash)
            REFERENCES pipeline_snapshot_schedule_definition_revision(org_id,project_id,definition_id,revision,content_hash)
    );
    CREATE TABLE pipeline_snapshot_schedule_current_member(
        org_id text NOT NULL,project_id text NOT NULL,schedule_id text NOT NULL,
        definition_id uuid NOT NULL,revision bigint NOT NULL,
        PRIMARY KEY(org_id,project_id,schedule_id),
        FOREIGN KEY(org_id,project_id,definition_id,revision,schedule_id)
            REFERENCES pipeline_snapshot_schedule_definition_member(org_id,project_id,definition_id,revision,schedule_id),
        CONSTRAINT snapshot_definition_current_head_fk FOREIGN KEY(org_id,project_id,definition_id,revision)
            REFERENCES pipeline_snapshot_schedule_definition_head(org_id,project_id,definition_id,revision)
            DEFERRABLE INITIALLY DEFERRED
    );
    CREATE FUNCTION validate_snapshot_definition_revision_a0v_063() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE r public.pipeline_snapshot_schedule_definition_revision; m record; expected jsonb; n integer;
    BEGIN
        IF TG_TABLE_NAME='pipeline_snapshot_schedule_definition_revision' THEN r=NEW;
        ELSE SELECT * INTO STRICT r FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND definition_id=NEW.definition_id AND revision=NEW.revision;
        END IF;
        SELECT count(*) INTO n FROM public.pipeline_snapshot_schedule_definition_member
            WHERE org_id=r.org_id AND project_id=r.project_id AND definition_id=r.definition_id AND revision=r.revision;
        IF (n=12 AND public.canonical_bundle_control_sha256(r.body)=r.content_hash
            AND public.canonical_bundle_control_sha256(r.request)=r.request_hash
            AND r.body->>'schemaVersion'='aos.snapshot-schedule-definition/v1'
            AND r.body->>'orgId'=r.org_id AND r.body->>'projectId'=r.project_id
            AND r.body->>'definitionId'=r.definition_id::text AND (r.body->>'revision')::bigint=r.revision
            AND r.body->>'installationId'=r.installation_id::text AND r.body->>'generation'=r.generation::text
            AND r.body->>'state'=r.state AND r.body->>'actor'=r.actor
            AND jsonb_array_length(r.body->'members')=12) IS NOT TRUE THEN
            RAISE EXCEPTION 'snapshot definition revision incomplete or invalid' USING ERRCODE='23514';
        END IF;
        IF (r.revision=1 AND r.body->'priorRef' IS DISTINCT FROM 'null'::jsonb) OR
            (r.revision>1 AND r.body->'priorRef' IS DISTINCT FROM jsonb_build_object(
                'resourceType','SnapshotScheduleDefinitionRevision','resourceId','snapshot-schedule-'||r.definition_id::text,
                'revision',r.previous_revision,'contentHash',r.previous_hash)) THEN
            RAISE EXCEPTION 'snapshot definition predecessor differs' USING ERRCODE='23514';
        END IF;
        FOR m IN SELECT x.ordinal,x.schedule_id,x.binding_id,x.binding_revision,x.binding_hash,
                b.pipeline_id,b.control_id,b.control_revision,b.control_hash,b.actor,b.installation_id,b.generation
            FROM public.pipeline_snapshot_schedule_definition_member x JOIN public.pipeline_schedule_control_binding b
            ON (b.org_id,b.project_id,b.schedule_id,b.binding_id,b.revision,b.content_hash)=
                (x.org_id,x.project_id,x.schedule_id,x.binding_id,x.binding_revision,x.binding_hash)
            WHERE x.org_id=r.org_id AND x.project_id=r.project_id AND x.definition_id=r.definition_id AND x.revision=r.revision
        LOOP
            expected=jsonb_build_object('scheduleId',m.schedule_id,'pipelineId',m.pipeline_id,
                'bindingRef',jsonb_build_object('resourceType','PipelineScheduleControlBinding','resourceId','schedule-control-'||m.binding_id::text,
                    'revision',m.binding_revision,'contentHash',m.binding_hash),
                'controlRef',jsonb_build_object('resourceType','PipelineRuntimeControlRevision','resourceId','pipeline-control-'||m.control_id::text,
                    'revision',m.control_revision,'contentHash',m.control_hash));
            IF (r.body->'members'->(m.ordinal-1)=expected AND m.actor=r.body->>'executor'
                AND m.installation_id=r.installation_id AND m.generation=r.generation) IS NOT TRUE THEN
                RAISE EXCEPTION 'snapshot definition member differs' USING ERRCODE='23514';
            END IF;
        END LOOP;
        RETURN NEW;
    END $$;
    CREATE FUNCTION validate_snapshot_definition_head_a0v_063() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE t record; h public.pipeline_snapshot_schedule_definition_head; r record; n integer;
    BEGIN
        IF TG_OP='DELETE' THEN t=OLD; ELSE t=NEW; END IF;
        SELECT * INTO STRICT h FROM public.pipeline_snapshot_schedule_definition_head
            WHERE org_id=t.org_id AND project_id=t.project_id AND definition_id=t.definition_id;
        SELECT * INTO STRICT r FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=h.org_id AND project_id=h.project_id AND definition_id=h.definition_id AND revision=h.revision;
        SELECT count(*) INTO n FROM public.pipeline_snapshot_schedule_current_member
            WHERE org_id=h.org_id AND project_id=h.project_id AND definition_id=h.definition_id;
        IF (h.content_hash=r.content_hash AND h.state=r.state AND h.installation_id=r.installation_id AND h.generation=r.generation
            AND n=CASE WHEN h.state='retired' THEN 0 ELSE 12 END) IS NOT TRUE THEN
            RAISE EXCEPTION 'snapshot definition current membership differs' USING ERRCODE='23514';
        END IF;
        RETURN NULL;
    END $$;
    CREATE FUNCTION advance_snapshot_definition_head_a0v_063() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF (NEW.org_id,NEW.project_id,NEW.definition_id,NEW.installation_id,NEW.generation) IS DISTINCT FROM
            (OLD.org_id,OLD.project_id,OLD.definition_id,OLD.installation_id,OLD.generation)
            OR NEW.revision<>OLD.revision+1 OR OLD.state='retired' THEN
            RAISE EXCEPTION 'snapshot definition head advance invalid' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER snapshot_definition_head_advance BEFORE UPDATE ON pipeline_snapshot_schedule_definition_head
        FOR EACH ROW EXECUTE FUNCTION advance_snapshot_definition_head_a0v_063();
    CREATE CONSTRAINT TRIGGER snapshot_definition_revision_complete AFTER INSERT ON pipeline_snapshot_schedule_definition_revision
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_definition_revision_a0v_063();
    CREATE CONSTRAINT TRIGGER snapshot_definition_history_member_complete AFTER INSERT ON pipeline_snapshot_schedule_definition_member
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_definition_revision_a0v_063();
    CREATE CONSTRAINT TRIGGER snapshot_definition_head_complete AFTER INSERT OR UPDATE ON pipeline_snapshot_schedule_definition_head
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_definition_head_a0v_063();
    CREATE CONSTRAINT TRIGGER snapshot_definition_member_complete AFTER INSERT OR UPDATE OR DELETE ON pipeline_snapshot_schedule_current_member
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_definition_head_a0v_063();
    ''')
    history=('pipeline_snapshot_schedule_definition_revision','pipeline_snapshot_schedule_definition_member')
    for table in history+('pipeline_snapshot_schedule_definition_head','pipeline_snapshot_schedule_current_member'):
        op.execute(f'''
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope ON {table}
            USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
            WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
        REVOKE ALL ON {table} FROM PUBLIC,aos_runtime;
        GRANT SELECT,INSERT ON {table} TO aos_runtime;
        CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
        ''')
        if table in history:
            op.execute(f'CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();')
    op.execute('GRANT UPDATE ON pipeline_snapshot_schedule_definition_head TO aos_runtime; GRANT DELETE ON pipeline_snapshot_schedule_current_member TO aos_runtime;')
    op.execute('CREATE TRIGGER immutable_head_delete BEFORE DELETE ON pipeline_snapshot_schedule_definition_head FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();')


def downgrade():
    raise RuntimeError('snapshot schedule definition history must be retained')
