"""O1-A0: Expand-only migration — DLQ + derived columns + projection outbox + alias sidecar + uninstalled fix.

Revision ID: o1a0_001
Revises: 228ti6edirectory
Create Date: 2026-08-09

O1-A0 安全扩展与前置门：
- ecom_dlq / ecom_dlq_retry_receipt / ecom_dlq_retry_event
- ecom_object 派生列 (derived_revision, derived_input_revision, derived_input_hash, derived_computed_at, derived_payload)
- ecom_derived_receipt
- projection_outbox / projection_watermark
- ecom_alias_migration (sidecar 台账)
- bundle_installation_revision.state CHECK 补 'uninstalled'

所有新表使用兼容默认值，不改变现有读路径。RLS FORCE + FK + CHECK。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1a0_001"
down_revision: str | Sequence[str] | None = "228ti6edirectory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════
    # 1. ecom_object 派生列（expand-only，历史行使用默认值）
    # ═══════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE ecom_object
          ADD COLUMN IF NOT EXISTS derived_revision INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS derived_input_revision BIGINT NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS derived_input_hash CHAR(64) DEFAULT NULL,
          ADD COLUMN IF NOT EXISTS derived_computed_at TIMESTAMPTZ DEFAULT NULL,
          ADD COLUMN IF NOT EXISTS derived_payload JSONB NOT NULL DEFAULT '{}'::jsonb;
    """)

    op.execute("""
        ALTER TABLE ecom_object
          ADD CONSTRAINT chk_derived_revision_nonneg CHECK (derived_revision >= 0),
          ADD CONSTRAINT chk_derived_input_revision_nonneg CHECK (derived_input_revision >= 0);
    """)

    # ═══════════════════════════════════════════════════════
    # 2. ecom_dlq（Dead Letter Queue）
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS ecom_dlq (
          dlq_id              TEXT        NOT NULL,
          org_id              TEXT        NOT NULL,
          project_id          TEXT        NOT NULL,
          workspace_id        TEXT        NOT NULL,
          pipeline_id         TEXT        NOT NULL,
          source_external_id  TEXT        DEFAULT NULL,
          source_object_type  TEXT        DEFAULT NULL,
          source_platform     TEXT        NOT NULL,
          source_shop_id      TEXT        NOT NULL,

          -- 分类
          error_code          TEXT        NOT NULL,
          source_error_code   TEXT        DEFAULT NULL,
          error_message       TEXT        NOT NULL,

          -- 上下文
          failed_payload      JSONB       DEFAULT NULL,
          sanitized           BOOLEAN     NOT NULL DEFAULT FALSE,

          -- 状态机
          status              TEXT        NOT NULL DEFAULT 'pending',

          -- 时间
          first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
          retry_count         INTEGER     NOT NULL DEFAULT 0,

          -- 幂等
          idempotency_key     TEXT        DEFAULT NULL,

          created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

          PRIMARY KEY (org_id, project_id, dlq_id)
        );
    """)

    op.execute("""
        ALTER TABLE ecom_dlq
          ADD CONSTRAINT chk_dlq_status CHECK (
            status IN ('pending', 'retrying', 'resolved', 'permanent_failure', 'abandoned')
          ),
          ADD CONSTRAINT chk_dlq_error_code CHECK (
            error_code IN (
              'IDEMPOTENCY_CONFLICT',
              'DANGLING_LINK',
              'SOURCE_VERSION_CONFLICT',
              'SCHEMA_VALIDATION_ERROR',
              'SOURCE_READ_ERROR',
              'UNCLASSIFIED_EXCEPTION'
            )
          );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dlq_org_status
          ON ecom_dlq (org_id, project_id, status, last_seen_at DESC);
        CREATE INDEX IF NOT EXISTS idx_dlq_pipeline
          ON ecom_dlq (org_id, project_id, pipeline_id, status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_dlq_idem
          ON ecom_dlq (org_id, project_id, idempotency_key)
          WHERE idempotency_key IS NOT NULL;
    """)

    # RLS FORCE
    op.execute("""
        ALTER TABLE ecom_dlq ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ecom_dlq FORCE ROW LEVEL SECURITY;
    """)
    op.execute("""
        CREATE POLICY ecom_dlq_isolation ON ecom_dlq
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 3. ecom_dlq_retry_receipt
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS ecom_dlq_retry_receipt (
          org_id        TEXT        NOT NULL,
          project_id    TEXT        NOT NULL,
          dlq_id        TEXT        NOT NULL,
          retry_seq     INTEGER     NOT NULL,
          retry_event_id TEXT       NOT NULL,
          actor         TEXT        NOT NULL,
          attempted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          outcome       TEXT        NOT NULL,
          error_snapshot JSONB      DEFAULT NULL,

          PRIMARY KEY (org_id, project_id, dlq_id, retry_seq),
          FOREIGN KEY (org_id, project_id, dlq_id)
            REFERENCES ecom_dlq (org_id, project_id, dlq_id)
            ON DELETE CASCADE
        );
    """)

    op.execute("""
        ALTER TABLE ecom_dlq_retry_receipt
          ADD CONSTRAINT chk_retry_outcome CHECK (
            outcome IN ('success', 'failed', 'skipped')
          );
    """)

    op.execute("""
        ALTER TABLE ecom_dlq_retry_receipt ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ecom_dlq_retry_receipt FORCE ROW LEVEL SECURITY;
        CREATE POLICY ecom_dlq_rr_isolation ON ecom_dlq_retry_receipt
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 4. ecom_dlq_retry_event
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS ecom_dlq_retry_event (
          org_id         TEXT        NOT NULL,
          project_id     TEXT        NOT NULL,
          event_id       TEXT        NOT NULL,
          dlq_id         TEXT        NOT NULL,
          event_type     TEXT        NOT NULL,
          payload        JSONB       NOT NULL DEFAULT '{}'::jsonb,
          created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

          PRIMARY KEY (org_id, project_id, event_id)
        );
    """)

    op.execute("""
        ALTER TABLE ecom_dlq_retry_event
          ADD CONSTRAINT chk_event_type CHECK (
            event_type IN ('retry_requested', 'retry_succeeded', 'retry_failed', 'status_changed', 'abandoned')
          );
    """)

    op.execute("""
        ALTER TABLE ecom_dlq_retry_event ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ecom_dlq_retry_event FORCE ROW LEVEL SECURITY;
        CREATE POLICY ecom_dlq_re_isolation ON ecom_dlq_retry_event
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 5. ecom_derived_receipt
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS ecom_derived_receipt (
          org_id              TEXT        NOT NULL,
          project_id          TEXT        NOT NULL,
          workspace_id        TEXT        NOT NULL,
          receipt_id          TEXT        NOT NULL,
          object_type         TEXT        NOT NULL,
          external_id         TEXT        NOT NULL,
          calculator_version  TEXT        NOT NULL,
          idempotency_key     TEXT        NOT NULL,
          payload_hash        CHAR(64)    NOT NULL,
          derived_revision    INTEGER     NOT NULL,
          input_revision      BIGINT      NOT NULL,
          input_hash          CHAR(64)    NOT NULL,
          computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
          created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

          PRIMARY KEY (org_id, project_id, receipt_id),
          UNIQUE (org_id, project_id, object_type, external_id, idempotency_key)
        );
    """)

    op.execute("""
        ALTER TABLE ecom_derived_receipt ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ecom_derived_receipt FORCE ROW LEVEL SECURITY;
        CREATE POLICY ecom_derived_r_isolation ON ecom_derived_receipt
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 6. projection_outbox
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS projection_outbox (
          outbox_id        BIGSERIAL   NOT NULL,
          org_id           TEXT        NOT NULL,
          project_id       TEXT        NOT NULL,
          workspace_id     TEXT        NOT NULL,

          -- 权威写入的 revision (单调递增)
          input_revision   BIGINT      NOT NULL,

          -- 变化类型
          change_kind      TEXT        NOT NULL,

          -- 对象身份（object 或 link 的完整 identity）
          object_type      TEXT        DEFAULT NULL,
          external_id      TEXT        DEFAULT NULL,
          link_type        TEXT        DEFAULT NULL,
          source_external_id TEXT      DEFAULT NULL,
          target_external_id TEXT      DEFAULT NULL,

          -- 平台信息
          platform         TEXT        NOT NULL,
          shop_or_marketplace_id TEXT  NOT NULL,

          -- payload envelope v1
          payload          JSONB       NOT NULL,

          -- 投影状态
          projected        BOOLEAN     NOT NULL DEFAULT FALSE,
          projected_at     TIMESTAMPTZ DEFAULT NULL,
          projection_error TEXT        DEFAULT NULL,

          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

          PRIMARY KEY (outbox_id)
        );
    """)

    op.execute("""
        ALTER TABLE projection_outbox
          ADD CONSTRAINT chk_outbox_change_kind CHECK (
            change_kind IN (
              'objects_written',
              'objects_tombstoned',
              'links_written',
              'links_tombstoned',
              'derived_upsert',
              'derived_tombstoned'
            )
          ),
          ADD CONSTRAINT chk_outbox_not_both CHECK (
            NOT (object_type IS NULL AND link_type IS NULL)
          ),
          ADD CONSTRAINT chk_outbox_revision_pos CHECK (input_revision > 0);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_project_unprojected
          ON projection_outbox (org_id, project_id, workspace_id, input_revision ASC)
          WHERE projected = FALSE;
        CREATE INDEX IF NOT EXISTS idx_outbox_scope_prefix
          ON projection_outbox (org_id, project_id, workspace_id, change_kind, input_revision);
    """)

    op.execute("""
        ALTER TABLE projection_outbox ENABLE ROW LEVEL SECURITY;
        ALTER TABLE projection_outbox FORCE ROW LEVEL SECURITY;
        CREATE POLICY projection_outbox_isolation ON projection_outbox
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 7. projection_watermark
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS projection_watermark (
          org_id           TEXT        NOT NULL,
          project_id       TEXT        NOT NULL,
          workspace_id     TEXT        NOT NULL,
          projector_name   TEXT        NOT NULL,
          last_processed_revision BIGINT NOT NULL DEFAULT 0,
          last_processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

          PRIMARY KEY (org_id, project_id, workspace_id, projector_name)
        );
    """)

    op.execute("""
        ALTER TABLE projection_watermark
          ADD CONSTRAINT chk_watermark_nonneg CHECK (last_processed_revision >= 0);
    """)

    op.execute("""
        ALTER TABLE projection_watermark ENABLE ROW LEVEL SECURITY;
        ALTER TABLE projection_watermark FORCE ROW LEVEL SECURITY;
        CREATE POLICY projection_wm_isolation ON projection_watermark
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 8. ecom_alias_migration (sidecar 台账)
    # ═══════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS ecom_alias_migration (
          org_id           TEXT        NOT NULL,
          project_id       TEXT        NOT NULL,
          workspace_id     TEXT        NOT NULL,
          alias_entry_id   TEXT        NOT NULL,

          -- 旧复合主键
          old_pk           TEXT        NOT NULL,

          -- 目标 Canonical ID
          target_external_id TEXT      NOT NULL,
          target_object_type TEXT      NOT NULL,

          -- props hash
          props_hash       CHAR(64)    NOT NULL,

          -- 来源推断
          source_platform  TEXT        NOT NULL,
          source_shop_id   TEXT        NOT NULL,

          -- 冲突类别
          conflict_category TEXT       DEFAULT NULL,
          conflict_details  JSONB      DEFAULT NULL,

          -- 处置状态
          disposition      TEXT        NOT NULL DEFAULT 'pending',

          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

          PRIMARY KEY (org_id, project_id, alias_entry_id)
        );
    """)

    op.execute("""
        ALTER TABLE ecom_alias_migration
          ADD CONSTRAINT chk_alias_disposition CHECK (
            disposition IN ('pending', 'queued', 'copied', 'verified', 'conflict_isolated', 'cleaned', 'restored')
          );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alias_org_workspace
          ON ecom_alias_migration (org_id, project_id, workspace_id, disposition);
    """)

    op.execute("""
        ALTER TABLE ecom_alias_migration ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ecom_alias_migration FORCE ROW LEVEL SECURITY;
        CREATE POLICY ecom_alias_isolation ON ecom_alias_migration
          TO aos_runtime
          USING (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          )
          WITH CHECK (
            current_setting('aos.org_id', true) = org_id
            AND current_setting('aos.project_id', true) = project_id
          );
    """)

    # ═══════════════════════════════════════════════════════
    # 9. bundle_installation_revision.state CHECK 补 'uninstalled'
    # ═══════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE bundle_installation_revision
          DROP CONSTRAINT IF EXISTS bundle_installation_revision_state_check;
    """)

    op.execute("""
        ALTER TABLE bundle_installation_revision
          ADD CONSTRAINT bundle_installation_revision_state_check CHECK (
            state = ANY (ARRAY[
              'draft', 'submitted', 'approved', 'rejected',
              'applied', 'active', 'rolled_back', 'uninstalled'
            ])
          );
    """)


def downgrade() -> None:
    # Expand-only migration: downgrade 只在新表上 DROP
    op.execute("DROP TABLE IF EXISTS ecom_alias_migration CASCADE;")
    op.execute("DROP TABLE IF EXISTS projection_watermark CASCADE;")
    op.execute("DROP TABLE IF EXISTS projection_outbox CASCADE;")
    op.execute("DROP TABLE IF EXISTS ecom_derived_receipt CASCADE;")
    op.execute("DROP TABLE IF EXISTS ecom_dlq_retry_event CASCADE;")
    op.execute("DROP TABLE IF EXISTS ecom_dlq_retry_receipt CASCADE;")
    op.execute("DROP TABLE IF EXISTS ecom_dlq CASCADE;")

    # 派生列
    op.execute("""
        ALTER TABLE ecom_object
          DROP CONSTRAINT IF EXISTS chk_derived_revision_nonneg,
          DROP CONSTRAINT IF EXISTS chk_derived_input_revision_nonneg,
          DROP COLUMN IF EXISTS derived_revision,
          DROP COLUMN IF EXISTS derived_input_revision,
          DROP COLUMN IF EXISTS derived_input_hash,
          DROP COLUMN IF EXISTS derived_computed_at,
          DROP COLUMN IF EXISTS derived_payload;
    """)

    # 恢复 state CHECK（不含 uninstalled）
    op.execute("""
        ALTER TABLE bundle_installation_revision
          DROP CONSTRAINT IF EXISTS bundle_installation_revision_state_check;
        ALTER TABLE bundle_installation_revision
          ADD CONSTRAINT bundle_installation_revision_state_check CHECK (
            state = ANY (ARRAY[
              'draft', 'submitted', 'approved', 'rejected',
              'applied', 'active', 'rolled_back'
            ])
          );
    """)
