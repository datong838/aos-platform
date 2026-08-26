"""Add fenced delivery control for the immutable DataRequirement Outbox.

Revision ID: biw2_004
Revises: biw2_003
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw2_004"
down_revision: str | Sequence[str] | None = "biw2_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLAIM_SIGNATURE = "(text,text,text,integer)"
FINISH_SIGNATURE = "(text,text,text)"
RECONCILE_SIGNATURE = "(text,text)"


def _secure_function(name: str, signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {name}{signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {name}{signature} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE data_requirement_outbox_delivery (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, outbox_id TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending', attempt INTEGER NOT NULL DEFAULT 0,
          worker_id TEXT, lease_token TEXT, lease_expires_at TIMESTAMPTZ,
          failure_code TEXT, reconciliation_receipt_id TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,outbox_id),
          FOREIGN KEY(org_id,project_id,outbox_id)
            REFERENCES data_requirement_outbox(org_id,project_id,outbox_id),
          CHECK(state IN ('pending','claimed','acked','failed','unknown')),
          CHECK(attempt>=0),
          CHECK((state='pending' AND attempt=0 AND worker_id IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)
             OR (state<>'pending' AND attempt>=1)),
          CHECK((state='claimed' AND worker_id IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
             OR state<>'claimed')
        )"""
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_data_requirement_outbox_delivery_token_biw2_004 "
        "ON data_requirement_outbox_delivery(org_id,project_id,lease_token) WHERE lease_token IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_data_requirement_outbox_delivery_claim_biw2_004 "
        "ON data_requirement_outbox_delivery(org_id,project_id,state,lease_expires_at,updated_at)"
    )
    op.execute("ALTER TABLE data_requirement_outbox_delivery ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE data_requirement_outbox_delivery FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_data_requirement_outbox_delivery_biw2_004
        ON data_requirement_outbox_delivery TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("GRANT SELECT ON data_requirement_outbox_delivery TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON data_requirement_outbox_delivery FROM aos_runtime")
    op.execute("REVOKE INSERT ON data_requirement_outbox FROM aos_runtime")

    op.execute(
        """CREATE FUNCTION data_requirement_outbox_claim_biw2_004(
          p_topic text,p_worker_id text,p_lease_token text,p_lease_seconds integer
        ) RETURNS TABLE(outbox_id text,requirement_id text,requirement_revision bigint,
          event_id text,topic text,payload jsonb,content_hash text,attempt integer,
          lease_token text,lease_expires_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_row record;
          v_lease_expires_at timestamptz;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_topic)='' OR btrim(p_worker_id)=''
             OR btrim(p_lease_token)='' OR p_lease_seconds<1 OR p_lease_seconds>3600
          THEN RAISE EXCEPTION USING ERRCODE='DO001',MESSAGE='invalid tenant-bound claim'; END IF;
          INSERT INTO data_requirement_outbox_delivery(org_id,project_id,outbox_id)
          SELECT o.org_id,o.project_id,o.outbox_id FROM data_requirement_outbox o
           WHERE o.org_id=v_org AND o.project_id=v_project AND o.topic=p_topic
          ON CONFLICT DO NOTHING;
          SELECT o.outbox_id,o.requirement_id,o.requirement_revision,o.event_id,o.topic,
                 o.payload,o.content_hash,d.attempt
            INTO v_row
            FROM data_requirement_outbox_delivery d
            JOIN data_requirement_outbox o USING(org_id,project_id,outbox_id)
           WHERE d.org_id=v_org AND d.project_id=v_project AND o.topic=p_topic
             AND (d.state='pending' OR (d.state='claimed' AND d.lease_expires_at<=NOW()))
           ORDER BY o.created_at,o.outbox_id
           FOR UPDATE OF d SKIP LOCKED LIMIT 1;
          IF NOT FOUND THEN RETURN; END IF;
          v_lease_expires_at:=NOW()+make_interval(secs=>p_lease_seconds);
          UPDATE data_requirement_outbox_delivery d SET state='claimed',attempt=d.attempt+1,
                 worker_id=p_worker_id,lease_token=p_lease_token,
                 lease_expires_at=v_lease_expires_at,
                 failure_code=NULL,reconciliation_receipt_id=NULL,updated_at=NOW()
           WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=v_row.outbox_id;
          RETURN QUERY SELECT v_row.outbox_id,v_row.requirement_id,v_row.requirement_revision,
            v_row.event_id,v_row.topic,v_row.payload,btrim(v_row.content_hash),v_row.attempt+1,
            p_lease_token,v_lease_expires_at;
        END $$"""
    )

    for operation, state in (("ack", "acked"), ("fail", "failed"), ("unknown", "unknown")):
        op.execute(
            f"""CREATE FUNCTION data_requirement_outbox_{operation}_biw2_004(
              p_outbox_id text,p_lease_token text,p_reason_code text
            ) RETURNS TABLE(state text,replayed boolean)
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
              v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_row record;
            BEGIN
              IF v_org IS NULL OR v_project IS NULL OR btrim(p_outbox_id)='' OR btrim(p_lease_token)=''
              THEN RAISE EXCEPTION USING ERRCODE='DO001',MESSAGE='invalid tenant-bound delivery command'; END IF;
              SELECT d.state,d.lease_token,d.lease_expires_at INTO v_row
                FROM data_requirement_outbox_delivery d
               WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=p_outbox_id FOR UPDATE;
              IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='DO002',MESSAGE='outbox delivery not found'; END IF;
              IF v_row.state='{state}' AND v_row.lease_token=p_lease_token THEN
                RETURN QUERY SELECT '{state}'::text,true; RETURN;
              END IF;
              IF v_row.state<>'claimed' OR v_row.lease_token<>p_lease_token OR v_row.lease_expires_at<=NOW()
              THEN RAISE EXCEPTION USING ERRCODE='DO003',MESSAGE='stale outbox delivery fence'; END IF;
              UPDATE data_requirement_outbox_delivery d SET state='{state}',
                failure_code=CASE WHEN '{state}' IN ('failed','unknown') THEN NULLIF(btrim(p_reason_code),'') ELSE NULL END,
                updated_at=NOW()
               WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=p_outbox_id;
              RETURN QUERY SELECT '{state}'::text,false;
            END $$"""
        )

    op.execute(
        """CREATE FUNCTION data_requirement_outbox_reconcile_biw2_004(
          p_outbox_id text,p_receipt_id text
        ) RETURNS TABLE(state text,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_row record;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR btrim(p_outbox_id)='' OR btrim(p_receipt_id)=''
          THEN RAISE EXCEPTION USING ERRCODE='DO001',MESSAGE='invalid tenant-bound reconcile'; END IF;
          SELECT d.state,d.reconciliation_receipt_id,o.requirement_id,o.requirement_revision INTO v_row
            FROM data_requirement_outbox_delivery d
            JOIN data_requirement_outbox o USING(org_id,project_id,outbox_id)
           WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=p_outbox_id FOR UPDATE OF d;
          IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='DO002',MESSAGE='outbox delivery not found'; END IF;
          IF v_row.state='acked' AND v_row.reconciliation_receipt_id=p_receipt_id THEN
            RETURN QUERY SELECT 'acked'::text,true; RETURN;
          END IF;
          IF v_row.state<>'unknown' OR NOT EXISTS(
            SELECT 1 FROM data_fulfillment_receipt r
             WHERE r.org_id=v_org AND r.project_id=v_project AND r.receipt_id=p_receipt_id
               AND r.requirement_id=v_row.requirement_id
               AND r.requirement_revision=v_row.requirement_revision AND r.status<>'unknown'
          ) THEN RAISE EXCEPTION USING ERRCODE='DO003',MESSAGE='unknown delivery lacks exact receipt evidence'; END IF;
          UPDATE data_requirement_outbox_delivery d SET state='acked',
            reconciliation_receipt_id=p_receipt_id,failure_code=NULL,updated_at=NOW()
           WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=p_outbox_id;
          RETURN QUERY SELECT 'acked'::text,false;
        END $$"""
    )

    _secure_function("data_requirement_outbox_claim_biw2_004", CLAIM_SIGNATURE)
    for operation in ("ack", "fail", "unknown"):
        _secure_function(f"data_requirement_outbox_{operation}_biw2_004", FINISH_SIGNATURE)
    _secure_function("data_requirement_outbox_reconcile_biw2_004", RECONCILE_SIGNATURE)


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM data_requirement_outbox_delivery LIMIT 1) THEN
            RAISE EXCEPTION 'cannot downgrade biw2_004 with outbox delivery state' USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute(f"DROP FUNCTION data_requirement_outbox_reconcile_biw2_004{RECONCILE_SIGNATURE}")
    for operation in ("unknown", "fail", "ack"):
        op.execute(f"DROP FUNCTION data_requirement_outbox_{operation}_biw2_004{FINISH_SIGNATURE}")
    op.execute(f"DROP FUNCTION data_requirement_outbox_claim_biw2_004{CLAIM_SIGNATURE}")
    op.execute("GRANT INSERT ON data_requirement_outbox TO aos_runtime")
    op.execute("DROP TABLE data_requirement_outbox_delivery")
