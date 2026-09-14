"""Bind complete snapshot groups to immutable source claims and original inputs."""
from alembic import op

revision='a0v_045'
down_revision='a0v_044'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    CREATE TABLE pipeline_snapshot_group_claim(
        org_id text NOT NULL,project_id text NOT NULL,group_id uuid NOT NULL,
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240 AND actor=btrim(actor)),
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        member_count smallint NOT NULL CHECK(member_count BETWEEN 1 AND 12),
        binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object' AND octet_length(binding::text)<=65536),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,group_id),
        UNIQUE(org_id,project_id,group_id,request_hash)
    );
    CREATE TABLE pipeline_snapshot_group_member(
        org_id text NOT NULL,project_id text NOT NULL,group_id uuid NOT NULL,
        ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 12),run_id text NOT NULL,
        PRIMARY KEY(org_id,project_id,group_id,ordinal),
        UNIQUE(org_id,project_id,run_id),
        FOREIGN KEY(org_id,project_id,group_id) REFERENCES pipeline_snapshot_group_claim(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,run_id) REFERENCES pipeline_controlled_source_claim(org_id,project_id,run_id)
    );
    CREATE TABLE pipeline_snapshot_group_input(
        org_id text NOT NULL,project_id text NOT NULL,group_id uuid NOT NULL,
        request_hash text NOT NULL,read_started_at timestamptz NOT NULL,read_completed_at timestamptz NOT NULL,
        snapshot_basis text NOT NULL CHECK(snapshot_basis='innodb-repeatable-read'),
        manifest_hash text NOT NULL CHECK(manifest_hash ~ '^sha256:[0-9a-f]{64}$'),
        manifest jsonb NOT NULL CHECK(jsonb_typeof(manifest)='object' AND octet_length(manifest::text)<=65536),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,group_id,request_hash) REFERENCES pipeline_snapshot_group_claim(org_id,project_id,group_id,request_hash),
        CHECK(read_completed_at>=read_started_at)
    );
    CREATE FUNCTION validate_snapshot_group_a0v_045() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE expected integer;actual integer;last_ordinal integer;group_actor text;valid_actor_count integer;
        item jsonb;run_ids text[]:=ARRAY[]::text[];found_input boolean;
    BEGIN
        EXECUTE format('SELECT member_count,actor FROM %I.pipeline_snapshot_group_claim WHERE org_id=$1 AND project_id=$2 AND group_id=$3',TG_TABLE_SCHEMA)
            INTO expected,group_actor USING NEW.org_id,NEW.project_id,NEW.group_id;
        EXECUTE format('SELECT count(*),max(ordinal) FROM %I.pipeline_snapshot_group_member WHERE org_id=$1 AND project_id=$2 AND group_id=$3',TG_TABLE_SCHEMA)
            INTO actual,last_ordinal USING NEW.org_id,NEW.project_id,NEW.group_id;
        IF expected IS NULL OR actual<>expected OR last_ordinal<>expected THEN
            RAISE EXCEPTION 'snapshot group membership incomplete' USING ERRCODE='23514';
        END IF;
        EXECUTE format('SELECT count(*) FROM %I.pipeline_snapshot_group_member m JOIN %I.pipeline_controlled_source_claim c ON (c.org_id,c.project_id,c.run_id)=(m.org_id,m.project_id,m.run_id) WHERE m.org_id=$1 AND m.project_id=$2 AND m.group_id=$3 AND c.actor=$4',TG_TABLE_SCHEMA,TG_TABLE_SCHEMA)
            INTO valid_actor_count USING NEW.org_id,NEW.project_id,NEW.group_id,group_actor;
        IF valid_actor_count<>expected THEN RAISE EXCEPTION 'snapshot group source actor differs' USING ERRCODE='23514'; END IF;
        IF TG_TABLE_NAME='pipeline_snapshot_group_input' THEN
            IF jsonb_typeof(NEW.manifest->'members') IS DISTINCT FROM 'array' OR NEW.manifest-'members'<>'{}'::jsonb THEN
                RAISE EXCEPTION 'snapshot group input manifest shape differs' USING ERRCODE='23514';
            END IF;
            IF jsonb_array_length(NEW.manifest->'members')<>expected THEN
                RAISE EXCEPTION 'snapshot group input membership incomplete' USING ERRCODE='23514';
            END IF;
            FOR item IN SELECT value FROM jsonb_array_elements(NEW.manifest->'members') LOOP
                IF (jsonb_typeof(item)='object' AND item ?& ARRAY['runId','envelopeHash','rowsHash','rowCount']
                    AND item-ARRAY['runId','envelopeHash','rowsHash','rowCount']='{}'::jsonb
                    AND jsonb_typeof(item->'runId')='string' AND length(item->>'runId') BETWEEN 1 AND 200
                    AND jsonb_typeof(item->'envelopeHash')='string' AND item->>'envelopeHash' ~ '^[0-9a-f]{64}$'
                    AND jsonb_typeof(item->'rowsHash')='string' AND item->>'rowsHash' ~ '^sha256:[0-9a-f]{64}$'
                    AND jsonb_typeof(item->'rowCount')='number' AND item->>'rowCount' ~ '^(0|[1-9][0-9]{0,2})$') IS NOT TRUE THEN
                    RAISE EXCEPTION 'snapshot group input member shape differs' USING ERRCODE='23514';
                END IF;
                IF item->>'runId'=ANY(run_ids) THEN RAISE EXCEPTION 'duplicate snapshot group input' USING ERRCODE='23514'; END IF;
                run_ids:=array_append(run_ids,item->>'runId');
                EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I.pipeline_snapshot_group_member m JOIN %I.ecommerce_ingress_command i ON (i.org_id,i.project_id,i.run_id)=(m.org_id,m.project_id,m.run_id) WHERE m.org_id=$1 AND m.project_id=$2 AND m.group_id=$3 AND m.run_id=$4 AND i.envelope_hash=$5)',TG_TABLE_SCHEMA,TG_TABLE_SCHEMA)
                    INTO found_input USING NEW.org_id,NEW.project_id,NEW.group_id,item->>'runId',item->>'envelopeHash';
                IF NOT found_input THEN RAISE EXCEPTION 'snapshot group original input differs' USING ERRCODE='23514'; END IF;
            END LOOP;
        END IF;
        RETURN NEW;
    END $$;
    ''')
    for table in ('pipeline_snapshot_group_claim','pipeline_snapshot_group_member','pipeline_snapshot_group_input'):
        op.execute(f'''
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope ON {table}
            USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
            WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
        CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
        CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
        CREATE CONSTRAINT TRIGGER complete_snapshot_group AFTER INSERT ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_group_a0v_045();
        REVOKE ALL ON {table} FROM PUBLIC,aos_runtime;
        GRANT SELECT,INSERT ON {table} TO aos_runtime;
        ''')


def downgrade():
    raise RuntimeError('snapshot group history must be retained; destructive downgrade is not supported')
