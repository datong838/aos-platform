"""Receipt-first ecommerce capability and three-bucket budget authority."""

from alembic import op


revision = "ar2_003"
down_revision = "ar2_002"
branch_labels = None
depends_on = None


_TABLES = (
    "aip_capability_invocation",
    "aip_capability_provider_request_receipt",
    "aip_capability_provider_receipt",
    "aip_budget_bucket",
    "aip_budget_reservation",
    "aip_budget_reservation_bucket",
    "aip_budget_usage_settlement",
    "aip_budget_reservation_event",
)


def _tenant_scope(table: str, *, update: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_ar2_003 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
    op.execute(f"GRANT SELECT,INSERT{',UPDATE' if update else ''} ON {table} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_capability_invocation (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          invocation_id UUID NOT NULL, operation_id TEXT NOT NULL,
          invocation_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
          task_ref JSONB NOT NULL, policy_ref JSONB NOT NULL,
          approval_ref JSONB NOT NULL, pricing_ref JSONB NOT NULL,
          currency TEXT NOT NULL CHECK(currency='CNY'),
          upper_bound_minor BIGINT NOT NULL CHECK(upper_bound_minor>0),
          state TEXT NOT NULL CHECK(state IN ('prepared','submitted','completed','failed','unknown')),
          revision BIGINT NOT NULL DEFAULT 1 CHECK(revision>0),
          content_hash TEXT NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,invocation_id),
          UNIQUE(org_id,project_id,operation_id,invocation_key),
          CHECK(length(operation_id) BETWEEN 1 AND 160),
          CHECK(length(invocation_key) BETWEEN 1 AND 200),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(task_ref)='object' AND jsonb_typeof(policy_ref)='object'
            AND jsonb_typeof(approval_ref)='object' AND jsonb_typeof(pricing_ref)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_capability_provider_request_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          request_receipt_id UUID NOT NULL, invocation_id UUID NOT NULL,
          request_hash CHAR(64) NOT NULL, provider_ref JSONB NOT NULL,
          provider_idempotency_hash CHAR(64) NOT NULL,
          revision BIGINT NOT NULL DEFAULT 1 CHECK(revision=1),
          content_hash TEXT NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          submitted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,request_receipt_id),
          UNIQUE(org_id,project_id,invocation_id),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(provider_idempotency_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(provider_ref)='object'),
          FOREIGN KEY(org_id,project_id,invocation_id)
            REFERENCES aip_capability_invocation(org_id,project_id,invocation_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_capability_provider_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          provider_receipt_id UUID NOT NULL, invocation_id UUID NOT NULL,
          request_receipt_id UUID NOT NULL,
          outcome TEXT NOT NULL CHECK(outcome IN ('completed','failed_no_effect','unknown')),
          provider_result_hash CHAR(64) NOT NULL,
          evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          revision BIGINT NOT NULL DEFAULT 1 CHECK(revision=1),
          content_hash TEXT NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          observed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,provider_receipt_id),
          UNIQUE(org_id,project_id,invocation_id,provider_result_hash),
          CHECK(provider_result_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(evidence_refs)='array'),
          FOREIGN KEY(org_id,project_id,invocation_id)
            REFERENCES aip_capability_invocation(org_id,project_id,invocation_id),
          FOREIGN KEY(org_id,project_id,request_receipt_id)
            REFERENCES aip_capability_provider_request_receipt(org_id,project_id,request_receipt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_budget_bucket (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          bucket_kind TEXT NOT NULL CHECK(bucket_kind IN ('task','daily','pilot')),
          account_id TEXT NOT NULL, period_start TIMESTAMPTZ NOT NULL,
          period_end TIMESTAMPTZ NOT NULL, currency TEXT NOT NULL CHECK(currency='CNY'),
          limit_minor BIGINT NOT NULL CHECK(limit_minor>0),
          held_minor BIGINT NOT NULL DEFAULT 0 CHECK(held_minor>=0),
          submitted_minor BIGINT NOT NULL DEFAULT 0 CHECK(submitted_minor>=0),
          settled_minor BIGINT NOT NULL DEFAULT 0 CHECK(settled_minor>=0),
          unknown_minor BIGINT NOT NULL DEFAULT 0 CHECK(unknown_minor>=0),
          version BIGINT NOT NULL DEFAULT 1 CHECK(version>0),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,bucket_kind,account_id,period_start,currency),
          CHECK(length(account_id) BETWEEN 1 AND 200),
          CHECK(period_end>period_start),
          CHECK(held_minor+submitted_minor+settled_minor+unknown_minor<=limit_minor)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_budget_reservation (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          reservation_id UUID NOT NULL, invocation_id UUID NOT NULL,
          operation_id TEXT NOT NULL, invocation_key TEXT NOT NULL,
          task_ref JSONB NOT NULL, policy_ref JSONB NOT NULL,
          pricing_ref JSONB NOT NULL, approval_ref JSONB NOT NULL,
          currency TEXT NOT NULL CHECK(currency='CNY'),
          upper_bound_minor BIGINT NOT NULL CHECK(upper_bound_minor>0),
          actual_minor BIGINT CHECK(actual_minor>=0 AND actual_minor<=upper_bound_minor),
          state TEXT NOT NULL CHECK(state IN ('held','submitted','settled','released','unknown')),
          provider_request_receipt_ref JSONB, provider_receipt_ref JSONB,
          usage_receipt_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          reconciliation_evidence_ref JSONB,
          request_hash CHAR(64) NOT NULL,
          revision BIGINT NOT NULL DEFAULT 1 CHECK(revision>0),
          content_hash TEXT NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,reservation_id),
          UNIQUE(org_id,project_id,operation_id,invocation_key),
          UNIQUE(org_id,project_id,invocation_id),
          CHECK(length(operation_id) BETWEEN 1 AND 160),
          CHECK(length(invocation_key) BETWEEN 1 AND 200),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(task_ref)='object' AND jsonb_typeof(policy_ref)='object'
            AND jsonb_typeof(pricing_ref)='object' AND jsonb_typeof(approval_ref)='object'),
          CHECK(jsonb_typeof(usage_receipt_refs)='array'),
          CHECK(provider_request_receipt_ref IS NULL OR jsonb_typeof(provider_request_receipt_ref)='object'),
          CHECK(provider_receipt_ref IS NULL OR jsonb_typeof(provider_receipt_ref)='object'),
          CHECK(reconciliation_evidence_ref IS NULL OR jsonb_typeof(reconciliation_evidence_ref)='object'),
          FOREIGN KEY(org_id,project_id,invocation_id)
            REFERENCES aip_capability_invocation(org_id,project_id,invocation_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_budget_reservation_bucket (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          reservation_id UUID NOT NULL,
          bucket_kind TEXT NOT NULL CHECK(bucket_kind IN ('task','daily','pilot')),
          account_id TEXT NOT NULL, period_start TIMESTAMPTZ NOT NULL,
          currency TEXT NOT NULL CHECK(currency='CNY'),
          reserved_minor BIGINT NOT NULL CHECK(reserved_minor>0),
          PRIMARY KEY(org_id,project_id,reservation_id,bucket_kind),
          UNIQUE(org_id,project_id,reservation_id,account_id,period_start,currency),
          FOREIGN KEY(org_id,project_id,reservation_id)
            REFERENCES aip_budget_reservation(org_id,project_id,reservation_id),
          FOREIGN KEY(org_id,project_id,bucket_kind,account_id,period_start,currency)
            REFERENCES aip_budget_bucket(org_id,project_id,bucket_kind,account_id,period_start,currency)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_budget_reservation_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_id UUID NOT NULL, reservation_id UUID NOT NULL,
          sequence BIGINT NOT NULL CHECK(sequence>0),
          from_state TEXT, to_state TEXT NOT NULL,
          actor TEXT NOT NULL, evidence_ref JSONB,
          event_hash TEXT NOT NULL CHECK(event_hash ~ '^sha256:[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,reservation_id,sequence),
          CHECK(length(actor) BETWEEN 1 AND 200),
          CHECK(to_state IN ('held','submitted','settled','released','unknown')),
          CHECK(from_state IS NULL OR from_state IN ('held','submitted','settled','released','unknown')),
          CHECK(evidence_ref IS NULL OR jsonb_typeof(evidence_ref)='object'),
          FOREIGN KEY(org_id,project_id,reservation_id)
            REFERENCES aip_budget_reservation(org_id,project_id,reservation_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_budget_usage_settlement (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          usage_receipt_id TEXT NOT NULL, reservation_id UUID NOT NULL,
          usage_receipt_ref JSONB NOT NULL, actual_minor BIGINT NOT NULL CHECK(actual_minor>=0),
          created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(org_id,project_id,usage_receipt_id),
          CHECK(jsonb_typeof(usage_receipt_ref)='object'),
          FOREIGN KEY(org_id,project_id,reservation_id)
            REFERENCES aip_budget_reservation(org_id,project_id,reservation_id)
        )"""
    )
    op.execute(
        """CREATE FUNCTION guard_ar2_capability_invocation_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.invocation_id,NEW.operation_id,
                 NEW.invocation_key,NEW.request_hash,NEW.task_ref,NEW.policy_ref,NEW.approval_ref,
                 NEW.pricing_ref,NEW.currency,NEW.upper_bound_minor,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.invocation_id,OLD.operation_id,
                 OLD.invocation_key,OLD.request_hash,OLD.task_ref,OLD.policy_ref,OLD.approval_ref,
                 OLD.pricing_ref,OLD.currency,OLD.upper_bound_minor,OLD.created_at)
          THEN RAISE EXCEPTION 'capability invocation identity is immutable'; END IF;
          IF NEW.revision<>OLD.revision+1 OR NEW.content_hash=OLD.content_hash
             OR NEW.updated_at<OLD.updated_at OR NOT (
               (OLD.state='prepared' AND NEW.state IN ('submitted','failed')) OR
               (OLD.state='submitted' AND NEW.state IN ('completed','failed','unknown')) OR
               (OLD.state='unknown' AND NEW.state IN ('completed','failed')))
          THEN RAISE EXCEPTION 'invalid capability invocation transition'; END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_ar2_capability_invocation_update
        BEFORE UPDATE ON aip_capability_invocation FOR EACH ROW
        EXECUTE FUNCTION guard_ar2_capability_invocation_update()"""
    )
    op.execute(
        """CREATE FUNCTION guard_ar2_budget_reservation_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.reservation_id,NEW.invocation_id,
                 NEW.operation_id,NEW.invocation_key,NEW.task_ref,NEW.policy_ref,
                 NEW.pricing_ref,NEW.approval_ref,NEW.currency,NEW.upper_bound_minor,
                 NEW.request_hash,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.reservation_id,OLD.invocation_id,
                 OLD.operation_id,OLD.invocation_key,OLD.task_ref,OLD.policy_ref,
                 OLD.pricing_ref,OLD.approval_ref,OLD.currency,OLD.upper_bound_minor,
                 OLD.request_hash,OLD.created_at)
          THEN RAISE EXCEPTION 'budget reservation identity is immutable'; END IF;
          IF NEW.revision<>OLD.revision+1 OR NEW.content_hash=OLD.content_hash
             OR NEW.updated_at<OLD.updated_at OR NOT (
               (OLD.state='held' AND NEW.state IN ('submitted','released')) OR
               (OLD.state='submitted' AND NEW.state IN ('settled','released','unknown')) OR
               (OLD.state='unknown' AND NEW.state IN ('settled','released')))
          THEN RAISE EXCEPTION 'invalid budget reservation transition'; END IF;
          IF NOT (
            (NEW.state='submitted' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NULL AND jsonb_array_length(NEW.usage_receipt_refs)=0
              AND NEW.actual_minor IS NULL AND NEW.reconciliation_evidence_ref IS NULL) OR
            (NEW.state='unknown' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NULL AND jsonb_array_length(NEW.usage_receipt_refs)=0
              AND NEW.actual_minor IS NULL AND NEW.reconciliation_evidence_ref IS NULL) OR
            (NEW.state='settled' AND NEW.provider_request_receipt_ref IS NOT NULL
              AND NEW.provider_receipt_ref IS NOT NULL AND jsonb_array_length(NEW.usage_receipt_refs)>0
              AND NEW.actual_minor IS NOT NULL) OR
            (NEW.state='released' AND NEW.provider_receipt_ref IS NULL
              AND jsonb_array_length(NEW.usage_receipt_refs)=0 AND NEW.actual_minor IS NULL
              AND ((NEW.provider_request_receipt_ref IS NULL AND NEW.reconciliation_evidence_ref IS NULL)
                OR (NEW.provider_request_receipt_ref IS NOT NULL
                  AND NEW.reconciliation_evidence_ref IS NOT NULL))))
          THEN RAISE EXCEPTION 'budget reservation state shape drifted'; END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_ar2_budget_reservation_update
        BEFORE UPDATE ON aip_budget_reservation FOR EACH ROW
        EXECUTE FUNCTION guard_ar2_budget_reservation_update()"""
    )
    op.execute(
        """CREATE FUNCTION guard_ar2_budget_bucket_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.bucket_kind,NEW.account_id,
                 NEW.period_start,NEW.period_end,NEW.currency,NEW.limit_minor)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.bucket_kind,OLD.account_id,
                 OLD.period_start,OLD.period_end,OLD.currency,OLD.limit_minor)
             OR NEW.version<>OLD.version+1 OR NEW.updated_at<OLD.updated_at
          THEN RAISE EXCEPTION 'budget bucket authority drifted'; END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_ar2_budget_bucket_update
        BEFORE UPDATE ON aip_budget_bucket FOR EACH ROW
        EXECUTE FUNCTION guard_ar2_budget_bucket_update()"""
    )
    for table in _TABLES:
        _tenant_scope(
            table,
            update=table in {
                "aip_capability_invocation",
                "aip_budget_bucket",
                "aip_budget_reservation",
            },
        )


def downgrade() -> None:
    predicates = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in _TABLES)
    op.execute(
        f"""DO $$ BEGIN
          IF {predicates} THEN
            RAISE EXCEPTION 'AR2_003_DOWNGRADE_REQUIRES_EMPTY_CAPABILITY_BUDGET_AUTHORITY'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION guard_ar2_budget_bucket_update()")
    op.execute("DROP FUNCTION guard_ar2_budget_reservation_update()")
    op.execute("DROP FUNCTION guard_ar2_capability_invocation_update()")
