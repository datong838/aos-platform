"""Add controlled exact FulfillmentReceipt binding. Revision ID: biw2_003."""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op

revision: str = "biw2_003"
down_revision: str | Sequence[str] | None = "biw2_002"
branch_labels = None
depends_on = None
SIGNATURE = "(text,text,text,bigint,char,text,jsonb,jsonb,timestamptz,timestamptz,char,text,text,char)"


def upgrade() -> None:
    op.execute("ALTER TABLE data_fulfillment_receipt ADD COLUMN operation TEXT, ADD COLUMN idempotency_key TEXT, ADD COLUMN request_hash CHAR(64)")
    op.execute("CREATE UNIQUE INDEX uq_data_fulfillment_idempotency_biw2_003 ON data_fulfillment_receipt(org_id,project_id,operation,idempotency_key) WHERE operation IS NOT NULL AND idempotency_key IS NOT NULL")
    op.execute("REVOKE INSERT ON data_fulfillment_receipt FROM aos_runtime")
    op.execute("""CREATE FUNCTION data_fulfillment_bind_biw2_003(
      p_fulfillment_id text,p_receipt_id text,p_requirement_id text,p_requirement_revision bigint,
      p_requirement_hash char(64),p_status text,p_artifact_refs jsonb,p_source_readiness_ref jsonb,
      p_cutoff_at timestamptz,p_fulfilled_at timestamptz,p_content_hash char(64),p_created_by text,
      p_idempotency_key text,p_request_hash char(64)
    ) RETURNS TABLE(bound_receipt_id text,result_content_hash text,replayed boolean)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),''); v_project text:=NULLIF(current_setting('aos.project_id',true),''); v_head record; v_old record;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='tenant scope required'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(concat_ws(':',v_org,v_project,'fulfillment.bind',p_idempotency_key),0));
      SELECT receipt_id,content_hash,request_hash INTO v_old FROM data_fulfillment_receipt
       WHERE org_id=v_org AND project_id=v_project AND operation='fulfillment.bind' AND idempotency_key=p_idempotency_key;
      IF FOUND THEN
        IF v_old.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='DF002',MESSAGE='idempotency conflict'; END IF;
        RETURN QUERY SELECT v_old.receipt_id,btrim(v_old.content_hash),true; RETURN;
      END IF;
      SELECT current_revision,current_content_hash INTO v_head FROM data_requirement_head
       WHERE org_id=v_org AND project_id=v_project AND requirement_id=p_requirement_id FOR SHARE;
      IF NOT FOUND OR v_head.current_revision<>p_requirement_revision OR v_head.current_content_hash<>p_requirement_hash
      THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='requirement exact ref is not current'; END IF;
      INSERT INTO data_fulfillment_receipt(org_id,project_id,fulfillment_id,receipt_id,requirement_id,requirement_revision,status,artifact_refs,source_readiness_ref,cutoff_at,fulfilled_at,content_hash,created_by,operation,idempotency_key,request_hash)
      VALUES(v_org,v_project,p_fulfillment_id,p_receipt_id,p_requirement_id,p_requirement_revision,p_status,p_artifact_refs,p_source_readiness_ref,p_cutoff_at,p_fulfilled_at,p_content_hash,p_created_by,'fulfillment.bind',p_idempotency_key,p_request_hash);
      RETURN QUERY SELECT p_receipt_id,btrim(p_content_hash),false;
    END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION data_fulfillment_bind_biw2_003{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION data_fulfillment_bind_biw2_003{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION data_fulfillment_bind_biw2_003{SIGNATURE} FROM aos_runtime")
    op.execute(f"DROP FUNCTION data_fulfillment_bind_biw2_003{SIGNATURE}")
    op.execute("GRANT INSERT ON data_fulfillment_receipt TO aos_runtime")
    op.execute("DROP INDEX uq_data_fulfillment_idempotency_biw2_003")
    op.execute("ALTER TABLE data_fulfillment_receipt DROP COLUMN request_hash, DROP COLUMN idempotency_key, DROP COLUMN operation")
