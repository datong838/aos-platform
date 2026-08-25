"""Add tenant-scoped media Provider Job and quarantine authority (W7-07).

Revision ID: w7_005
Revises: w7_004
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w7_005"
down_revision: str | Sequence[str] | None = "w7_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_append_only(table: str) -> str:
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope_{table}_w7_005 ON {table} TO aos_runtime
      USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''));
    GRANT SELECT,INSERT ON {table} TO aos_runtime;
    REVOKE UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime;
    CREATE TRIGGER trg_{table}_append_only_w7_005
      BEFORE UPDATE OR DELETE ON {table}
      FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
    CREATE TRIGGER trg_{table}_truncate_guard_w7_005
      BEFORE TRUNCATE ON {table}
      FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();
    """


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_media_asset_scan_observation (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, scan_id TEXT NOT NULL,
          artifact_ref JSONB NOT NULL, direction TEXT NOT NULL,
          scan_policy_ref JSONB NOT NULL, scanner_ref JSONB NOT NULL,
          detected_mime TEXT NOT NULL, byte_size BIGINT NOT NULL,
          content_hash CHAR(64) NOT NULL, verdict TEXT NOT NULL,
          findings JSONB NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,scan_id),
          CHECK(direction IN ('input','output')),
          CHECK(verdict IN ('passed','rejected','unknown')),
          CHECK(byte_size>=0),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(artifact_ref)='object'),
          CHECK(jsonb_typeof(scan_policy_ref)='object'),
          CHECK(jsonb_typeof(scanner_ref)='object'),
          CHECK(jsonb_typeof(findings)='array'),
          CHECK((verdict='passed' AND jsonb_array_length(findings)=0)
             OR (verdict<>'passed' AND jsonb_array_length(findings)>0))
        );

        CREATE TABLE aip_media_provider_job (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, job_id TEXT NOT NULL,
          task_run_ref JSONB NOT NULL, step_run_ref JSONB NOT NULL,
          binding_snapshot JSONB NOT NULL, input_artifact_refs JSONB NOT NULL,
          input_scan_refs JSONB NOT NULL, scan_policy_ref JSONB NOT NULL,
          scanner_ref JSONB NOT NULL, expected_output_modality TEXT NOT NULL,
          purpose TEXT NOT NULL, data_classification TEXT NOT NULL,
          request_fingerprint CHAR(64) NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,job_id),
          UNIQUE(org_id,project_id,request_fingerprint),
          CHECK(jsonb_typeof(task_run_ref)='object'),
          CHECK(jsonb_typeof(step_run_ref)='object'),
          CHECK(jsonb_typeof(binding_snapshot)='object'),
          CHECK(jsonb_typeof(scan_policy_ref)='object'),
          CHECK(jsonb_typeof(scanner_ref)='object'),
          CHECK(jsonb_typeof(input_artifact_refs)='array' AND jsonb_array_length(input_artifact_refs)>0),
          CHECK(jsonb_typeof(input_scan_refs)='array'
            AND jsonb_array_length(input_scan_refs)=jsonb_array_length(input_artifact_refs)),
          CHECK(expected_output_modality IN ('image','audio','video')),
          CHECK(data_classification IN ('public','internal','confidential','restricted')),
          CHECK(request_fingerprint ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE aip_media_provider_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          job_id TEXT NOT NULL, operation TEXT NOT NULL, outcome TEXT NOT NULL,
          provider_request_id_hash CHAR(64), output_artifact_refs JSONB NOT NULL,
          usage_receipt_ref JSONB, payload_hash CHAR(64) NOT NULL,
          actor TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,receipt_id),
          UNIQUE(org_id,project_id,job_id,operation,payload_hash),
          FOREIGN KEY(org_id,project_id,job_id)
            REFERENCES aip_media_provider_job(org_id,project_id,job_id),
          CHECK(operation IN ('submit','status','webhook','cancel','reconcile')),
          CHECK(outcome IN ('prepared','submitted','running','cancel_requested','unknown','succeeded','failed','cancelled')),
          CHECK(provider_request_id_hash IS NULL OR provider_request_id_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(output_artifact_refs)='array'),
          CHECK(usage_receipt_ref IS NULL OR jsonb_typeof(usage_receipt_ref)='object'),
          CHECK(payload_hash ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE aip_media_provider_job_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, job_id TEXT NOT NULL,
          sequence BIGINT NOT NULL, event_type TEXT NOT NULL, status TEXT NOT NULL,
          provider_receipt_ref JSONB, blocker_codes JSONB NOT NULL,
          event_hash CHAR(64) NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,job_id,sequence),
          UNIQUE(org_id,project_id,job_id,event_hash),
          FOREIGN KEY(org_id,project_id,job_id)
            REFERENCES aip_media_provider_job(org_id,project_id,job_id),
          CHECK(sequence>=1),
          CHECK(event_type IN ('prepared','submitted','status_observed','cancel_requested','reconciled')),
          CHECK(status IN ('prepared','submitted','running','cancel_requested','unknown','succeeded','failed','cancelled')),
          CHECK(provider_receipt_ref IS NULL OR jsonb_typeof(provider_receipt_ref)='object'),
          CHECK(jsonb_typeof(blocker_codes)='array'),
          CHECK((status IN ('unknown','failed') AND jsonb_array_length(blocker_codes)>0)
             OR (status NOT IN ('unknown','failed') AND jsonb_array_length(blocker_codes)=0)),
          CHECK(event_hash ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE aip_media_access_grant (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, grant_id TEXT NOT NULL,
          artifact_ref JSONB NOT NULL, principal_ref TEXT NOT NULL,
          purpose TEXT NOT NULL, marking TEXT NOT NULL, license_ref JSONB NOT NULL,
          expires_at TIMESTAMPTZ NOT NULL, token_hash CHAR(64) NOT NULL,
          access_receipt_ref JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,grant_id),
          UNIQUE(org_id,project_id,token_hash),
          CHECK(jsonb_typeof(artifact_ref)='object'),
          CHECK(jsonb_typeof(license_ref)='object'),
          CHECK(jsonb_typeof(access_receipt_ref)='object'),
          CHECK(token_hash ~ '^[0-9a-f]{64}$'),
          CHECK(expires_at>created_at)
        );

        CREATE TABLE aip_media_provider_job_idempotency (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          result_ref JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,operation,idempotency_key),
          CHECK(char_length(idempotency_key) BETWEEN 1 AND 120),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(result_ref)='object')
        );

        CREATE INDEX idx_media_job_task_w7_005
          ON aip_media_provider_job(org_id,project_id,(task_run_ref->>'resourceId'),created_at DESC);
        CREATE INDEX idx_media_job_event_status_w7_005
          ON aip_media_provider_job_event(org_id,project_id,status,created_at DESC);
        CREATE INDEX idx_media_scan_artifact_w7_005
          ON aip_media_asset_scan_observation(org_id,project_id,(artifact_ref->>'resourceId'),created_at DESC);
        """
    )
    for table in (
        "aip_media_asset_scan_observation",
        "aip_media_provider_job",
        "aip_media_provider_receipt",
        "aip_media_provider_job_event",
        "aip_media_access_grant",
        "aip_media_provider_job_idempotency",
    ):
        op.execute(_tenant_append_only(table))


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_media_provider_job LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_media_asset_scan_observation LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_media_provider_receipt LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_media_access_grant LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade w7_005 with media Provider authority data'
            USING ERRCODE='55000'; END IF;
        END $$;
        DROP TABLE aip_media_provider_job_idempotency CASCADE;
        DROP TABLE aip_media_access_grant CASCADE;
        DROP TABLE aip_media_provider_job_event CASCADE;
        DROP TABLE aip_media_provider_receipt CASCADE;
        DROP TABLE aip_media_provider_job CASCADE;
        DROP TABLE aip_media_asset_scan_observation CASCADE;
        """
    )
