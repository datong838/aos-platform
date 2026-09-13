"""Event schema storage vocabulary only; no write authority or activation."""
from alembic import op

revision='a0v_039'
down_revision='a0v_038'
branch_labels=depends_on=None

_TABLE='ecommerce_investigation_schedule_policy_revision'
_KIND='ecommerce_investigation_schedule_policy_revis_policy_kind_check'
_CADENCE='ecommerce_investigation_schedule_policy_revision_cadence_check'
_PAIR='ck_ecommerce_schedule_event_pair_a0v_039'


def upgrade():
    op.execute("""DO $$ BEGIN
      IF (SELECT count(*) FROM pg_constraint
        WHERE conrelid='ecommerce_investigation_schedule_policy_revision'::regclass AND contype='c'
        AND ((conname='ecommerce_investigation_schedule_policy_revis_policy_kind_check'
          AND pg_get_constraintdef(oid)=$def$CHECK ((policy_kind = ANY (ARRAY['initial_checkup'::text, 'weekly_review'::text, 'topic_analysis'::text])))$def$)
        OR (conname='ecommerce_investigation_schedule_policy_revision_cadence_check'
          AND pg_get_constraintdef(oid)=$def$CHECK ((cadence = ANY (ARRAY['once'::text, 'weekly'::text, 'on_demand'::text])))$def$))) <> 2
      THEN RAISE EXCEPTION 'schedule constraints differ' USING ERRCODE='23514'; END IF;
    END $$""")
    op.execute(f'ALTER TABLE {_TABLE} DROP CONSTRAINT {_KIND}, DROP CONSTRAINT {_CADENCE}')
    op.execute(f"""ALTER TABLE {_TABLE} ADD CONSTRAINT {_PAIR} CHECK (
      (policy_kind IN ('initial_checkup','weekly_review','topic_analysis') AND cadence IN ('once','weekly','on_demand')
        AND (authority_data->>'schemaVersion') IS DISTINCT FROM 'aos.ecommerce.product-event-schedule-policy/v1')
      OR (policy_kind='product_event' AND cadence='event'
        AND (authority_data->>'schemaVersion') IS NOT DISTINCT FROM 'aos.ecommerce.product-event-schedule-policy/v1'))""")


def downgrade():
    op.execute(f"""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM {_TABLE} WHERE policy_kind='product_event' OR cadence='event')
      THEN RAISE EXCEPTION 'event history prevents downgrade' USING ERRCODE='23514'; END IF;
    END $$""")
    op.execute(f'ALTER TABLE {_TABLE} DROP CONSTRAINT {_PAIR}')
    op.execute(f"""ALTER TABLE {_TABLE}
      ADD CONSTRAINT {_KIND} CHECK (policy_kind IN ('initial_checkup','weekly_review','topic_analysis')),
      ADD CONSTRAINT {_CADENCE} CHECK (cadence IN ('once','weekly','on_demand'))""")
