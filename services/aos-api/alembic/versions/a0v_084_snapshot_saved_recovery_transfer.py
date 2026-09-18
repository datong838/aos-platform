"""Permit one audited disabled definition advance to an exact replacement."""
from alembic import op

revision='a0v_084'
down_revision='a0v_083'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE OR REPLACE FUNCTION advance_snapshot_definition_head_a0v_063() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE request jsonb;
    BEGIN
      IF (NEW.org_id,NEW.project_id,NEW.definition_id) IS DISTINCT FROM
          (OLD.org_id,OLD.project_id,OLD.definition_id)
          OR NEW.revision<>OLD.revision+1 OR OLD.state='retired' THEN
        RAISE EXCEPTION 'snapshot definition head advance invalid' USING ERRCODE='23514';
      END IF;
      IF (NEW.installation_id,NEW.generation) IS DISTINCT FROM
          (OLD.installation_id,OLD.generation) THEN
        SELECT r.request INTO STRICT request
          FROM public.pipeline_snapshot_schedule_definition_revision r
         WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
           AND r.definition_id=NEW.definition_id AND r.revision=NEW.revision;
        IF OLD.state<>'disabled' OR NEW.state<>'disabled'
           OR request->>'intent'<>'transfer_saved_recovery'
           OR request->'settings' IS DISTINCT FROM 'null'::jsonb
           OR jsonb_typeof(request->'transfer')<>'object'
           OR request->'expectedRef' IS DISTINCT FROM jsonb_build_object(
              'resourceType','SnapshotScheduleDefinitionRevision',
              'resourceId','snapshot-schedule-'||OLD.definition_id::text,
              'revision',OLD.revision,'contentHash',OLD.content_hash) THEN
          RAISE EXCEPTION 'snapshot saved recovery transfer invalid' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    COMMENT ON FUNCTION advance_snapshot_definition_head_a0v_063()
      IS 'a0v084: adjacent identity is immutable except audited disabled saved-input replacement transfer';
    ''')


def downgrade():
    raise RuntimeError('saved recovery transfer history must be retained')
