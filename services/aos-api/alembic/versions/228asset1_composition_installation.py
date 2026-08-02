"""Add immutable bundle composition and installation control-plane storage.

Revision ID: 228assetinstall
Revises: 228assetevidence
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228assetinstall"
down_revision: str | Sequence[str] | None = "228assetevidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE_TABLES = (
    "bundle_composition",
    "bundle_composition_lock",
    "bundle_installation_revision",
    "bundle_installation_decision",
    "bundle_installation_event",
    "bundle_installation_command",
)


def _create_tables() -> None:
    op.execute(
        """
        CREATE TABLE bundle_composition (
          org_id TEXT NOT NULL CHECK (
            org_id = btrim(org_id) AND char_length(org_id) BETWEEN 1 AND 160
          ),
          project_id TEXT NOT NULL CHECK (
            project_id = btrim(project_id)
            AND char_length(project_id) BETWEEN 1 AND 160
          ),
          composition_pk UUID NOT NULL,
          composition_id UUID NOT NULL,
          request_json JSONB NOT NULL
            CHECK (jsonb_typeof(request_json) = 'object'),
          request_hash TEXT NOT NULL
            CHECK (request_hash ~ '^sha256:[0-9a-f]{64}$'),
          registry_snapshot_json JSONB NOT NULL
            CHECK (jsonb_typeof(registry_snapshot_json) = 'object'),
          registry_snapshot_hash TEXT NOT NULL
            CHECK (registry_snapshot_hash ~ '^sha256:[0-9a-f]{64}$'),
          current_installation_ref_json JSONB CHECK (
            current_installation_ref_json IS NULL
            OR jsonb_typeof(current_installation_ref_json) = 'object'
          ),
          current_installation_ref_hash TEXT CHECK (
            current_installation_ref_hash IS NULL
            OR current_installation_ref_hash ~ '^sha256:[0-9a-f]{64}$'
          ),
          resolver_version TEXT NOT NULL CHECK (
            resolver_version = btrim(resolver_version)
            AND char_length(resolver_version) BETWEEN 1 AND 160
          ),
          created_by TEXT NOT NULL CHECK (
            created_by = btrim(created_by)
            AND char_length(created_by) BETWEEN 1 AND 240
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, composition_pk),
          UNIQUE (org_id, project_id, composition_id),
          CHECK (
            (current_installation_ref_json IS NULL)
            = (current_installation_ref_hash IS NULL)
          )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_bundle_composition_equivalent_input
          ON bundle_composition (
            org_id,
            project_id,
            request_hash,
            registry_snapshot_hash,
            resolver_version,
            COALESCE(current_installation_ref_hash, '')
          )
        """
    )
    op.execute(
        """
        CREATE TABLE bundle_composition_lock (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          composition_pk UUID NOT NULL,
          revision BIGINT NOT NULL CHECK (revision >= 1),
          lock_payload JSONB NOT NULL
            CHECK (jsonb_typeof(lock_payload) = 'object'),
          lock_hash TEXT NOT NULL
            CHECK (lock_hash ~ '^sha256:[0-9a-f]{64}$'),
          permission_diff_json JSONB NOT NULL
            CHECK (jsonb_typeof(permission_diff_json) = 'object'),
          permission_diff_hash TEXT NOT NULL
            CHECK (permission_diff_hash ~ '^sha256:[0-9a-f]{64}$'),
          migration_plan_json JSONB NOT NULL
            CHECK (jsonb_typeof(migration_plan_json) = 'object'),
          migration_plan_hash TEXT NOT NULL
            CHECK (migration_plan_hash ~ '^sha256:[0-9a-f]{64}$'),
          contribution_diff_json JSONB NOT NULL
            CHECK (jsonb_typeof(contribution_diff_json) = 'object'),
          contribution_diff_hash TEXT NOT NULL
            CHECK (contribution_diff_hash ~ '^sha256:[0-9a-f]{64}$'),
          created_by TEXT NOT NULL CHECK (
            created_by = btrim(created_by)
            AND char_length(created_by) BETWEEN 1 AND 240
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, composition_pk, revision),
          UNIQUE (org_id, project_id, composition_pk, lock_hash),
          CONSTRAINT fk_bundle_composition_lock_composition
            FOREIGN KEY (org_id, project_id, composition_pk)
            REFERENCES bundle_composition(org_id, project_id, composition_pk)
            ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bundle_installation (
          org_id TEXT NOT NULL CHECK (
            org_id = btrim(org_id) AND char_length(org_id) BETWEEN 1 AND 160
          ),
          project_id TEXT NOT NULL CHECK (
            project_id = btrim(project_id)
            AND char_length(project_id) BETWEEN 1 AND 160
          ),
          installation_pk UUID NOT NULL,
          installation_id UUID NOT NULL,
          display_name TEXT NOT NULL CHECK (
            display_name = btrim(display_name)
            AND char_length(display_name) BETWEEN 1 AND 240
          ),
          current_revision BIGINT NOT NULL CHECK (current_revision >= 1),
          active_revision BIGINT CHECK (active_revision >= 1),
          previous_active_revision BIGINT CHECK (previous_active_revision >= 1),
          etag_version BIGINT NOT NULL CHECK (etag_version >= 1),
          created_by TEXT NOT NULL CHECK (
            created_by = btrim(created_by)
            AND char_length(created_by) BETWEEN 1 AND 240
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, installation_pk),
          UNIQUE (org_id, project_id, installation_id),
          CHECK (updated_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bundle_installation_revision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          installation_pk UUID NOT NULL,
          revision BIGINT NOT NULL CHECK (revision >= 1),
          parent_revision BIGINT,
          state TEXT NOT NULL CHECK (
            state IN (
              'draft', 'submitted', 'approved', 'rejected',
              'applied', 'active', 'rolled_back'
            )
          ),
          composition_pk UUID NOT NULL,
          lock_revision BIGINT NOT NULL CHECK (lock_revision >= 1),
          lock_hash TEXT NOT NULL
            CHECK (lock_hash ~ '^sha256:[0-9a-f]{64}$'),
          permission_diff_hash TEXT NOT NULL
            CHECK (permission_diff_hash ~ '^sha256:[0-9a-f]{64}$'),
          migration_plan_hash TEXT NOT NULL
            CHECK (migration_plan_hash ~ '^sha256:[0-9a-f]{64}$'),
          contribution_diff_hash TEXT NOT NULL
            CHECK (contribution_diff_hash ~ '^sha256:[0-9a-f]{64}$'),
          overlay_revision TEXT NOT NULL CHECK (
            overlay_revision = btrim(overlay_revision)
            AND char_length(overlay_revision) BETWEEN 1 AND 160
          ),
          requested_by TEXT NOT NULL CHECK (
            requested_by = btrim(requested_by)
            AND char_length(requested_by) BETWEEN 1 AND 240
          ),
          decision_id UUID,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, installation_pk, revision),
          CONSTRAINT fk_bundle_installation_revision_installation
            FOREIGN KEY (org_id, project_id, installation_pk)
            REFERENCES bundle_installation(org_id, project_id, installation_pk)
            ON DELETE RESTRICT,
          CONSTRAINT fk_bundle_installation_revision_parent
            FOREIGN KEY (
              org_id, project_id, installation_pk, parent_revision
            )
            REFERENCES bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_bundle_installation_revision_lock
            FOREIGN KEY (
              org_id, project_id, composition_pk, lock_revision
            )
            REFERENCES bundle_composition_lock(
              org_id, project_id, composition_pk, revision
            )
            ON DELETE RESTRICT,
          CHECK (
            (revision = 1 AND parent_revision IS NULL)
            OR (revision > 1 AND parent_revision = revision - 1)
          )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bundle_installation_decision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          decision_id UUID NOT NULL,
          installation_pk UUID NOT NULL,
          submitted_revision BIGINT NOT NULL CHECK (submitted_revision >= 1),
          decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
          actor TEXT NOT NULL CHECK (
            actor = btrim(actor) AND char_length(actor) BETWEEN 1 AND 240
          ),
          lock_hash TEXT NOT NULL
            CHECK (lock_hash ~ '^sha256:[0-9a-f]{64}$'),
          permission_diff_hash TEXT NOT NULL
            CHECK (permission_diff_hash ~ '^sha256:[0-9a-f]{64}$'),
          migration_plan_hash TEXT NOT NULL
            CHECK (migration_plan_hash ~ '^sha256:[0-9a-f]{64}$'),
          contribution_diff_hash TEXT NOT NULL
            CHECK (contribution_diff_hash ~ '^sha256:[0-9a-f]{64}$'),
          reason TEXT CHECK (
            reason IS NULL
            OR (
              reason = btrim(reason) AND char_length(reason) BETWEEN 1 AND 2000
            )
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, decision_id),
          UNIQUE (org_id, project_id, installation_pk, submitted_revision),
          CONSTRAINT fk_bundle_installation_decision_installation
            FOREIGN KEY (org_id, project_id, installation_pk)
            REFERENCES bundle_installation(org_id, project_id, installation_pk)
            ON DELETE RESTRICT,
          CONSTRAINT fk_bundle_installation_decision_submitted_revision
            FOREIGN KEY (
              org_id, project_id, installation_pk, submitted_revision
            )
            REFERENCES bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT,
          CHECK (decision <> 'rejected' OR reason IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE bundle_installation_revision
          ADD CONSTRAINT fk_bundle_installation_revision_decision
          FOREIGN KEY (org_id, project_id, decision_id)
          REFERENCES bundle_installation_decision(
            org_id, project_id, decision_id
          )
          ON DELETE RESTRICT
          DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        CREATE TABLE bundle_installation_event (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          installation_pk UUID NOT NULL,
          sequence BIGINT NOT NULL CHECK (sequence >= 1),
          from_revision BIGINT,
          to_revision BIGINT NOT NULL CHECK (to_revision >= 1),
          from_state TEXT CHECK (
            from_state IS NULL OR from_state IN (
              'draft', 'submitted', 'approved', 'rejected',
              'applied', 'active', 'rolled_back'
            )
          ),
          to_state TEXT NOT NULL CHECK (
            to_state IN (
              'draft', 'submitted', 'approved', 'rejected',
              'applied', 'active', 'rolled_back'
            )
          ),
          actor TEXT NOT NULL CHECK (
            actor = btrim(actor) AND char_length(actor) BETWEEN 1 AND 240
          ),
          reason TEXT CHECK (
            reason IS NULL
            OR (
              reason = btrim(reason) AND char_length(reason) BETWEEN 1 AND 2000
            )
          ),
          evidence_json JSONB CHECK (
            evidence_json IS NULL OR jsonb_typeof(evidence_json) = 'object'
          ),
          evidence_hash TEXT CHECK (
            evidence_hash IS NULL
            OR evidence_hash ~ '^sha256:[0-9a-f]{64}$'
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, installation_pk, sequence),
          CONSTRAINT fk_bundle_installation_event_installation
            FOREIGN KEY (org_id, project_id, installation_pk)
            REFERENCES bundle_installation(org_id, project_id, installation_pk)
            ON DELETE RESTRICT,
          CONSTRAINT fk_bundle_installation_event_from_revision
            FOREIGN KEY (
              org_id, project_id, installation_pk, from_revision
            )
            REFERENCES bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT,
          CONSTRAINT fk_bundle_installation_event_to_revision
            FOREIGN KEY (
              org_id, project_id, installation_pk, to_revision
            )
            REFERENCES bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT,
          CHECK ((evidence_json IS NULL) = (evidence_hash IS NULL)),
          CHECK ((from_revision IS NULL) = (from_state IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bundle_installation_command (
          org_id TEXT NOT NULL CHECK (
            org_id = btrim(org_id) AND char_length(org_id) BETWEEN 1 AND 160
          ),
          project_id TEXT NOT NULL CHECK (
            project_id = btrim(project_id)
            AND char_length(project_id) BETWEEN 1 AND 160
          ),
          operation TEXT NOT NULL CHECK (
            operation = btrim(operation)
            AND char_length(operation) BETWEEN 1 AND 160
          ),
          idempotency_key TEXT NOT NULL CHECK (
            idempotency_key = btrim(idempotency_key)
            AND char_length(idempotency_key) BETWEEN 1 AND 160
            AND idempotency_key !~ '[[:cntrl:]]'
          ),
          subject TEXT NOT NULL CHECK (
            subject = btrim(subject) AND char_length(subject) BETWEEN 1 AND 240
          ),
          request_hash TEXT NOT NULL
            CHECK (request_hash ~ '^sha256:[0-9a-f]{64}$'),
          status_code SMALLINT NOT NULL CHECK (status_code BETWEEN 200 AND 299),
          response_json JSONB NOT NULL
            CHECK (jsonb_typeof(response_json) = 'object'),
          response_etag TEXT CHECK (
            response_etag IS NULL OR response_etag ~ '^"[1-9][0-9]*"$'
          ),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, operation, idempotency_key)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE bundle_installation
          ADD CONSTRAINT fk_bundle_installation_current_revision
          FOREIGN KEY (
            org_id, project_id, installation_pk, current_revision
          )
          REFERENCES bundle_installation_revision(
            org_id, project_id, installation_pk, revision
          )
          ON DELETE RESTRICT
          DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        ALTER TABLE bundle_installation
          ADD CONSTRAINT fk_bundle_installation_active_revision
          FOREIGN KEY (
            org_id, project_id, installation_pk, active_revision
          )
          REFERENCES bundle_installation_revision(
            org_id, project_id, installation_pk, revision
          )
          ON DELETE RESTRICT
          DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        ALTER TABLE bundle_installation
          ADD CONSTRAINT fk_bundle_installation_previous_active_revision
          FOREIGN KEY (
            org_id, project_id, installation_pk, previous_active_revision
          )
          REFERENCES bundle_installation_revision(
            org_id, project_id, installation_pk, revision
          )
          ON DELETE RESTRICT
          DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        CREATE INDEX idx_bundle_installation_list
          ON bundle_installation (org_id, project_id, created_at DESC, installation_id)
        """
    )


def _create_hash_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION canonical_bundle_control_sha256(input_value JSONB)
        RETURNS TEXT
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT 'sha256:' || encode(
            public.digest(
              convert_to(canonical_asset_registry_jsonb(input_value), 'UTF8'),
              'sha256'
            ),
            'hex'
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_bundle_composition_lock_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.lock_payload -> 'permissionDiff'
               IS DISTINCT FROM NEW.permission_diff_json
             OR NEW.lock_payload -> 'migrationPlan'
               IS DISTINCT FROM NEW.migration_plan_json
             OR NEW.lock_payload -> 'contributionDiff'
               IS DISTINCT FROM NEW.contribution_diff_json THEN
            RAISE EXCEPTION
              'composition lock payload does not embed its canonical diffs'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.lock_hash IS DISTINCT FROM
               canonical_bundle_control_sha256(NEW.lock_payload)
             OR NEW.permission_diff_hash IS DISTINCT FROM
               canonical_bundle_control_sha256(NEW.permission_diff_json)
             OR NEW.migration_plan_hash IS DISTINCT FROM
               canonical_bundle_control_sha256(NEW.migration_plan_json)
             OR NEW.contribution_diff_hash IS DISTINCT FROM
               canonical_bundle_control_sha256(NEW.contribution_diff_json) THEN
            RAISE EXCEPTION
              'composition lock or diff hash is invalid'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bundle_composition_lock_hash_guard
        BEFORE INSERT ON bundle_composition_lock
        FOR EACH ROW EXECUTE FUNCTION guard_bundle_composition_lock_insert()
        """
    )


def _create_immutability_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_bundle_control_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION
            'canonical bundle control-plane rows are immutable'
            USING ERRCODE = '23514';
        END;
        $$
        """
    )
    for table in _IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_bundle_control_immutable()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_bundle_control_immutable()
            """
        )


def _create_revision_and_decision_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_bundle_installation_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          parent_row bundle_installation_revision%ROWTYPE;
          lock_row bundle_composition_lock%ROWTYPE;
        BEGIN
          SELECT * INTO lock_row
            FROM bundle_composition_lock
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND composition_pk = NEW.composition_pk
             AND revision = NEW.lock_revision;
          IF NOT FOUND
             OR NEW.lock_hash IS DISTINCT FROM lock_row.lock_hash
             OR NEW.permission_diff_hash IS DISTINCT FROM lock_row.permission_diff_hash
             OR NEW.migration_plan_hash IS DISTINCT FROM lock_row.migration_plan_hash
             OR NEW.contribution_diff_hash IS DISTINCT FROM lock_row.contribution_diff_hash THEN
            RAISE EXCEPTION
              'installation revision does not match its canonical lock'
              USING ERRCODE = '23514';
          END IF;

          IF NEW.revision = 1 THEN
            IF NEW.state <> 'draft' OR NEW.parent_revision IS NOT NULL
               OR NEW.decision_id IS NOT NULL THEN
              RAISE EXCEPTION
                'installation revision 1 must be an undecided draft'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;

          SELECT * INTO parent_row
            FROM bundle_installation_revision
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND installation_pk = NEW.installation_pk
             AND revision = NEW.parent_revision;
          IF NOT FOUND THEN
            RAISE EXCEPTION
              'installation revision parent is missing'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.composition_pk IS DISTINCT FROM parent_row.composition_pk
             OR NEW.lock_revision IS DISTINCT FROM parent_row.lock_revision
             OR NEW.lock_hash IS DISTINCT FROM parent_row.lock_hash
             OR NEW.permission_diff_hash IS DISTINCT FROM parent_row.permission_diff_hash
             OR NEW.migration_plan_hash IS DISTINCT FROM parent_row.migration_plan_hash
             OR NEW.contribution_diff_hash IS DISTINCT FROM parent_row.contribution_diff_hash
             OR NEW.overlay_revision IS DISTINCT FROM parent_row.overlay_revision
             OR NEW.requested_by IS DISTINCT FROM parent_row.requested_by THEN
            RAISE EXCEPTION
              'installation revision changed its immutable plan'
              USING ERRCODE = '23514';
          END IF;
          IF NOT (
            (parent_row.state = 'draft' AND NEW.state = 'submitted')
            OR (
              parent_row.state = 'submitted'
              AND NEW.state IN ('approved', 'rejected')
            )
            OR (parent_row.state = 'approved' AND NEW.state = 'applied')
            OR (parent_row.state = 'applied' AND NEW.state = 'active')
            OR (parent_row.state = 'active' AND NEW.state = 'rolled_back')
          ) THEN
            RAISE EXCEPTION
              'invalid immutable installation revision transition'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.state IN ('approved', 'rejected') THEN
            IF NEW.decision_id IS NULL THEN
              RAISE EXCEPTION
                'installation decision state requires decision id'
                USING ERRCODE = '23514';
            END IF;
          ELSIF NEW.state IN ('applied', 'active', 'rolled_back') THEN
            IF NEW.decision_id IS NULL
               OR NEW.decision_id IS DISTINCT FROM parent_row.decision_id THEN
              RAISE EXCEPTION
                'approved decision id must be inherited by descendants'
                USING ERRCODE = '23514';
            END IF;
          ELSE
            IF NEW.decision_id IS NOT NULL THEN
              RAISE EXCEPTION
                'pre-decision installation revision cannot have decision id'
                USING ERRCODE = '23514';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bundle_installation_revision_insert_guard
        BEFORE INSERT ON bundle_installation_revision
        FOR EACH ROW EXECUTE FUNCTION guard_bundle_installation_revision_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_bundle_installation_decision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          submitted_row bundle_installation_revision%ROWTYPE;
        BEGIN
          SELECT * INTO submitted_row
            FROM bundle_installation_revision
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND installation_pk = NEW.installation_pk
             AND revision = NEW.submitted_revision;
          IF NOT FOUND OR submitted_row.state <> 'submitted' THEN
            RAISE EXCEPTION
              'installation decision must target a submitted revision'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.actor = submitted_row.requested_by THEN
            RAISE EXCEPTION
              'installation requester cannot decide its own revision'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.lock_hash IS DISTINCT FROM submitted_row.lock_hash
             OR NEW.permission_diff_hash IS DISTINCT FROM
                  submitted_row.permission_diff_hash
             OR NEW.migration_plan_hash IS DISTINCT FROM
                  submitted_row.migration_plan_hash
             OR NEW.contribution_diff_hash IS DISTINCT FROM
                  submitted_row.contribution_diff_hash THEN
            RAISE EXCEPTION
              'installation decision hashes are stale'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bundle_installation_decision_insert_guard
        BEFORE INSERT ON bundle_installation_decision
        FOR EACH ROW EXECUTE FUNCTION guard_bundle_installation_decision_insert()
        """
    )


def _create_event_and_pointer_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_bundle_installation_event_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          previous_event bundle_installation_event%ROWTYPE;
          target_state TEXT;
        BEGIN
          PERFORM 1
            FROM bundle_installation
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND installation_pk = NEW.installation_pk
           FOR UPDATE;
          IF NOT FOUND THEN
            RAISE EXCEPTION
              'installation event parent is missing'
              USING ERRCODE = '23514';
          END IF;
          SELECT * INTO previous_event
            FROM bundle_installation_event
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND installation_pk = NEW.installation_pk
           ORDER BY sequence DESC
           LIMIT 1;
          IF NOT FOUND THEN
            IF NEW.sequence <> 1 OR NEW.from_revision IS NOT NULL
               OR NEW.from_state IS NOT NULL OR NEW.to_revision <> 1 THEN
              RAISE EXCEPTION
                'first installation event must create revision 1'
                USING ERRCODE = '23514';
            END IF;
          ELSE
            IF NEW.sequence <> previous_event.sequence + 1
               OR NEW.from_revision IS DISTINCT FROM previous_event.to_revision
               OR NEW.from_state IS DISTINCT FROM previous_event.to_state
               OR NEW.to_revision <> previous_event.to_revision + 1 THEN
              RAISE EXCEPTION
                'installation event does not extend the event tail'
                USING ERRCODE = '23514';
            END IF;
          END IF;
          SELECT state INTO target_state
            FROM bundle_installation_revision
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND installation_pk = NEW.installation_pk
             AND revision = NEW.to_revision;
          IF target_state IS NULL OR NEW.to_state IS DISTINCT FROM target_state THEN
            RAISE EXCEPTION
              'installation event state does not match target revision'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.evidence_json IS NOT NULL
             AND NEW.evidence_hash IS DISTINCT FROM
                  canonical_bundle_control_sha256(NEW.evidence_json) THEN
            RAISE EXCEPTION
              'installation event evidence hash is invalid'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bundle_installation_event_insert_guard
        BEFORE INSERT ON bundle_installation_event
        FOR EACH ROW EXECUTE FUNCTION guard_bundle_installation_event_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_bundle_installation_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'TRUNCATE' THEN
            RAISE EXCEPTION
              'bundle installations cannot be truncated'
              USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION
              'bundle installations cannot be deleted'
              USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'INSERT' THEN
            IF NEW.current_revision <> 1 OR NEW.etag_version <> 1
               OR NEW.active_revision IS NOT NULL
               OR NEW.previous_active_revision IS NOT NULL THEN
              RAISE EXCEPTION
                'new installation must start at draft revision and etag 1'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;
          IF NEW.org_id IS DISTINCT FROM OLD.org_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.installation_pk IS DISTINCT FROM OLD.installation_pk
             OR NEW.installation_id IS DISTINCT FROM OLD.installation_id
             OR NEW.display_name IS DISTINCT FROM OLD.display_name
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION
              'installation identity is immutable'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.current_revision <> OLD.current_revision + 1
             OR NEW.etag_version <> OLD.etag_version + 1
             OR NEW.updated_at <= OLD.updated_at THEN
            RAISE EXCEPTION
              'installation transition must advance revision, etag, and time once'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bundle_installation_mutation_guard
        BEFORE INSERT OR UPDATE OR DELETE ON bundle_installation
        FOR EACH ROW EXECUTE FUNCTION guard_bundle_installation_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bundle_installation_truncate_guard
        BEFORE TRUNCATE ON bundle_installation
        FOR EACH STATEMENT EXECUTE FUNCTION guard_bundle_installation_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION assert_bundle_installation_consistency(
          target_org TEXT,
          target_project TEXT,
          target_installation UUID
        )
        RETURNS VOID
        LANGUAGE plpgsql
        AS $$
        DECLARE
          installation_row bundle_installation%ROWTYPE;
          current_state TEXT;
          active_state TEXT;
          previous_state TEXT;
          maximum_revision BIGINT;
          maximum_sequence BIGINT;
          tail_revision BIGINT;
          tail_state TEXT;
        BEGIN
          SELECT * INTO installation_row
            FROM bundle_installation
           WHERE org_id = target_org
             AND project_id = target_project
             AND installation_pk = target_installation;
          IF NOT FOUND THEN
            RAISE EXCEPTION
              'installation consistency parent is missing'
              USING ERRCODE = '23514';
          END IF;
          SELECT state INTO current_state
            FROM bundle_installation_revision
           WHERE org_id = target_org
             AND project_id = target_project
             AND installation_pk = target_installation
             AND revision = installation_row.current_revision;
          SELECT MAX(revision) INTO maximum_revision
            FROM bundle_installation_revision
           WHERE org_id = target_org
             AND project_id = target_project
             AND installation_pk = target_installation;
          SELECT sequence, to_revision, to_state
            INTO maximum_sequence, tail_revision, tail_state
            FROM bundle_installation_event
           WHERE org_id = target_org
             AND project_id = target_project
             AND installation_pk = target_installation
           ORDER BY sequence DESC
           LIMIT 1;
          IF current_state IS NULL
             OR maximum_revision IS DISTINCT FROM installation_row.current_revision
             OR maximum_sequence IS DISTINCT FROM installation_row.current_revision
             OR tail_revision IS DISTINCT FROM installation_row.current_revision
             OR tail_state IS DISTINCT FROM current_state
             OR installation_row.etag_version IS DISTINCT FROM
                  installation_row.current_revision THEN
            RAISE EXCEPTION
              'installation pointer, event tail, revision, and etag disagree'
              USING ERRCODE = '23514';
          END IF;

          IF installation_row.active_revision IS NOT NULL THEN
            SELECT state INTO active_state
              FROM bundle_installation_revision
             WHERE org_id = target_org
               AND project_id = target_project
               AND installation_pk = target_installation
               AND revision = installation_row.active_revision;
            IF active_state <> 'active' THEN
              RAISE EXCEPTION
                'installation active pointer does not reference active revision'
                USING ERRCODE = '23514';
            END IF;
          END IF;
          IF installation_row.previous_active_revision IS NOT NULL THEN
            SELECT state INTO previous_state
              FROM bundle_installation_revision
             WHERE org_id = target_org
               AND project_id = target_project
               AND installation_pk = target_installation
               AND revision = installation_row.previous_active_revision;
            IF previous_state <> 'active' THEN
              RAISE EXCEPTION
                'installation previous pointer does not reference active revision'
                USING ERRCODE = '23514';
            END IF;
          END IF;

          IF current_state = 'active' THEN
            IF installation_row.active_revision IS DISTINCT FROM
                 installation_row.current_revision
               OR (
                 installation_row.previous_active_revision IS NOT NULL
                 AND installation_row.previous_active_revision >=
                     installation_row.current_revision
               ) THEN
              RAISE EXCEPTION
                'active installation pointers do not describe valid history'
                USING ERRCODE = '23514';
            END IF;
          ELSIF current_state = 'rolled_back' THEN
            IF installation_row.active_revision IS DISTINCT FROM
                 installation_row.previous_active_revision
               OR installation_row.active_revision IS NOT DISTINCT FROM
                    installation_row.current_revision
               OR installation_row.previous_active_revision IS NOT DISTINCT FROM
                    installation_row.current_revision THEN
              RAISE EXCEPTION
                'rolled back installation pointers do not restore valid history'
                USING ERRCODE = '23514';
            END IF;
          ELSIF installation_row.active_revision IS NOT NULL
                OR installation_row.previous_active_revision IS NOT NULL THEN
            RAISE EXCEPTION
              'pre-active installation cannot expose active pointers'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION ensure_bundle_installation_row_consistency()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          PERFORM assert_bundle_installation_consistency(
            NEW.org_id, NEW.project_id, NEW.installation_pk
          );
          RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_bundle_installation_consistency
        AFTER INSERT OR UPDATE ON bundle_installation
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ensure_bundle_installation_row_consistency()
        """
    )
    op.execute(
        """
        CREATE FUNCTION ensure_bundle_installation_child_consistency()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          PERFORM assert_bundle_installation_consistency(
            NEW.org_id, NEW.project_id, NEW.installation_pk
          );
          RETURN NULL;
        END;
        $$
        """
    )
    for table in ("bundle_installation_revision", "bundle_installation_event"):
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER trg_{table}_installation_consistency
            AFTER INSERT ON {table}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW
            EXECUTE FUNCTION ensure_bundle_installation_child_consistency()
            """
        )
    op.execute(
        """
        CREATE FUNCTION ensure_bundle_installation_revision_decision()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          decision_row bundle_installation_decision%ROWTYPE;
        BEGIN
          IF NEW.state IN ('draft', 'submitted') THEN
            IF NEW.decision_id IS NOT NULL THEN
              RAISE EXCEPTION
                'pre-decision revision cannot reference a decision'
                USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
          END IF;
          SELECT * INTO decision_row
            FROM bundle_installation_decision
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND decision_id = NEW.decision_id;
          IF NOT FOUND
             OR decision_row.installation_pk IS DISTINCT FROM NEW.installation_pk
             OR decision_row.lock_hash IS DISTINCT FROM NEW.lock_hash
             OR decision_row.permission_diff_hash IS DISTINCT FROM
                  NEW.permission_diff_hash
             OR decision_row.migration_plan_hash IS DISTINCT FROM
                  NEW.migration_plan_hash
             OR decision_row.contribution_diff_hash IS DISTINCT FROM
                  NEW.contribution_diff_hash
             OR (
               NEW.state = 'rejected' AND decision_row.decision <> 'rejected'
             )
             OR (
               NEW.state IN ('approved', 'applied', 'active', 'rolled_back')
               AND decision_row.decision <> 'approved'
             ) THEN
            RAISE EXCEPTION
              'installation revision decision lineage is invalid'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.state IN ('approved', 'rejected')
             AND decision_row.submitted_revision IS DISTINCT FROM
                  NEW.parent_revision THEN
            RAISE EXCEPTION
              'installation decision is not bound to submitted parent'
              USING ERRCODE = '23514';
          END IF;
          RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_bundle_installation_revision_decision
        AFTER INSERT ON bundle_installation_revision
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION ensure_bundle_installation_revision_decision()
        """
    )
    op.execute(
        """
        CREATE FUNCTION ensure_bundle_installation_decision_child()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          child_state TEXT;
          child_decision UUID;
        BEGIN
          SELECT state, decision_id INTO child_state, child_decision
            FROM bundle_installation_revision
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND installation_pk = NEW.installation_pk
             AND revision = NEW.submitted_revision + 1;
          IF child_decision IS DISTINCT FROM NEW.decision_id
             OR (NEW.decision = 'approved' AND child_state <> 'approved')
             OR (NEW.decision = 'rejected' AND child_state <> 'rejected') THEN
            RAISE EXCEPTION
              'installation decision does not have its immutable child revision'
              USING ERRCODE = '23514';
          END IF;
          RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_bundle_installation_decision_child
        AFTER INSERT ON bundle_installation_decision
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ensure_bundle_installation_decision_child()
        """
    )


def upgrade() -> None:
    _create_tables()
    _create_hash_guards()
    _create_immutability_guards()
    _create_revision_and_decision_guards()
    _create_event_and_pointer_guards()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM bundle_composition_lock LIMIT 1)
             OR EXISTS (SELECT 1 FROM bundle_installation LIMIT 1)
             OR EXISTS (SELECT 1 FROM bundle_installation_command LIMIT 1) THEN
            RAISE EXCEPTION
              'bundle control-plane downgrade blocked: canonical data exists'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        "ALTER TABLE bundle_installation "
        "DROP CONSTRAINT fk_bundle_installation_previous_active_revision"
    )
    op.execute(
        "ALTER TABLE bundle_installation "
        "DROP CONSTRAINT fk_bundle_installation_active_revision"
    )
    op.execute(
        "ALTER TABLE bundle_installation "
        "DROP CONSTRAINT fk_bundle_installation_current_revision"
    )
    op.execute(
        "ALTER TABLE bundle_installation_revision "
        "DROP CONSTRAINT fk_bundle_installation_revision_decision"
    )
    op.execute("DROP TABLE bundle_installation_command")
    op.execute("DROP TABLE bundle_installation_event")
    op.execute("DROP TABLE bundle_installation_decision")
    op.execute("DROP TABLE bundle_installation_revision")
    op.execute("DROP TABLE bundle_installation")
    op.execute("DROP TABLE bundle_composition_lock")
    op.execute("DROP TABLE bundle_composition")
    op.execute("DROP FUNCTION ensure_bundle_installation_decision_child()")
    op.execute("DROP FUNCTION ensure_bundle_installation_revision_decision()")
    op.execute("DROP FUNCTION ensure_bundle_installation_child_consistency()")
    op.execute("DROP FUNCTION ensure_bundle_installation_row_consistency()")
    op.execute("DROP FUNCTION assert_bundle_installation_consistency(TEXT, TEXT, UUID)")
    op.execute("DROP FUNCTION guard_bundle_installation_mutation()")
    op.execute("DROP FUNCTION guard_bundle_installation_event_insert()")
    op.execute("DROP FUNCTION guard_bundle_installation_decision_insert()")
    op.execute("DROP FUNCTION guard_bundle_installation_revision_insert()")
    op.execute("DROP FUNCTION guard_bundle_control_immutable()")
    op.execute("DROP FUNCTION guard_bundle_composition_lock_insert()")
    op.execute("DROP FUNCTION canonical_bundle_control_sha256(JSONB)")
