"""A saved-input renewal definition is never an ordinary schedule read grant."""
from alembic import op
revision='a0v_066'
down_revision='a0v_065'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    CREATE FUNCTION reject_recovery_only_schedule_claim_a0v_066() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    BEGIN
        IF EXISTS(SELECT 1 FROM public.pipeline_snapshot_schedule_definition_revision d
            WHERE d.org_id=NEW.org_id AND d.project_id=NEW.project_id
                AND 'snapshot-schedule-'||d.definition_id::text=NEW.request->'definitionRef'->>'resourceId'
                AND d.revision::text=NEW.request->'definitionRef'->>'revision'
                AND d.content_hash=NEW.request->'definitionRef'->>'contentHash'
                AND d.request->>'intent'='renew_saved_group') THEN
            RAISE EXCEPTION 'snapshot recovery-only definition cannot create new schedule claims' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER snapshot_recovery_only_claim_fence BEFORE INSERT ON pipeline_snapshot_schedule_claim
        FOR EACH ROW EXECUTE FUNCTION reject_recovery_only_schedule_claim_a0v_066();
    ''')


def downgrade():raise RuntimeError('saved-input recovery admission fence must be retained')
