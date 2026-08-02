"""Add the canonical asset bundle registry.

Revision ID: a93c7e1b4f20
Revises: 228logicpublish
Create Date: 2026-08-03
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a93c7e1b4f20"
down_revision: str | Sequence[str] | None = "228logicpublish"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE asset_bundle (
          bundle_pk UUID PRIMARY KEY,
          publisher TEXT NOT NULL CHECK (btrim(publisher) <> ''),
          bundle_id TEXT NOT NULL
            CHECK (bundle_id ~ '^[a-z0-9][a-z0-9.-]*$'),
          kind TEXT NOT NULL CHECK (
            kind IN (
              'DomainPack',
              'SolutionPack',
              'VerticalPack',
              'PlatformAdapterPack',
              'PluginPack'
            )
          ),
          display_name TEXT NOT NULL CHECK (btrim(display_name) <> ''),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (publisher, bundle_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE asset_bundle_version (
          version_pk UUID PRIMARY KEY,
          bundle_pk UUID NOT NULL
            REFERENCES asset_bundle(bundle_pk) ON DELETE RESTRICT,
          version TEXT NOT NULL CHECK (
            version ~ '^[0-9]+[.][0-9]+[.][0-9]+(-[0-9A-Za-z.-]+)?([+][0-9A-Za-z.-]+)?$'
          ),
          manifest_json JSONB NOT NULL
            CHECK (jsonb_typeof(manifest_json) = 'object'),
          content_hash TEXT NOT NULL
            CHECK (content_hash ~ '^sha256:[0-9a-f]{64}$'),
          signature JSONB CHECK (
            signature IS NULL OR jsonb_typeof(signature) = 'object'
          ),
          status TEXT NOT NULL DEFAULT 'draft' CHECK (
            status IN (
              'draft', 'validated', 'published',
              'deprecated', 'revoked', 'rejected'
            )
          ),
          created_by TEXT NOT NULL CHECK (btrim(created_by) <> ''),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (bundle_pk, version),
          CHECK (
            status NOT IN ('published', 'deprecated', 'revoked')
            OR signature IS NOT NULL
          )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE asset_bundle_dependency (
          version_pk UUID NOT NULL
            REFERENCES asset_bundle_version(version_pk) ON DELETE CASCADE,
          dependency_publisher TEXT
            CHECK (
              dependency_publisher IS NULL
              OR btrim(dependency_publisher) <> ''
            ),
          dependency_id TEXT NOT NULL
            CHECK (dependency_id ~ '^[a-z0-9][a-z0-9.-]*$'),
          version_range TEXT NOT NULL CHECK (btrim(version_range) <> ''),
          optional BOOLEAN NOT NULL DEFAULT FALSE,
          ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
          PRIMARY KEY (version_pk, optional, ordinal)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE asset_bundle_artifact (
          version_pk UUID NOT NULL
            REFERENCES asset_bundle_version(version_pk) ON DELETE CASCADE,
          relative_path TEXT NOT NULL CHECK (
            btrim(relative_path) <> ''
            AND relative_path !~ '^/'
            AND relative_path !~ '(^|/)[.][.](/|$)'
            AND position(chr(92) IN relative_path) = 0
          ),
          artifact_ref TEXT NOT NULL CHECK (
            artifact_ref ~ '^bundle://'
            AND artifact_ref !~ '(^|/)[.][.](/|$)'
            AND position(chr(92) IN artifact_ref) = 0
          ),
          digest TEXT NOT NULL CHECK (digest ~ '^sha256:[0-9a-f]{64}$'),
          size BIGINT NOT NULL CHECK (size >= 0),
          media_type TEXT NOT NULL CHECK (btrim(media_type) <> ''),
          PRIMARY KEY (version_pk, relative_path)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE asset_bundle_evidence (
          version_pk UUID NOT NULL
            REFERENCES asset_bundle_version(version_pk) ON DELETE CASCADE,
          evidence_type TEXT NOT NULL CHECK (btrim(evidence_type) <> ''),
          artifact_ref TEXT NOT NULL CHECK (btrim(artifact_ref) <> ''),
          artifact_hash TEXT NOT NULL
            CHECK (artifact_hash ~ '^sha256:[0-9a-f]{64}$'),
          status TEXT NOT NULL DEFAULT 'pending' CHECK (
            status IN ('pending', 'valid', 'invalid', 'expired', 'revoked')
          ),
          observed_at TIMESTAMPTZ NOT NULL,
          expires_at TIMESTAMPTZ,
          revoked_at TIMESTAMPTZ,
          metadata JSONB NOT NULL DEFAULT '{}'::JSONB
            CHECK (jsonb_typeof(metadata) = 'object'),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_by TEXT NOT NULL CHECK (btrim(updated_by) <> ''),
          status_reason TEXT,
          PRIMARY KEY (version_pk, evidence_type, artifact_ref),
          CHECK (expires_at IS NULL OR expires_at > observed_at),
          CHECK (
            (status = 'revoked' AND revoked_at IS NOT NULL)
            OR (status <> 'revoked' AND revoked_at IS NULL)
          )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX idx_asset_bundle_catalog
          ON asset_bundle (kind, publisher, bundle_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_asset_bundle_version_catalog
          ON asset_bundle_version (status, created_at DESC, bundle_pk)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_asset_bundle_dependency_lookup
          ON asset_bundle_dependency (dependency_publisher, dependency_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_asset_bundle_artifact_ref
          ON asset_bundle_artifact (artifact_ref)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_asset_bundle_evidence_status
          ON asset_bundle_evidence (version_pk, status, evidence_type)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_asset_bundle_evidence_expiry
          ON asset_bundle_evidence (expires_at)
          WHERE expires_at IS NOT NULL AND status IN ('pending', 'valid')
        """
    )

    op.execute(
        """
        CREATE FUNCTION guard_asset_bundle_version_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'draft' THEN
              RAISE EXCEPTION
                'asset bundle versions must be created as draft'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;

          IF TG_OP = 'DELETE' THEN
            IF OLD.status IN ('published', 'deprecated', 'revoked') THEN
              RAISE EXCEPTION
                'published asset bundle versions cannot be deleted'
                USING ERRCODE = '23514';
            END IF;
            RETURN OLD;
          END IF;

          IF OLD.status = 'published' THEN
            IF NEW.status NOT IN ('deprecated', 'revoked')
               OR NEW.version_pk IS DISTINCT FROM OLD.version_pk
               OR NEW.bundle_pk IS DISTINCT FROM OLD.bundle_pk
               OR NEW.version IS DISTINCT FROM OLD.version
               OR NEW.manifest_json IS DISTINCT FROM OLD.manifest_json
               OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
               OR NEW.signature IS DISTINCT FROM OLD.signature
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
              RAISE EXCEPTION
                'published asset bundle version content is immutable'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;

          IF OLD.status IN ('deprecated', 'revoked', 'rejected') THEN
            RAISE EXCEPTION
              'terminal asset bundle versions are immutable'
              USING ERRCODE = '23514';
          END IF;

          IF NOT (
            (OLD.status = 'draft' AND NEW.status IN ('draft', 'validated', 'rejected'))
            OR (
              OLD.status = 'validated'
              AND NEW.status IN ('validated', 'published', 'rejected')
            )
          ) THEN
            RAISE EXCEPTION
              'invalid asset bundle version status transition: % -> %',
              OLD.status,
              NEW.status
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_bundle_version_guard
        BEFORE INSERT OR UPDATE OR DELETE ON asset_bundle_version
        FOR EACH ROW EXECUTE FUNCTION guard_asset_bundle_version_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_asset_bundle_identity_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM asset_bundle_version
             WHERE bundle_pk = OLD.bundle_pk
               AND status IN ('published', 'deprecated', 'revoked')
          ) THEN
            RAISE EXCEPTION
              'asset bundle identity with a published version is immutable'
              USING ERRCODE = '23514';
          END IF;
          RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_bundle_identity_guard
        BEFORE UPDATE OR DELETE ON asset_bundle
        FOR EACH ROW EXECUTE FUNCTION guard_asset_bundle_identity_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_asset_bundle_projection_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          old_version_pk UUID;
          new_version_pk UUID;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            old_version_pk := OLD.version_pk;
          END IF;
          IF TG_OP <> 'DELETE' THEN
            new_version_pk := NEW.version_pk;
          END IF;

          IF EXISTS (
            SELECT 1
              FROM asset_bundle_version
             WHERE version_pk IN (old_version_pk, new_version_pk)
               AND status IN ('published', 'deprecated', 'revoked')
          ) THEN
            RAISE EXCEPTION
              'published asset bundle projections are immutable'
              USING ERRCODE = '23514';
          END IF;
          RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    for table in ("asset_bundle_dependency", "asset_bundle_artifact"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_guard
            BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_asset_bundle_projection_mutation()
            """
        )

    op.execute(
        """
        CREATE FUNCTION guard_asset_bundle_evidence_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          old_version_pk UUID;
          new_version_pk UUID;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            old_version_pk := OLD.version_pk;
          END IF;
          IF TG_OP <> 'DELETE' THEN
            new_version_pk := NEW.version_pk;
          END IF;

          IF NOT EXISTS (
            SELECT 1
              FROM asset_bundle_version
             WHERE version_pk IN (old_version_pk, new_version_pk)
               AND status IN ('published', 'deprecated', 'revoked')
          ) THEN
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
          END IF;

          IF TG_OP <> 'UPDATE' THEN
            RAISE EXCEPTION
              'published asset bundle evidence cannot be inserted or deleted'
              USING ERRCODE = '23514';
          END IF;

          IF NEW.version_pk IS DISTINCT FROM OLD.version_pk
             OR NEW.evidence_type IS DISTINCT FROM OLD.evidence_type
             OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref
             OR NEW.artifact_hash IS DISTINCT FROM OLD.artifact_hash
             OR NEW.observed_at IS DISTINCT FROM OLD.observed_at
             OR NEW.metadata IS DISTINCT FROM OLD.metadata
             OR NOT (
               (OLD.status = 'pending' AND NEW.status IN (
                 'valid', 'invalid', 'expired', 'revoked'
               ))
               OR (OLD.status = 'valid' AND NEW.status IN ('expired', 'revoked'))
             ) THEN
            RAISE EXCEPTION
              'published asset bundle evidence identity is immutable'
              USING ERRCODE = '23514';
          END IF;

          IF NEW.updated_at <= OLD.updated_at
             OR btrim(NEW.updated_by) = ''
             OR NEW.status_reason IS NULL
             OR btrim(NEW.status_reason) = '' THEN
            RAISE EXCEPTION
              'evidence status changes require updated_at, actor, and reason'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_bundle_evidence_guard
        BEFORE INSERT OR UPDATE OR DELETE ON asset_bundle_evidence
        FOR EACH ROW EXECUTE FUNCTION guard_asset_bundle_evidence_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM asset_bundle LIMIT 1)
             OR EXISTS (SELECT 1 FROM asset_bundle_version LIMIT 1)
             OR EXISTS (SELECT 1 FROM asset_bundle_dependency LIMIT 1)
             OR EXISTS (SELECT 1 FROM asset_bundle_artifact LIMIT 1)
             OR EXISTS (SELECT 1 FROM asset_bundle_evidence LIMIT 1) THEN
            RAISE EXCEPTION
              'asset registry downgrade blocked: canonical tables are not empty'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute("DROP TABLE asset_bundle_evidence")
    op.execute("DROP TABLE asset_bundle_artifact")
    op.execute("DROP TABLE asset_bundle_dependency")
    op.execute("DROP TABLE asset_bundle_version")
    op.execute("DROP TABLE asset_bundle")
    op.execute("DROP FUNCTION guard_asset_bundle_evidence_mutation()")
    op.execute("DROP FUNCTION guard_asset_bundle_projection_mutation()")
    op.execute("DROP FUNCTION guard_asset_bundle_identity_mutation()")
    op.execute("DROP FUNCTION guard_asset_bundle_version_mutation()")
