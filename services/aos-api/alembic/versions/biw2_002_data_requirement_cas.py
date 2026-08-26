"""Add the controlled DataRequirement CAS entrypoint.

Revision ID: biw2_002
Revises: biw2_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "biw2_002"
down_revision: str | Sequence[str] | None = "biw2_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURE = "(text,bigint,text,text,char,bigint,bigint,char,text,jsonb,jsonb,jsonb,jsonb,text,text,text)"


def upgrade() -> None:
    op.execute(
        """CREATE FUNCTION data_requirement_apply_biw2_002(
          p_requirement_id text, p_expected_version bigint, p_operation text,
          p_idempotency_key text, p_request_hash char(64), p_revision bigint,
          p_prior_revision bigint, p_content_hash char(64), p_status text,
          p_case_ref jsonb, p_run_ref jsonb, p_checkpoint_ref jsonb,
          p_payload jsonb, p_created_by text, p_event_id text, p_outbox_id text
        ) RETURNS TABLE(
          requirement_revision bigint, result_content_hash text,
          head_version bigint, replayed boolean
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_org text := NULLIF(current_setting('aos.org_id', true), '');
          v_project text := NULLIF(current_setting('aos.project_id', true), '');
          v_head record;
          v_replay record;
          v_from_status text;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL THEN
            RAISE EXCEPTION USING ERRCODE='DR004', MESSAGE='tenant scope is required';
          END IF;
          IF p_operation NOT IN ('request','accept','reject','cancel') THEN
            RAISE EXCEPTION USING ERRCODE='DR003', MESSAGE='unsupported DataRequirement operation';
          END IF;

          PERFORM pg_advisory_xact_lock(
            hashtextextended(concat_ws(':',v_org,v_project,p_operation,p_idempotency_key),0)
          );
          SELECT r.revision,r.content_hash,r.request_hash INTO v_replay
          FROM data_requirement_revision r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.operation=p_operation AND r.idempotency_key=p_idempotency_key;
          IF FOUND THEN
            IF v_replay.request_hash<>p_request_hash THEN
              RAISE EXCEPTION USING ERRCODE='DR002', MESSAGE='idempotency conflict';
            END IF;
            RETURN QUERY SELECT v_replay.revision,btrim(v_replay.content_hash),v_replay.revision,true;
            RETURN;
          END IF;

          SELECT h.current_revision,h.current_content_hash,h.status,h.version INTO v_head
          FROM data_requirement_head h
          WHERE h.org_id=v_org AND h.project_id=v_project
            AND h.requirement_id=p_requirement_id
          FOR UPDATE;

          IF p_operation='request' THEN
            IF FOUND OR p_expected_version<>0 OR p_revision<>1
               OR p_prior_revision IS NOT NULL OR p_status<>'requested' THEN
              RAISE EXCEPTION USING ERRCODE='DR001', MESSAGE='request expected version mismatch';
            END IF;
            v_from_status := NULL;
            INSERT INTO data_requirement_head(
              org_id,project_id,requirement_id,current_revision,
              current_content_hash,status,version,created_by
            ) VALUES(
              v_org,v_project,p_requirement_id,1,p_content_hash,p_status,1,p_created_by
            );
          ELSE
            IF NOT FOUND OR v_head.version<>p_expected_version
               OR p_revision<>p_expected_version+1
               OR p_prior_revision<>v_head.current_revision THEN
              RAISE EXCEPTION USING ERRCODE='DR001', MESSAGE='expected version mismatch';
            END IF;
            v_from_status := v_head.status;
            IF NOT (
              (v_from_status='requested' AND p_status IN ('accepted','rejected','cancelled'))
              OR (v_from_status='accepted' AND p_status='cancelled')
            ) THEN
              RAISE EXCEPTION USING ERRCODE='DR003', MESSAGE='invalid DataRequirement transition';
            END IF;
            IF p_operation='accept' AND p_status<>'accepted'
               OR p_operation='reject' AND p_status<>'rejected'
               OR p_operation='cancel' AND p_status<>'cancelled' THEN
              RAISE EXCEPTION USING ERRCODE='DR003', MESSAGE='operation and status mismatch';
            END IF;
            UPDATE data_requirement_head
            SET current_revision=p_revision,current_content_hash=p_content_hash,
                status=p_status,version=version+1,updated_at=NOW()
            WHERE org_id=v_org AND project_id=v_project
              AND requirement_id=p_requirement_id AND version=p_expected_version;
            IF NOT FOUND THEN
              RAISE EXCEPTION USING ERRCODE='DR001', MESSAGE='authority head CAS lost';
            END IF;
          END IF;

          INSERT INTO data_requirement_revision(
            org_id,project_id,requirement_id,revision,prior_revision,
            content_hash,status,operation,idempotency_key,request_hash,
            case_ref,run_ref,checkpoint_ref,payload,created_by
          ) VALUES(
            v_org,v_project,p_requirement_id,p_revision,p_prior_revision,
            p_content_hash,p_status,p_operation,p_idempotency_key,p_request_hash,
            p_case_ref,p_run_ref,p_checkpoint_ref,p_payload,p_created_by
          );
          INSERT INTO data_requirement_event(
            org_id,project_id,requirement_id,requirement_revision,event_id,
            sequence,event_type,from_status,to_status,payload,content_hash,created_by
          ) VALUES(
            v_org,v_project,p_requirement_id,p_revision,p_event_id,p_revision,
            'data_requirement.'||p_operation,v_from_status,p_status,
            jsonb_build_object('requirementId',p_requirement_id,'revision',p_revision,
              'contentHash','sha256:'||btrim(p_content_hash),'status',p_status),
            p_content_hash,p_created_by
          );
          INSERT INTO data_requirement_outbox(
            org_id,project_id,outbox_id,requirement_id,requirement_revision,
            event_id,topic,payload,content_hash,created_by
          ) VALUES(
            v_org,v_project,p_outbox_id,p_requirement_id,p_revision,p_event_id,
            'data.requirement.'||p_operation,
            jsonb_build_object('eventId',p_event_id,'requirementId',p_requirement_id,
              'revision',p_revision,'contentHash','sha256:'||btrim(p_content_hash)),
            p_content_hash,p_created_by
          );
          RETURN QUERY SELECT p_revision,btrim(p_content_hash),p_revision,false;
        END;
        $$"""
    )
    op.execute(f"REVOKE ALL ON FUNCTION data_requirement_apply_biw2_002{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION data_requirement_apply_biw2_002{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION data_requirement_apply_biw2_002{SIGNATURE} FROM aos_runtime")
    op.execute(f"DROP FUNCTION data_requirement_apply_biw2_002{SIGNATURE}")
