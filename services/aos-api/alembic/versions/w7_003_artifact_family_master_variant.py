"""Close immutable Artifact family, Variant and selection contracts (W7-05).

Revision ID: w7_003
Revises: w7_002
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w7_003"
down_revision: str | Sequence[str] | None = "w7_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_artifact WHERE content_hash IS NULL) THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_HASH_BACKFILL_REQUIRED'
              USING ERRCODE='55000';
          END IF;
        END $$;

        ALTER TABLE aip_artifact
          ALTER COLUMN content_hash SET NOT NULL,
          ADD COLUMN family_id TEXT,
          ADD COLUMN family_revision BIGINT,
          ADD COLUMN family_role TEXT,
          ADD COLUMN profile TEXT,
          ADD COLUMN platform TEXT,
          ADD COLUMN rendition_spec JSONB,
          ADD COLUMN rendition_spec_hash CHAR(64),
          ADD COLUMN lineage_refs JSONB,
          ADD CONSTRAINT ck_artifact_hash_w7_003 CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_artifact_family_revision_w7_003
            CHECK (family_revision IS NULL OR family_revision>=1),
          ADD CONSTRAINT ck_artifact_family_role_w7_003
            CHECK (family_role IS NULL OR family_role IN
              ('family_manifest','preview','draft','master','variant')),
          ADD CONSTRAINT ck_artifact_family_shape_w7_003 CHECK (
            (family_role IS NULL AND family_id IS NULL AND family_revision IS NULL
              AND profile IS NULL AND platform IS NULL AND rendition_spec IS NULL
              AND rendition_spec_hash IS NULL AND lineage_refs IS NULL)
            OR
            (family_role IS NOT NULL AND family_id IS NOT NULL AND family_revision IS NOT NULL
              AND profile IS NOT NULL AND platform IS NOT NULL
              AND jsonb_typeof(rendition_spec)='object'
              AND rendition_spec_hash ~ '^[0-9a-f]{64}$'
              AND jsonb_typeof(lineage_refs)='array')
          ),
          ADD CONSTRAINT ck_artifact_family_manifest_type_w7_003 CHECK (
            family_role<>'family_manifest' OR artifact_type='artifact_family_manifest'
          );
        CREATE UNIQUE INDEX aip_artifact_family_revision_w7_003
          ON aip_artifact(org_id,project_id,family_id,family_revision)
          WHERE family_id IS NOT NULL;

        REVOKE UPDATE,DELETE,TRUNCATE ON aip_artifact FROM aos_runtime;
        CREATE TRIGGER trg_aip_artifact_append_only_w7_003
          BEFORE UPDATE OR DELETE ON aip_artifact
          FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
        CREATE TRIGGER trg_aip_artifact_truncate_guard_w7_003
          BEFORE TRUNCATE ON aip_artifact
          FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();

        CREATE TABLE aip_artifact_family_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, family_id TEXT NOT NULL,
          manifest_artifact_id TEXT NOT NULL, manifest_content_hash CHAR(64) NOT NULL,
          current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,family_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          CHECK(manifest_content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,manifest_artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id)
        );

        CREATE TABLE aip_artifact_family_selection_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, family_id TEXT NOT NULL,
          selection_key TEXT NOT NULL, revision BIGINT NOT NULL,
          expected_family_version BIGINT NOT NULL,
          selected_artifact_id TEXT NOT NULL, selected_content_hash CHAR(64) NOT NULL,
          candidate_refs JSONB NOT NULL, candidate_set_hash CHAR(64) NOT NULL,
          policy_ref JSONB NOT NULL, reason TEXT NOT NULL,
          decision_hash CHAR(64) NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,family_id,selection_key,revision),
          CHECK(revision>=1), CHECK(expected_family_version>=1),
          CHECK(selected_content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(candidate_set_hash ~ '^[0-9a-f]{64}$'),
          CHECK(decision_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(candidate_refs)='array' AND jsonb_array_length(candidate_refs)>1),
          CHECK(jsonb_typeof(policy_ref)='object'),
          FOREIGN KEY(org_id,project_id,family_id)
            REFERENCES aip_artifact_family_head(org_id,project_id,family_id),
          FOREIGN KEY(org_id,project_id,selected_artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id)
        );

        ALTER TABLE aip_artifact_family_head ENABLE ROW LEVEL SECURITY;
        ALTER TABLE aip_artifact_family_head FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope_aip_artifact_family_head_w7_003
          ON aip_artifact_family_head TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''));
        GRANT SELECT,INSERT,UPDATE ON aip_artifact_family_head TO aos_runtime;

        CREATE FUNCTION guard_aip_artifact_family_head_w7_003()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF ROW(NEW.org_id,NEW.project_id,NEW.family_id,NEW.manifest_artifact_id,
                 NEW.manifest_content_hash,NEW.created_by,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.org_id,OLD.project_id,OLD.family_id,OLD.manifest_artifact_id,
                 OLD.manifest_content_hash,OLD.created_by,OLD.created_at)
          THEN RAISE EXCEPTION 'AIP_ARTIFACT_FAMILY_HEAD_IMMUTABLE_FIELDS'; END IF;
          IF NEW.version<>OLD.version+1 OR NEW.current_revision NOT IN (
            OLD.current_revision, OLD.current_revision+1
          ) THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_FAMILY_HEAD_CAS_REQUIRED';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_aip_artifact_family_head_guard_w7_003
          BEFORE UPDATE ON aip_artifact_family_head
          FOR EACH ROW EXECUTE FUNCTION guard_aip_artifact_family_head_w7_003();
        CREATE TRIGGER trg_aip_artifact_family_head_delete_guard_w7_003
          BEFORE DELETE ON aip_artifact_family_head
          FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
        CREATE TRIGGER trg_aip_artifact_family_head_truncate_guard_w7_003
          BEFORE TRUNCATE ON aip_artifact_family_head
          FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();

        ALTER TABLE aip_artifact_family_selection_revision ENABLE ROW LEVEL SECURITY;
        ALTER TABLE aip_artifact_family_selection_revision FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope_aip_artifact_family_selection_w7_003
          ON aip_artifact_family_selection_revision TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''));
        GRANT SELECT,INSERT ON aip_artifact_family_selection_revision TO aos_runtime;
        CREATE TRIGGER trg_aip_artifact_family_selection_append_only_w7_003
          BEFORE UPDATE OR DELETE ON aip_artifact_family_selection_revision
          FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
        CREATE TRIGGER trg_aip_artifact_family_selection_truncate_guard_w7_003
          BEFORE TRUNCATE ON aip_artifact_family_selection_revision
          FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();

        CREATE UNIQUE INDEX aip_artifact_family_one_membership_w7_003
          ON aip_artifact_relation(org_id,project_id,from_artifact_id)
          WHERE relation_type='family_member';
        CREATE UNIQUE INDEX aip_artifact_family_one_master_w7_003
          ON aip_artifact_relation(org_id,project_id,from_artifact_id)
          WHERE relation_type='variant_of';
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_aip_artifact_relation_w2()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          source_row aip_artifact%ROWTYPE;
          target_row aip_artifact%ROWTYPE;
        BEGIN
          SELECT * INTO source_row FROM aip_artifact
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND artifact_id=NEW.from_artifact_id;
          SELECT * INTO target_row FROM aip_artifact
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND artifact_id=NEW.to_artifact_id;
          IF source_row.content_hash IS NULL OR target_row.content_hash IS NULL THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_HASH_MISSING';
          END IF;
          IF source_row.content_hash<>NEW.from_content_hash
             OR target_row.content_hash<>NEW.to_content_hash THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_HASH_DRIFTED';
          END IF;
          IF NEW.relation_type='family_member' AND NOT (
            source_row.family_id IS NOT NULL
            AND target_row.family_role='family_manifest'
            AND source_row.family_id=target_row.family_id
          ) THEN RAISE EXCEPTION 'AIP_ARTIFACT_FAMILY_MEMBERSHIP_INVALID'; END IF;
          IF NEW.relation_type='variant_of' AND NOT (
            source_row.family_role='variant' AND target_row.family_role='master'
            AND source_row.family_id=target_row.family_id
            AND source_row.artifact_type=target_row.artifact_type
            AND source_row.profile=target_row.profile
            AND source_row.platform=target_row.platform
            AND source_row.rendition_spec_hash=target_row.rendition_spec_hash
          ) THEN RAISE EXCEPTION 'AIP_ARTIFACT_VARIANT_MASTER_INVALID'; END IF;
          IF NEW.relation_type='supersedes' AND NOT (
            source_row.family_id IS NOT NULL
            AND source_row.family_id=target_row.family_id
            AND source_row.family_role=target_row.family_role
            AND source_row.artifact_type=target_row.artifact_type
            AND source_row.profile=target_row.profile
            AND source_row.platform=target_row.platform
            AND source_row.rendition_spec_hash=target_row.rendition_spec_hash
          ) THEN RAISE EXCEPTION 'AIP_ARTIFACT_SUPERSEDES_INCOMPATIBLE'; END IF;
          IF EXISTS (
            WITH RECURSIVE reachable(artifact_id) AS (
              SELECT NEW.to_artifact_id
              UNION
              SELECT relation.to_artifact_id
              FROM aip_artifact_relation relation
              JOIN reachable path ON relation.from_artifact_id=path.artifact_id
              WHERE relation.org_id=NEW.org_id AND relation.project_id=NEW.project_id
            ) SELECT 1 FROM reachable WHERE artifact_id=NEW.from_artifact_id
          ) THEN RAISE EXCEPTION 'AIP_ARTIFACT_RELATION_CYCLE'; END IF;
          RETURN NEW;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_artifact_family_selection_revision LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_artifact_family_head LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade w7_003 with Artifact family authority data'
            USING ERRCODE='55000'; END IF;
        END $$;
        DROP INDEX aip_artifact_family_one_master_w7_003;
        DROP INDEX aip_artifact_family_one_membership_w7_003;
        DROP TABLE aip_artifact_family_selection_revision CASCADE;
        DROP TRIGGER trg_aip_artifact_family_head_guard_w7_003 ON aip_artifact_family_head;
        DROP FUNCTION guard_aip_artifact_family_head_w7_003();
        DROP TABLE aip_artifact_family_head CASCADE;
        DROP TRIGGER trg_aip_artifact_truncate_guard_w7_003 ON aip_artifact;
        DROP TRIGGER trg_aip_artifact_append_only_w7_003 ON aip_artifact;
        DROP INDEX aip_artifact_family_revision_w7_003;
        ALTER TABLE aip_artifact
          DROP CONSTRAINT ck_artifact_family_manifest_type_w7_003,
          DROP CONSTRAINT ck_artifact_family_shape_w7_003,
          DROP CONSTRAINT ck_artifact_family_role_w7_003,
          DROP CONSTRAINT ck_artifact_family_revision_w7_003,
          DROP CONSTRAINT ck_artifact_hash_w7_003,
          DROP COLUMN lineage_refs, DROP COLUMN rendition_spec_hash,
          DROP COLUMN rendition_spec, DROP COLUMN platform, DROP COLUMN profile,
          DROP COLUMN family_role, DROP COLUMN family_revision, DROP COLUMN family_id,
          ALTER COLUMN content_hash DROP NOT NULL;
        GRANT UPDATE,DELETE ON aip_artifact TO aos_runtime;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_aip_artifact_relation_w2()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          source_hash TEXT;
          target_hash TEXT;
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
            ) SELECT 1 FROM reachable WHERE artifact_id=NEW.from_artifact_id
          ) THEN
            RAISE EXCEPTION 'AIP_ARTIFACT_RELATION_CYCLE';
          END IF;
          RETURN NEW;
        END $$
        """
    )
