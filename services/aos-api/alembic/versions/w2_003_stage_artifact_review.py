"""Add W2-C stage template, artifact relation and review return authority.

Revision ID: w2_003
Revises: aip7_002
Create Date: 2026-08-14
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w2_003"
down_revision: str | Sequence[str] | None = "aip7_002"
branch_labels = None
depends_on = None

TABLES = (
    "aip_stage_template_head",
    "aip_stage_template_revision",
    "aip_artifact_relation",
    "aip_review_issue",
    "aip_review_issue_event",
    "aip_return_decision",
)


def _tenant_table(name: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w2 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    grant = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")


def _append_only(name: str) -> None:
    op.execute(
        f"""CREATE TRIGGER trg_{name}_append_only
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{name}_truncate_guard
        BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_stage_template_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, template_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,template_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          FOREIGN KEY(org_id,project_id) REFERENCES twa_workspace(org_id,project_id))"""
    )
    op.execute(
        """CREATE TABLE aip_stage_template_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, template_id TEXT NOT NULL,
          revision BIGINT NOT NULL, profile TEXT NOT NULL, source_bundle_ref JSONB NOT NULL,
          stages JSONB NOT NULL, content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL,
          sealed_by TEXT, sealed_at TIMESTAMPTZ, seal_hash TEXT, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,template_id,revision),
          CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(lifecycle IN ('draft','frozen','withdrawn','superseded')),
          CHECK(jsonb_typeof(source_bundle_ref)='object'),
          CHECK(jsonb_typeof(stages)='array' AND jsonb_array_length(stages)>0),
          CHECK((lifecycle='frozen' AND sealed_by IS NOT NULL AND sealed_at IS NOT NULL
                 AND seal_hash ~ '^[0-9a-f]{64}$')
             OR (lifecycle<>'frozen' AND sealed_by IS NULL AND sealed_at IS NULL AND seal_hash IS NULL)),
          FOREIGN KEY(org_id,project_id,template_id)
            REFERENCES aip_stage_template_head(org_id,project_id,template_id)
            DEFERRABLE INITIALLY DEFERRED)"""
    )
    op.execute(
        """CREATE TABLE aip_artifact_relation (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, relation_id TEXT NOT NULL,
          relation_type TEXT NOT NULL, from_artifact_id TEXT NOT NULL,
          from_content_hash TEXT NOT NULL, to_artifact_id TEXT NOT NULL,
          to_content_hash TEXT NOT NULL, reason TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,relation_id),
          UNIQUE(org_id,project_id,relation_type,from_artifact_id,to_artifact_id),
          CHECK(relation_type IN ('family_member','variant_of','supersedes','derived_from')),
          CHECK(from_artifact_id<>to_artifact_id),
          CHECK(from_content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(to_content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,from_artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id),
          FOREIGN KEY(org_id,project_id,to_artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id))"""
    )
    op.execute(
        """CREATE FUNCTION validate_aip_artifact_relation_w2()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source_hash TEXT; target_hash TEXT;
        BEGIN
          SELECT content_hash INTO source_hash FROM aip_artifact
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND artifact_id=NEW.from_artifact_id;
          SELECT content_hash INTO target_hash FROM aip_artifact
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND artifact_id=NEW.to_artifact_id;
          IF source_hash IS NULL OR target_hash IS NULL THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_HASH_MISSING';
          END IF;
          IF source_hash<>NEW.from_content_hash OR target_hash<>NEW.to_content_hash THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_HASH_DRIFTED';
          END IF;
          IF EXISTS (
            WITH RECURSIVE reachable(artifact_id) AS (
              SELECT NEW.to_artifact_id
              UNION
              SELECT relation.to_artifact_id
              FROM aip_artifact_relation relation
              JOIN reachable path ON relation.from_artifact_id=path.artifact_id
              WHERE relation.org_id=NEW.org_id AND relation.project_id=NEW.project_id
            )
            SELECT 1 FROM reachable WHERE artifact_id=NEW.from_artifact_id
          ) THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_RELATION_CYCLE';
          END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_artifact_relation_validate
        BEFORE INSERT ON aip_artifact_relation
        FOR EACH ROW EXECUTE FUNCTION validate_aip_artifact_relation_w2()"""
    )
    op.execute(
        """CREATE TABLE aip_review_issue (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, issue_id TEXT NOT NULL,
          rule_ref JSONB NOT NULL, severity TEXT NOT NULL,
          artifact_id TEXT NOT NULL, artifact_hash TEXT NOT NULL,
          eval_report_id TEXT NOT NULL, eval_report_revision BIGINT NOT NULL,
          eval_report_hash TEXT NOT NULL, location JSONB NOT NULL,
          evidence_refs JSONB NOT NULL, suggested_fix TEXT NOT NULL,
          return_stage TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
          version BIGINT NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_by TEXT NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,issue_id),
          CHECK(severity IN ('info','warning','error','critical')),
          CHECK(status IN ('open','resolved','returned','superseded')),
          CHECK(version>=1), CHECK(artifact_hash ~ '^[0-9a-f]{64}$'),
          CHECK(eval_report_revision>=1), CHECK(eval_report_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(rule_ref)='object'), CHECK(jsonb_typeof(location)='object'),
          CHECK(jsonb_typeof(evidence_refs)='array'),
          FOREIGN KEY(org_id,project_id,artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id),
          FOREIGN KEY(org_id,project_id,eval_report_id,eval_report_revision)
            REFERENCES aip_eval_report_revision(org_id,project_id,report_id,revision))"""
    )
    op.execute(
        """CREATE FUNCTION guard_aip_review_issue_update_w2()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.issue_id,NEW.rule_ref,NEW.severity,
                 NEW.artifact_id,NEW.artifact_hash,NEW.eval_report_id,
                 NEW.eval_report_revision,NEW.eval_report_hash,NEW.location,
                 NEW.evidence_refs,NEW.suggested_fix,NEW.return_stage,NEW.created_by,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.issue_id,OLD.rule_ref,OLD.severity,
                 OLD.artifact_id,OLD.artifact_hash,OLD.eval_report_id,
                 OLD.eval_report_revision,OLD.eval_report_hash,OLD.location,
                 OLD.evidence_refs,OLD.suggested_fix,OLD.return_stage,OLD.created_by,OLD.created_at)
          THEN RAISE EXCEPTION 'AIP_REVIEW_ISSUE_IMMUTABLE_FIELDS'; END IF;
          IF OLD.status<>'open' OR NEW.status NOT IN ('resolved','returned','superseded')
             OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'AIP_REVIEW_ISSUE_INVALID_TRANSITION';
          END IF;
          RETURN NEW;
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_review_issue_update_guard
        BEFORE UPDATE ON aip_review_issue
        FOR EACH ROW EXECUTE FUNCTION guard_aip_review_issue_update_w2()"""
    )
    op.execute(
        """CREATE TABLE aip_review_issue_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          issue_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          issue_version BIGINT NOT NULL, payload_hash TEXT NOT NULL,
          actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,issue_id,sequence),
          CHECK(sequence>=1), CHECK(issue_version>=1),
          CHECK(event_type IN ('opened','resolved','returned','superseded')),
          CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,issue_id)
            REFERENCES aip_review_issue(org_id,project_id,issue_id))"""
    )
    op.execute(
        """CREATE TABLE aip_return_decision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          issue_id TEXT NOT NULL, issue_version BIGINT NOT NULL, run_id TEXT NOT NULL,
          step_key TEXT NOT NULL, step_run_id TEXT NOT NULL, attempt INTEGER NOT NULL,
          attempt_idempotency_key TEXT NOT NULL, reason TEXT NOT NULL,
          decision_hash TEXT NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id),
          UNIQUE(org_id,project_id,issue_id,issue_version),
          UNIQUE(org_id,project_id,attempt_idempotency_key),
          CHECK(issue_version>=1), CHECK(attempt>=1),
          CHECK(decision_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,issue_id)
            REFERENCES aip_review_issue(org_id,project_id,issue_id),
          FOREIGN KEY(org_id,project_id,run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY(org_id,project_id,step_run_id)
            REFERENCES aip_step_run(org_id,project_id,step_run_id))"""
    )

    for table in TABLES:
        _tenant_table(
            table,
            mutable=table in {"aip_stage_template_head", "aip_review_issue"},
        )
    for table in (
        "aip_stage_template_revision",
        "aip_artifact_relation",
        "aip_review_issue_event",
        "aip_return_decision",
    ):
        _append_only(table)

    op.execute(
        "CREATE INDEX aip_stage_template_updated_idx ON "
        "aip_stage_template_head(org_id,project_id,updated_at DESC,template_id)"
    )
    op.execute(
        "CREATE INDEX aip_artifact_relation_from_idx ON "
        "aip_artifact_relation(org_id,project_id,from_artifact_id,created_at)"
    )
    op.execute(
        "CREATE INDEX aip_artifact_relation_to_idx ON "
        "aip_artifact_relation(org_id,project_id,to_artifact_id,created_at)"
    )
    op.execute(
        "CREATE INDEX aip_review_issue_status_idx ON "
        "aip_review_issue(org_id,project_id,status,updated_at DESC,issue_id)"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip_review_issue_update_w2() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS validate_aip_artifact_relation_w2() CASCADE")
