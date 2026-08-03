"""Add immutable Integration Case, Evidence, and projection storage.

Revision ID: 228assetintegration
Revises: 228assetinstall
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228assetintegration"
down_revision: str | Sequence[str] | None = "228assetinstall"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAGES = (
    "planned",
    "connection_verified",
    "data_verified",
    "ontology_verified",
    "logic_verified",
    "workshop_verified",
    "production_ready",
    "production_active",
)
_EVIDENCE_TYPES = (
    "source_connection",
    "tenant_isolation",
    "pipeline_run",
    "dataset_revision",
    "data_quality",
    "ontology_revision",
    "mapping_validation",
    "logic_publication",
    "logic_eval",
    "workshop_validation",
    "action_safety",
    "operations_readiness",
    "security_validation",
    "runtime_health",
)
_HISTORY_TABLES = (
    "integration_case",
    "integration_instance_revision",
    "integration_evidence",
    "integration_evidence_snapshot",
    "integration_stage_event",
    "integration_case_command",
)
_ALL_TABLES = (
    "integration_case",
    "integration_instance",
    "integration_instance_revision",
    "integration_evidence",
    "integration_evidence_snapshot",
    "integration_stage_event",
    "integration_case_projection",
    "integration_case_command",
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_tables() -> None:
    op.execute(
        """
        CREATE TABLE integration_case (
          org_id TEXT NOT NULL CHECK (
            org_id = btrim(org_id) AND char_length(org_id) BETWEEN 1 AND 160
          ),
          project_id TEXT NOT NULL CHECK (
            project_id = btrim(project_id)
            AND char_length(project_id) BETWEEN 1 AND 160
          ),
          case_pk UUID NOT NULL,
          case_id UUID NOT NULL,
          scope TEXT NOT NULL CHECK (scope IN ('current', 'reference')),
          display_name TEXT NOT NULL CHECK (
            display_name = btrim(display_name)
            AND char_length(display_name) BETWEEN 1 AND 240
            AND display_name !~ '[[:cntrl:]]'
          ),
          owner TEXT CHECK (
            owner IS NULL OR (
              owner = btrim(owner)
              AND char_length(owner) BETWEEN 1 AND 1024
              AND owner !~ '[[:cntrl:]]'
              AND owner !~* '[A-Z0-9._%+-]+@[A-Z0-9.-]+[.][A-Z]{2,}'
            )
          ),
          required_markings JSONB NOT NULL DEFAULT '[]'::JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, case_pk),
          UNIQUE (org_id, project_id, case_id),
          CHECK (
            (scope = 'current' AND owner IS NOT NULL)
            OR (scope = 'reference' AND owner IS NULL)
          ),
          CHECK (updated_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE integration_instance (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          instance_pk UUID NOT NULL,
          case_pk UUID NOT NULL,
          current_revision BIGINT NOT NULL CHECK (current_revision >= 1),
          etag_version BIGINT NOT NULL CHECK (etag_version >= 1),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, instance_pk),
          UNIQUE (org_id, project_id, case_pk),
          CONSTRAINT fk_integration_instance_case
            FOREIGN KEY (org_id, project_id, case_pk)
            REFERENCES integration_case(org_id, project_id, case_pk)
            ON DELETE RESTRICT,
          CHECK (updated_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE integration_instance_revision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          instance_pk UUID NOT NULL,
          revision BIGINT NOT NULL CHECK (revision >= 1),
          parent_revision BIGINT,
          installation_pk UUID,
          installation_revision BIGINT CHECK (installation_revision >= 1),
          composition_pk UUID,
          lock_revision BIGINT CHECK (lock_revision >= 1),
          lock_hash TEXT CHECK (
            lock_hash IS NULL OR lock_hash ~ '^sha256:[0-9a-f]{64}$'
          ),
          overlay_revision TEXT CHECK (
            overlay_revision IS NULL OR (
              overlay_revision = btrim(overlay_revision)
              AND char_length(overlay_revision) BETWEEN 1 AND 160
              AND overlay_revision !~ '[[:cntrl:]]'
            )
          ),
          required_markings JSONB NOT NULL DEFAULT '[]'::JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, instance_pk, revision),
          CONSTRAINT fk_integration_instance_revision_instance
            FOREIGN KEY (org_id, project_id, instance_pk)
            REFERENCES integration_instance(org_id, project_id, instance_pk)
            ON DELETE RESTRICT,
          CONSTRAINT fk_integration_instance_revision_parent
            FOREIGN KEY (org_id, project_id, instance_pk, parent_revision)
            REFERENCES integration_instance_revision(
              org_id, project_id, instance_pk, revision
            )
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_integration_instance_revision_installation
            FOREIGN KEY (
              org_id, project_id, installation_pk, installation_revision
            )
            REFERENCES bundle_installation_revision(
              org_id, project_id, installation_pk, revision
            )
            ON DELETE RESTRICT,
          CONSTRAINT fk_integration_instance_revision_lock
            FOREIGN KEY (org_id, project_id, composition_pk, lock_revision)
            REFERENCES bundle_composition_lock(
              org_id, project_id, composition_pk, revision
            )
            ON DELETE RESTRICT,
          CHECK (
            (revision = 1 AND parent_revision IS NULL)
            OR (revision > 1 AND parent_revision = revision - 1)
          ),
          CHECK (
            num_nonnulls(
              installation_pk, installation_revision, composition_pk,
              lock_revision, lock_hash, overlay_revision
            ) IN (0, 6)
          )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE integration_instance
          ADD CONSTRAINT fk_integration_instance_current_revision
          FOREIGN KEY (
            org_id, project_id, instance_pk, current_revision
          )
          REFERENCES integration_instance_revision(
            org_id, project_id, instance_pk, revision
          )
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        f"""
        CREATE TABLE integration_evidence (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          evidence_pk UUID NOT NULL,
          evidence_id UUID NOT NULL,
          case_pk UUID NOT NULL,
          revision BIGINT NOT NULL CHECK (revision >= 1),
          evidence_type TEXT NOT NULL CHECK (
            evidence_type IN ({_sql_values(_EVIDENCE_TYPES)})
          ),
          series_key TEXT NOT NULL CHECK (
            series_key = btrim(series_key)
            AND char_length(series_key) BETWEEN 1 AND 1024
            AND series_key !~ '[[:cntrl:]]'
          ),
          subject_ref TEXT NOT NULL CHECK (
            subject_ref = btrim(subject_ref)
            AND char_length(subject_ref) BETWEEN 1 AND 1024
            AND subject_ref !~ '[[:cntrl:]]'
          ),
          artifact_ref TEXT NOT NULL CHECK (
            artifact_ref = btrim(artifact_ref)
            AND char_length(artifact_ref) BETWEEN 1 AND 1024
            AND artifact_ref !~ '[[:cntrl:]]'
          ),
          artifact_hash TEXT NOT NULL
            CHECK (artifact_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          outcome TEXT NOT NULL CHECK (outcome IN ('valid', 'invalid', 'revoked')),
          observed_at TIMESTAMPTZ NOT NULL,
          expires_at TIMESTAMPTZ,
          revoked_at TIMESTAMPTZ,
          required_markings JSONB NOT NULL,
          producer TEXT NOT NULL CHECK (
            producer = btrim(producer)
            AND char_length(producer) BETWEEN 1 AND 1024
            AND producer !~ '[[:cntrl:]]'
          ),
          claims_json JSONB NOT NULL CHECK (jsonb_typeof(claims_json) = 'object'),
          envelope_json JSONB NOT NULL
            CHECK (jsonb_typeof(envelope_json) = 'object'),
          evidence_hash TEXT NOT NULL
            CHECK (evidence_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, evidence_pk, revision),
          UNIQUE (org_id, project_id, evidence_id, revision),
          UNIQUE (
            org_id, project_id, case_pk, producer, series_key, revision
          ),
          CONSTRAINT fk_integration_evidence_case
            FOREIGN KEY (org_id, project_id, case_pk)
            REFERENCES integration_case(org_id, project_id, case_pk)
            ON DELETE RESTRICT,
          CHECK (expires_at IS NULL OR expires_at > observed_at),
          CHECK (recorded_at >= observed_at),
          CHECK (
            (outcome = 'revoked' AND revoked_at IS NOT NULL)
            OR (outcome <> 'revoked' AND revoked_at IS NULL)
          ),
          CHECK (
            revoked_at IS NULL
            OR (revoked_at >= observed_at AND revoked_at <= recorded_at)
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE integration_evidence_snapshot (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          case_pk UUID NOT NULL,
          snapshot_revision BIGINT NOT NULL CHECK (snapshot_revision >= 1),
          instance_pk UUID NOT NULL,
          instance_revision BIGINT NOT NULL CHECK (instance_revision >= 1),
          snapshot_json JSONB NOT NULL
            CHECK (jsonb_typeof(snapshot_json) = 'object'),
          snapshot_hash TEXT NOT NULL
            CHECK (snapshot_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          cutoff_at TIMESTAMPTZ NOT NULL,
          next_projection_at TIMESTAMPTZ,
          computed_stage TEXT NOT NULL CHECK (
            computed_stage IN ({_sql_values(_STAGES)})
          ),
          stage_policy_version TEXT NOT NULL CHECK (
            stage_policy_version = 'aos.integration-stage/v1'
          ),
          evidence_count INTEGER NOT NULL CHECK (
            evidence_count BETWEEN 0 AND 512
          ),
          stage_gates_json JSONB NOT NULL CHECK (
            jsonb_typeof(stage_gates_json) = 'array'
            AND jsonb_array_length(stage_gates_json) = 8
          ),
          blocker_refs_json JSONB NOT NULL CHECK (
            jsonb_typeof(blocker_refs_json) = 'array'
            AND jsonb_array_length(blocker_refs_json) <= 256
          ),
          etag_version BIGINT NOT NULL CHECK (etag_version >= 1),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, case_pk, snapshot_revision),
          CONSTRAINT fk_integration_snapshot_case
            FOREIGN KEY (org_id, project_id, case_pk)
            REFERENCES integration_case(org_id, project_id, case_pk)
            ON DELETE RESTRICT,
          CONSTRAINT fk_integration_snapshot_instance_revision
            FOREIGN KEY (
              org_id, project_id, instance_pk, instance_revision
            )
            REFERENCES integration_instance_revision(
              org_id, project_id, instance_pk, revision
            )
            ON DELETE RESTRICT,
          CHECK (
            next_projection_at IS NULL OR next_projection_at > cutoff_at
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE integration_stage_event (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          case_pk UUID NOT NULL,
          sequence BIGINT NOT NULL CHECK (sequence >= 1),
          snapshot_revision BIGINT NOT NULL CHECK (snapshot_revision >= 1),
          old_stage TEXT CHECK (
            old_stage IS NULL OR old_stage IN ({_sql_values(_STAGES)})
          ),
          new_stage TEXT NOT NULL CHECK (
            new_stage IN ({_sql_values(_STAGES)})
          ),
          cause TEXT NOT NULL CHECK (cause IN (
            'created', 'evidence_added', 'negative_observed',
            'evidence_expired', 'evidence_revoked', 'projection_rebuilt'
          )),
          reason_refs JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, case_pk, sequence),
          CONSTRAINT fk_integration_stage_event_snapshot
            FOREIGN KEY (
              org_id, project_id, case_pk, snapshot_revision
            )
            REFERENCES integration_evidence_snapshot(
              org_id, project_id, case_pk, snapshot_revision
            )
            ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE integration_case_projection (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          case_pk UUID NOT NULL,
          instance_pk UUID NOT NULL,
          instance_revision BIGINT NOT NULL CHECK (instance_revision >= 1),
          snapshot_revision BIGINT NOT NULL CHECK (snapshot_revision >= 1),
          computed_stage TEXT NOT NULL CHECK (
            computed_stage IN ({_sql_values(_STAGES)})
          ),
          stage_policy_version TEXT NOT NULL CHECK (
            stage_policy_version = 'aos.integration-stage/v1'
          ),
          cutoff_at TIMESTAMPTZ NOT NULL,
          next_projection_at TIMESTAMPTZ,
          stage_gates_json JSONB NOT NULL CHECK (
            jsonb_typeof(stage_gates_json) = 'array'
            AND jsonb_array_length(stage_gates_json) = 8
          ),
          blockers_json JSONB NOT NULL CHECK (
            jsonb_typeof(blockers_json) = 'array'
            AND jsonb_array_length(blockers_json) <= 256
          ),
          connector_count BIGINT CHECK (connector_count >= 0),
          pipeline_count BIGINT CHECK (pipeline_count >= 0),
          dataset_row_count BIGINT CHECK (dataset_row_count >= 0),
          latency_ms BIGINT CHECK (latency_ms >= 0),
          blocker_count INTEGER NOT NULL CHECK (blocker_count BETWEEN 0 AND 256),
          etag_version BIGINT NOT NULL CHECK (etag_version >= 1),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, case_pk),
          CONSTRAINT fk_integration_projection_case
            FOREIGN KEY (org_id, project_id, case_pk)
            REFERENCES integration_case(org_id, project_id, case_pk)
            ON DELETE RESTRICT,
          CONSTRAINT fk_integration_projection_instance_revision
            FOREIGN KEY (
              org_id, project_id, instance_pk, instance_revision
            )
            REFERENCES integration_instance_revision(
              org_id, project_id, instance_pk, revision
            )
            ON DELETE RESTRICT,
          CONSTRAINT fk_integration_projection_snapshot
            FOREIGN KEY (
              org_id, project_id, case_pk, snapshot_revision
            )
            REFERENCES integration_evidence_snapshot(
              org_id, project_id, case_pk, snapshot_revision
            )
            ON DELETE RESTRICT,
          CHECK (
            next_projection_at IS NULL OR next_projection_at > cutoff_at
          )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE integration_case_command (
          org_id TEXT NOT NULL CHECK (
            org_id = btrim(org_id) AND char_length(org_id) BETWEEN 1 AND 160
          ),
          project_id TEXT NOT NULL CHECK (
            project_id = btrim(project_id)
            AND char_length(project_id) BETWEEN 1 AND 160
          ),
          operation TEXT NOT NULL CHECK (
            operation IN ('integration_cases.create', 'integration_cases.project')
          ),
          idempotency_key TEXT NOT NULL CHECK (
            idempotency_key = btrim(idempotency_key)
            AND char_length(idempotency_key) BETWEEN 1 AND 160
            AND idempotency_key !~ '[[:cntrl:]]'
          ),
          case_pk UUID NOT NULL,
          subject TEXT NOT NULL CHECK (
            subject = btrim(subject)
            AND char_length(subject) BETWEEN 1 AND 240
            AND subject !~ '[[:cntrl:]]'
            AND subject !~* '[A-Z0-9._%+-]+@[A-Z0-9.-]+[.][A-Z]{2,}'
          ),
          request_hash TEXT NOT NULL
            CHECK (request_hash ~ '^sha256:[0-9a-f]{64}$'),
          if_match_etag BIGINT CHECK (if_match_etag >= 1),
          status_code SMALLINT NOT NULL CHECK (status_code BETWEEN 200 AND 299),
          response_json JSONB NOT NULL
            CHECK (jsonb_typeof(response_json) = 'object'),
          response_etag TEXT NOT NULL
            CHECK (response_etag ~ '^"[1-9][0-9]*"$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, operation, idempotency_key),
          CONSTRAINT fk_integration_case_command_case
            FOREIGN KEY (org_id, project_id, case_pk)
            REFERENCES integration_case(org_id, project_id, case_pk)
            ON DELETE RESTRICT,
          CHECK (
            (operation = 'integration_cases.create' AND if_match_etag IS NULL)
            OR (
              operation = 'integration_cases.project'
              AND if_match_etag IS NOT NULL
            )
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_integration_case_list
          ON integration_case (
            org_id, project_id, scope, created_at DESC, case_id
          )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_integration_evidence_series_head
          ON integration_evidence (
            org_id, project_id, case_pk, producer, series_key, revision DESC
          )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_integration_evidence_expiry
          ON integration_evidence (
            org_id, project_id, expires_at, case_pk
          ) WHERE expires_at IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX idx_integration_projection_stage
          ON integration_case_projection (
            org_id, project_id, computed_stage, case_pk
          )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_integration_projection_expiry
          ON integration_case_projection (
            next_projection_at, org_id, project_id, case_pk
          ) WHERE next_projection_at IS NOT NULL
        """
    )


def _create_canonical_and_stage_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION canonical_integration_case_jsonb(input_value JSONB)
        RETURNS TEXT
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT canonical_asset_registry_jsonb(input_value)
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION canonical_integration_case_sha256(input_value JSONB)
        RETURNS TEXT
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT 'sha256:' || encode(
            public.digest(
              convert_to(canonical_integration_case_jsonb(input_value), 'UTF8'),
              'sha256'
            ),
            'hex'
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_jsonb_has_exact_keys(
          input_value JSONB,
          expected_keys TEXT[]
        )
        RETURNS BOOLEAN
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT jsonb_typeof(input_value) = 'object'
             AND ARRAY(
                   SELECT key FROM jsonb_object_keys(input_value) AS key
                   ORDER BY key
                 ) = ARRAY(
                   SELECT key FROM unnest(expected_keys) AS key ORDER BY key
                 )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_text_array_is_canonical(
          input_value JSONB,
          maximum_items INTEGER
        )
        RETURNS BOOLEAN
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT jsonb_typeof(input_value) = 'array'
             AND jsonb_array_length(input_value) <= maximum_items
             AND NOT EXISTS (
               SELECT 1
                 FROM jsonb_array_elements(input_value) AS item(value)
                WHERE jsonb_typeof(value) <> 'string'
                   OR value #>> '{}' = ''
                   OR value #>> '{}' <> btrim(value #>> '{}')
                   OR char_length(value #>> '{}') > 1024
                   OR value #>> '{}' ~ '[[:cntrl:]]'
             )
             AND ARRAY(
                   SELECT value #>> '{}'
                     FROM jsonb_array_elements(input_value)
                          WITH ORDINALITY AS item(value, ordinal)
                    ORDER BY ordinal
                 ) = ARRAY(
                   SELECT value #>> '{}'
                     FROM jsonb_array_elements(input_value) AS item(value)
                    ORDER BY value #>> '{}'
                 )
             AND (
               SELECT COUNT(*) = COUNT(DISTINCT value #>> '{}')
                 FROM jsonb_array_elements(input_value) AS item(value)
             )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_jsonb_contains_sensitive_text(
          input_value JSONB
        )
        RETURNS BOOLEAN
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT input_value::TEXT ~*
                   '[A-Z0-9._%+-]+@[A-Z0-9.-]+[.][A-Z]{2,}'
              OR input_value::TEXT ~*
                   '"(password|passwd|secret|authorization|bearer|access[_-]?token|refresh[_-]?token|api[_-]?key|private[_-]?key)"[[:space:]]*:'
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_claims_shape_valid(
          evidence_type_value TEXT,
          claims JSONB
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
        BEGIN
          CASE evidence_type_value
            WHEN 'source_connection' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['connectionRef','authMode','readProbe','tenantBinding']
              ) AND jsonb_typeof(claims->'connectionRef') = 'string'
                AND claims->>'connectionRef' <> ''
                AND claims->>'authMode' IN (
                  'oauth','service_account','api_key','database','other'
                )
                AND jsonb_typeof(claims->'readProbe') = 'boolean'
                AND jsonb_typeof(claims->'tenantBinding') = 'boolean';
            WHEN 'tenant_isolation' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims,
                ARRAY['positiveTenant','negativeTenant','crossTenantDenied']
              ) AND jsonb_typeof(claims->'positiveTenant') = 'string'
                AND jsonb_typeof(claims->'negativeTenant') = 'string'
                AND claims->>'positiveTenant' <> claims->>'negativeTenant'
                AND jsonb_typeof(claims->'crossTenantDenied') = 'boolean';
            WHEN 'pipeline_run' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims,
                ARRAY[
                  'pipelineRef','runId','result','inputRevision','outputRevision'
                ]
              ) AND jsonb_typeof(claims->'pipelineRef') = 'string'
                AND jsonb_typeof(claims->'runId') = 'string'
                AND claims->>'result' IN ('succeeded','failed')
                AND jsonb_typeof(claims->'inputRevision') = 'string'
                AND jsonb_typeof(claims->'outputRevision') = 'string';
            WHEN 'dataset_revision' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['datasetRef','revision','schemaHash','rowCount']
              ) AND jsonb_typeof(claims->'datasetRef') = 'string'
                AND jsonb_typeof(claims->'revision') = 'string'
                AND claims->>'schemaHash' ~ '^sha256:[0-9a-f]{64}$'
                AND (
                  jsonb_typeof(claims->'rowCount') = 'null'
                  OR (
                    jsonb_typeof(claims->'rowCount') = 'number'
                    AND (claims->>'rowCount')::NUMERIC >= 0
                    AND trunc((claims->>'rowCount')::NUMERIC)
                        = (claims->>'rowCount')::NUMERIC
                  )
                );
            WHEN 'data_quality' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims,
                ARRAY['datasetRef','checkSetHash','requiredPassed','failedChecks']
              ) AND jsonb_typeof(claims->'datasetRef') = 'string'
                AND claims->>'checkSetHash' ~ '^sha256:[0-9a-f]{64}$'
                AND jsonb_typeof(claims->'requiredPassed') = 'boolean'
                AND integration_text_array_is_canonical(
                  claims->'failedChecks', 128
                );
            WHEN 'ontology_revision' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['ontologyRef','revision','schemaHash']
              ) AND jsonb_typeof(claims->'ontologyRef') = 'string'
                AND jsonb_typeof(claims->'revision') = 'string'
                AND claims->>'schemaHash' ~ '^sha256:[0-9a-f]{64}$';
            WHEN 'mapping_validation' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['mappingRef','coverage','linkValidationPassed']
              ) AND jsonb_typeof(claims->'mappingRef') = 'string'
                AND jsonb_typeof(claims->'coverage') = 'number'
                AND (claims->>'coverage')::NUMERIC BETWEEN 0 AND 1
                AND jsonb_typeof(claims->'linkValidationPassed') = 'boolean';
            WHEN 'logic_publication' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['logicRef','immutableRevision','publicationHash']
              ) AND jsonb_typeof(claims->'logicRef') = 'string'
                AND jsonb_typeof(claims->'immutableRevision') = 'string'
                AND claims->>'publicationHash' ~ '^sha256:[0-9a-f]{64}$';
            WHEN 'logic_eval' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['logicRef','evalSuiteHash','requiredPassed']
              ) AND jsonb_typeof(claims->'logicRef') = 'string'
                AND claims->>'evalSuiteHash' ~ '^sha256:[0-9a-f]{64}$'
                AND jsonb_typeof(claims->'requiredPassed') = 'boolean';
            WHEN 'workshop_validation' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims,
                ARRAY[
                  'workshopRef','realSource','emptyStatePassed',
                  'permissionPassed','mainFlowPassed'
                ]
              ) AND jsonb_typeof(claims->'workshopRef') = 'string'
                AND jsonb_typeof(claims->'realSource') = 'boolean'
                AND jsonb_typeof(claims->'emptyStatePassed') = 'boolean'
                AND jsonb_typeof(claims->'permissionPassed') = 'boolean'
                AND jsonb_typeof(claims->'mainFlowPassed') = 'boolean';
            WHEN 'action_safety' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims,
                ARRAY[
                  'actionRef','approvalControlPassed','rollbackControlPassed',
                  'idempotencyControlPassed','installationApplyVerified',
                  'installationVerifyVerified'
                ]
              ) AND jsonb_typeof(claims->'actionRef') = 'string'
                AND jsonb_typeof(claims->'approvalControlPassed') = 'boolean'
                AND jsonb_typeof(claims->'rollbackControlPassed') = 'boolean'
                AND jsonb_typeof(claims->'idempotencyControlPassed') = 'boolean'
                AND jsonb_typeof(claims->'installationApplyVerified') = 'boolean'
                AND jsonb_typeof(claims->'installationVerifyVerified') = 'boolean';
            WHEN 'operations_readiness' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims,
                ARRAY['runbookRef','alertRef','ownerRef','requiredChecksPassed']
              ) AND jsonb_typeof(claims->'runbookRef') = 'string'
                AND jsonb_typeof(claims->'alertRef') = 'string'
                AND jsonb_typeof(claims->'ownerRef') = 'string'
                AND jsonb_typeof(claims->'requiredChecksPassed') = 'boolean';
            WHEN 'security_validation' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['policySetHash','requiredChecksPassed']
              ) AND claims->>'policySetHash' ~ '^sha256:[0-9a-f]{64}$'
                AND jsonb_typeof(claims->'requiredChecksPassed') = 'boolean';
            WHEN 'runtime_health' THEN
              RETURN integration_jsonb_has_exact_keys(
                claims, ARRAY['deploymentRef','runId','healthy','latencyMs']
              ) AND jsonb_typeof(claims->'deploymentRef') = 'string'
                AND jsonb_typeof(claims->'runId') = 'string'
                AND jsonb_typeof(claims->'healthy') = 'boolean'
                AND (
                  jsonb_typeof(claims->'latencyMs') = 'null'
                  OR (
                    jsonb_typeof(claims->'latencyMs') = 'number'
                    AND (claims->>'latencyMs')::NUMERIC >= 0
                    AND trunc((claims->>'latencyMs')::NUMERIC)
                        = (claims->>'latencyMs')::NUMERIC
                  )
                );
            ELSE
              RETURN FALSE;
          END CASE;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_claims_pass(
          evidence_type_value TEXT,
          claims JSONB
        )
        RETURNS BOOLEAN
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT CASE evidence_type_value
            WHEN 'source_connection' THEN
              (claims->>'readProbe')::BOOLEAN
              AND (claims->>'tenantBinding')::BOOLEAN
            WHEN 'tenant_isolation' THEN
              (claims->>'crossTenantDenied')::BOOLEAN
            WHEN 'pipeline_run' THEN claims->>'result' = 'succeeded'
            WHEN 'dataset_revision' THEN TRUE
            WHEN 'data_quality' THEN (claims->>'requiredPassed')::BOOLEAN
            WHEN 'ontology_revision' THEN TRUE
            WHEN 'mapping_validation' THEN
              (claims->>'coverage')::NUMERIC = 1
              AND (claims->>'linkValidationPassed')::BOOLEAN
            WHEN 'logic_publication' THEN TRUE
            WHEN 'logic_eval' THEN (claims->>'requiredPassed')::BOOLEAN
            WHEN 'workshop_validation' THEN
              (claims->>'realSource')::BOOLEAN
              AND (claims->>'emptyStatePassed')::BOOLEAN
              AND (claims->>'permissionPassed')::BOOLEAN
              AND (claims->>'mainFlowPassed')::BOOLEAN
            WHEN 'action_safety' THEN
              (claims->>'approvalControlPassed')::BOOLEAN
              AND (claims->>'rollbackControlPassed')::BOOLEAN
              AND (claims->>'idempotencyControlPassed')::BOOLEAN
              AND (claims->>'installationApplyVerified')::BOOLEAN
              AND (claims->>'installationVerifyVerified')::BOOLEAN
            WHEN 'operations_readiness' THEN
              (claims->>'requiredChecksPassed')::BOOLEAN
            WHEN 'security_validation' THEN
              (claims->>'requiredChecksPassed')::BOOLEAN
            WHEN 'runtime_health' THEN (claims->>'healthy')::BOOLEAN
            ELSE FALSE
          END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_snapshot_has_passing_type(
          snapshot_value JSONB,
          evidence_type_value TEXT,
          cutoff_value TIMESTAMPTZ
        )
        RETURNS BOOLEAN
        LANGUAGE SQL
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
          SELECT EXISTS (
            SELECT 1
              FROM jsonb_array_elements(snapshot_value->'evidence') AS item(value)
             WHERE value->>'evidenceType' = evidence_type_value
               AND value->>'outcome' = 'valid'
               AND (value->>'observedAt')::TIMESTAMPTZ <= cutoff_value
               AND (
                 jsonb_typeof(value->'expiresAt') = 'null'
                 OR cutoff_value < (value->>'expiresAt')::TIMESTAMPTZ
               )
               AND jsonb_typeof(value->'revokedAt') = 'null'
               AND integration_claims_pass(
                 evidence_type_value, value->'claims'
               )
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_snapshot_computed_stage(
          snapshot_value JSONB,
          cutoff_value TIMESTAMPTZ
        )
        RETURNS TEXT
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
        DECLARE
          result_stage TEXT := 'planned';
        BEGIN
          IF NOT (
            integration_snapshot_has_passing_type(
              snapshot_value, 'source_connection', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'tenant_isolation', cutoff_value
            )
          ) THEN RETURN result_stage; END IF;
          result_stage := 'connection_verified';
          IF NOT (
            integration_snapshot_has_passing_type(
              snapshot_value, 'pipeline_run', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'dataset_revision', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'data_quality', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'tenant_isolation', cutoff_value
            )
          ) THEN RETURN result_stage; END IF;
          result_stage := 'data_verified';
          IF NOT (
            integration_snapshot_has_passing_type(
              snapshot_value, 'ontology_revision', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'mapping_validation', cutoff_value
            )
          ) THEN RETURN result_stage; END IF;
          result_stage := 'ontology_verified';
          IF NOT (
            integration_snapshot_has_passing_type(
              snapshot_value, 'logic_publication', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'logic_eval', cutoff_value
            )
          ) THEN RETURN result_stage; END IF;
          result_stage := 'logic_verified';
          IF NOT integration_snapshot_has_passing_type(
            snapshot_value, 'workshop_validation', cutoff_value
          ) THEN RETURN result_stage; END IF;
          result_stage := 'workshop_verified';
          IF NOT (
            integration_snapshot_has_passing_type(
              snapshot_value, 'action_safety', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'operations_readiness', cutoff_value
            ) AND integration_snapshot_has_passing_type(
              snapshot_value, 'security_validation', cutoff_value
            )
          ) THEN RETURN result_stage; END IF;
          result_stage := 'production_ready';
          IF jsonb_array_length(snapshot_value->'blockerRefs') > 0
             OR NOT integration_snapshot_has_passing_type(
               snapshot_value, 'runtime_health', cutoff_value
             ) THEN RETURN result_stage; END IF;
          RETURN 'production_active';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION integration_stage_gates_are_canonical(gates JSONB)
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
        DECLARE
          expected_stages TEXT[] := ARRAY[{_sql_values(_STAGES)}];
          gate JSONB;
          gate_index INTEGER := 0;
        BEGIN
          IF jsonb_typeof(gates) <> 'array'
             OR jsonb_array_length(gates) <> 8 THEN
            RETURN FALSE;
          END IF;
          FOR gate IN SELECT value FROM jsonb_array_elements(gates) LOOP
            gate_index := gate_index + 1;
            IF NOT integration_jsonb_has_exact_keys(
                 gate, ARRAY['stage','status','evidenceRefs','reasonRefs']
               )
               OR gate->>'stage' <> expected_stages[gate_index]
               OR gate->>'status' NOT IN (
                 'satisfied','blocked','not_evaluated'
               )
               OR NOT integration_text_array_is_canonical(
                 gate->'evidenceRefs', 128
               )
               OR NOT integration_text_array_is_canonical(
                 gate->'reasonRefs', 128
               ) THEN
              RETURN FALSE;
            END IF;
          END LOOP;
          RETURN TRUE;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION integration_stage_gates_match_stage(
          gates JSONB,
          computed_stage_value TEXT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
        DECLARE
          expected_stages TEXT[] := ARRAY[{_sql_values(_STAGES)}];
          computed_rank INTEGER;
          gate JSONB;
          gate_index INTEGER := 0;
          expected_status TEXT;
        BEGIN
          computed_rank := array_position(expected_stages, computed_stage_value);
          IF computed_rank IS NULL
             OR NOT integration_stage_gates_are_canonical(gates) THEN
            RETURN FALSE;
          END IF;
          FOR gate IN SELECT value FROM jsonb_array_elements(gates) LOOP
            gate_index := gate_index + 1;
            expected_status := CASE
              WHEN gate_index <= computed_rank THEN 'satisfied'
              WHEN gate_index = computed_rank + 1 THEN 'blocked'
              ELSE 'not_evaluated'
            END;
            IF gate->>'status' <> expected_status THEN
              RETURN FALSE;
            END IF;
          END LOOP;
          RETURN TRUE;
        END;
        $$
        """
    )


def _create_immutability_and_identity_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_integration_history_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION
            'integration canonical history is immutable'
            USING ERRCODE = '23514';
        END;
        $$
        """
    )
    for table in _HISTORY_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_integration_history_immutable()
            """
        )
    for table in _ALL_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_integration_history_immutable()
            """
        )
    op.execute(
        """
        CREATE FUNCTION guard_integration_case_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NOT integration_text_array_is_canonical(
            NEW.required_markings, 64
          ) THEN
            RAISE EXCEPTION
              'integration case markings are not canonical'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_case_insert_guard
        BEFORE INSERT ON integration_case
        FOR EACH ROW EXECUTE FUNCTION guard_integration_case_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_integration_instance_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          case_scope TEXT;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION
              'integration instances cannot be deleted'
              USING ERRCODE = '23514';
          END IF;
          SELECT scope INTO case_scope
            FROM integration_case
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
           FOR UPDATE;
          IF case_scope IS NULL THEN
            RAISE EXCEPTION
              'integration instance case is missing'
              USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'INSERT' THEN
            IF NEW.current_revision <> 1 OR NEW.etag_version <> 1 THEN
              RAISE EXCEPTION
                'new integration instance must start at revision and etag 1'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;
          IF case_scope = 'reference' THEN
            RAISE EXCEPTION
              'reference integration instances are immutable'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.org_id IS DISTINCT FROM OLD.org_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.instance_pk IS DISTINCT FROM OLD.instance_pk
             OR NEW.case_pk IS DISTINCT FROM OLD.case_pk
             OR NEW.created_at IS DISTINCT FROM OLD.created_at
             OR NEW.current_revision <> OLD.current_revision + 1
             OR NEW.etag_version <> OLD.etag_version + 1
             OR NEW.updated_at <= OLD.updated_at THEN
            RAISE EXCEPTION
              'instance transition must advance revision, etag, and time once'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_instance_mutation_guard
        BEFORE INSERT OR UPDATE OR DELETE ON integration_instance
        FOR EACH ROW EXECUTE FUNCTION guard_integration_instance_mutation()
        """
    )


def _create_instance_and_evidence_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_integration_instance_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          instance_row integration_instance%ROWTYPE;
          case_scope TEXT;
          previous_revision BIGINT;
          installation_row RECORD;
        BEGIN
          SELECT * INTO instance_row
            FROM integration_instance
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND instance_pk = NEW.instance_pk
           FOR UPDATE;
          IF NOT FOUND THEN
            RAISE EXCEPTION
              'integration instance revision parent is missing'
              USING ERRCODE = '23514';
          END IF;
          SELECT scope INTO case_scope
            FROM integration_case
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = instance_row.case_pk;
          SELECT MAX(revision) INTO previous_revision
            FROM integration_instance_revision
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND instance_pk = NEW.instance_pk;
          IF (previous_revision IS NULL AND NEW.revision <> 1)
             OR (
               previous_revision IS NOT NULL
               AND NEW.revision <> previous_revision + 1
             ) THEN
            RAISE EXCEPTION
              'instance revision must extend the revision tail'
              USING ERRCODE = '23514';
          END IF;
          IF NOT integration_text_array_is_canonical(
            NEW.required_markings, 64
          ) THEN
            RAISE EXCEPTION
              'instance revision markings are not canonical'
              USING ERRCODE = '23514';
          END IF;
          IF case_scope = 'reference' THEN
            IF num_nonnulls(
                 NEW.installation_pk, NEW.installation_revision,
                 NEW.composition_pk, NEW.lock_revision,
                 NEW.lock_hash, NEW.overlay_revision
               ) <> 0 THEN
              RAISE EXCEPTION
                'reference instance cannot retain installation bindings'
                USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
              SELECT 1 FROM integration_case_projection
               WHERE org_id = NEW.org_id
                 AND project_id = NEW.project_id
                 AND case_pk = instance_row.case_pk
            ) THEN
              RAISE EXCEPTION
                'reference instance cannot be revised after projection'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;
          IF num_nonnulls(
               NEW.installation_pk, NEW.installation_revision,
               NEW.composition_pk, NEW.lock_revision,
               NEW.lock_hash, NEW.overlay_revision
             ) <> 6 THEN
            RAISE EXCEPTION
              'current instance requires exact installation and lock bindings'
              USING ERRCODE = '23514';
          END IF;
          SELECT i.active_revision,
                 r.state, r.composition_pk, r.lock_revision,
                 r.lock_hash, r.overlay_revision
            INTO installation_row
            FROM bundle_installation AS i
            JOIN bundle_installation_revision AS r
              ON r.org_id = i.org_id
             AND r.project_id = i.project_id
             AND r.installation_pk = i.installation_pk
             AND r.revision = NEW.installation_revision
           WHERE i.org_id = NEW.org_id
             AND i.project_id = NEW.project_id
             AND i.installation_pk = NEW.installation_pk;
          IF NOT FOUND
             OR installation_row.active_revision IS DISTINCT FROM
                  NEW.installation_revision
             OR installation_row.state <> 'active'
             OR installation_row.composition_pk IS DISTINCT FROM
                  NEW.composition_pk
             OR installation_row.lock_revision IS DISTINCT FROM
                  NEW.lock_revision
             OR installation_row.lock_hash IS DISTINCT FROM NEW.lock_hash
             OR installation_row.overlay_revision IS DISTINCT FROM
                  NEW.overlay_revision THEN
            RAISE EXCEPTION
              'instance binding is not the exact active installation revision'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_instance_revision_insert_guard
        BEFORE INSERT ON integration_instance_revision
        FOR EACH ROW EXECUTE FUNCTION guard_integration_instance_revision_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_integration_evidence_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          case_scope TEXT;
          previous_row integration_evidence%ROWTYPE;
          expected_keys TEXT[] := ARRAY[
            'evidenceId','revision','evidenceType','seriesKey','subjectRef',
            'artifactRef','artifactHash','outcome','observedAt','expiresAt',
            'revokedAt','requiredMarkings','producer','claims','evidenceHash',
            'recordedAt'
          ];
        BEGIN
          SELECT scope INTO case_scope
            FROM integration_case
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
           FOR UPDATE;
          IF case_scope IS NULL THEN
            RAISE EXCEPTION
              'integration evidence case is missing'
              USING ERRCODE = '23514';
          END IF;
          IF case_scope = 'reference' AND EXISTS (
            SELECT 1 FROM integration_case_projection
             WHERE org_id = NEW.org_id
               AND project_id = NEW.project_id
               AND case_pk = NEW.case_pk
          ) THEN
            RAISE EXCEPTION
              'reference evidence cannot mutate after projection'
              USING ERRCODE = '23514';
          END IF;
          SELECT * INTO previous_row
            FROM integration_evidence
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND evidence_pk = NEW.evidence_pk
           ORDER BY revision DESC
           LIMIT 1;
          IF NOT FOUND THEN
            IF NEW.revision <> 1 THEN
              RAISE EXCEPTION
                'first evidence series revision must be 1'
                USING ERRCODE = '23514';
            END IF;
          ELSIF NEW.revision <> previous_row.revision + 1
             OR NEW.evidence_id IS DISTINCT FROM previous_row.evidence_id
             OR NEW.case_pk IS DISTINCT FROM previous_row.case_pk
             OR NEW.evidence_type IS DISTINCT FROM previous_row.evidence_type
             OR NEW.series_key IS DISTINCT FROM previous_row.series_key
             OR NEW.subject_ref IS DISTINCT FROM previous_row.subject_ref
             OR NEW.artifact_ref IS DISTINCT FROM previous_row.artifact_ref
             OR NEW.producer IS DISTINCT FROM previous_row.producer THEN
            RAISE EXCEPTION
              'evidence revision does not extend an immutable series identity'
              USING ERRCODE = '23514';
          END IF;
          IF NOT integration_text_array_is_canonical(
               NEW.required_markings, 64
             )
             OR NOT integration_claims_shape_valid(
               NEW.evidence_type, NEW.claims_json
             )
             OR NOT integration_jsonb_has_exact_keys(
               NEW.envelope_json, expected_keys
             )
             OR integration_jsonb_contains_sensitive_text(
               NEW.envelope_json
             ) THEN
            RAISE EXCEPTION
              'evidence typed claims or envelope shape is invalid'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.envelope_json->>'evidenceId' <> NEW.evidence_id::TEXT
             OR (NEW.envelope_json->>'revision')::BIGINT <> NEW.revision
             OR NEW.envelope_json->>'evidenceType' <> NEW.evidence_type
             OR NEW.envelope_json->>'seriesKey' <> NEW.series_key
             OR NEW.envelope_json->>'subjectRef' <> NEW.subject_ref
             OR NEW.envelope_json->>'artifactRef' <> NEW.artifact_ref
             OR NEW.envelope_json->>'artifactHash' <> NEW.artifact_hash
             OR NEW.envelope_json->>'outcome' <> NEW.outcome
             OR (NEW.envelope_json->>'observedAt')::TIMESTAMPTZ
                  IS DISTINCT FROM NEW.observed_at
             OR NEW.envelope_json->>'observedAt' !~ '(Z|[+]00:00)$'
             OR (CASE WHEN jsonb_typeof(NEW.envelope_json->'expiresAt') = 'null'
                      THEN NULL
                      ELSE (NEW.envelope_json->>'expiresAt')::TIMESTAMPTZ END)
                  IS DISTINCT FROM NEW.expires_at
             OR (
               jsonb_typeof(NEW.envelope_json->'expiresAt') <> 'null'
               AND NEW.envelope_json->>'expiresAt' !~ '(Z|[+]00:00)$'
             )
             OR (CASE WHEN jsonb_typeof(NEW.envelope_json->'revokedAt') = 'null'
                      THEN NULL
                      ELSE (NEW.envelope_json->>'revokedAt')::TIMESTAMPTZ END)
                  IS DISTINCT FROM NEW.revoked_at
             OR (
               jsonb_typeof(NEW.envelope_json->'revokedAt') <> 'null'
               AND NEW.envelope_json->>'revokedAt' !~ '(Z|[+]00:00)$'
             )
             OR NEW.envelope_json->'requiredMarkings'
                  IS DISTINCT FROM NEW.required_markings
             OR NEW.envelope_json->>'producer' <> NEW.producer
             OR NEW.envelope_json->'claims' IS DISTINCT FROM NEW.claims_json
             OR NEW.envelope_json->>'evidenceHash' <> NEW.evidence_hash
             OR (NEW.envelope_json->>'recordedAt')::TIMESTAMPTZ
                  IS DISTINCT FROM NEW.recorded_at
             OR NEW.envelope_json->>'recordedAt' !~ '(Z|[+]00:00)$'
             OR NEW.evidence_hash IS DISTINCT FROM
                  canonical_integration_case_sha256(
                    NEW.envelope_json - 'evidenceHash'
                  ) THEN
            RAISE EXCEPTION
              'evidence envelope mirror or canonical hash is invalid'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_evidence_insert_guard
        BEFORE INSERT ON integration_evidence
        FOR EACH ROW EXECUTE FUNCTION guard_integration_evidence_insert()
        """
    )


def _create_snapshot_event_projection_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_integration_snapshot_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          case_row integration_case%ROWTYPE;
          instance_row integration_instance%ROWTYPE;
          previous_revision BIGINT;
          expected_evidence JSONB;
          expected_count INTEGER;
          expected_keys TEXT[] := ARRAY[
            'caseId','snapshotRevision','instanceRevision','cutoffAt',
            'nextProjectionAt','evidence','snapshotHash','computedStage',
            'stagePolicyVersion','stageGates','blockerRefs'
          ];
        BEGIN
          SELECT * INTO case_row
            FROM integration_case
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
           FOR UPDATE;
          IF NOT FOUND THEN
            RAISE EXCEPTION
              'integration snapshot case is missing'
              USING ERRCODE = '23514';
          END IF;
          SELECT * INTO instance_row
            FROM integration_instance
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND instance_pk = NEW.instance_pk
             AND case_pk = NEW.case_pk
           FOR UPDATE;
          IF NOT FOUND
             OR NEW.instance_revision IS DISTINCT FROM
                  instance_row.current_revision
             OR NEW.etag_version IS DISTINCT FROM instance_row.etag_version THEN
            RAISE EXCEPTION
              'snapshot must bind the current instance revision and etag'
              USING ERRCODE = '23514';
          END IF;
          IF case_row.scope = 'reference' AND EXISTS (
            SELECT 1 FROM integration_case_projection
             WHERE org_id = NEW.org_id
               AND project_id = NEW.project_id
               AND case_pk = NEW.case_pk
          ) THEN
            RAISE EXCEPTION
              'reference snapshots cannot mutate after initial projection'
              USING ERRCODE = '23514';
          END IF;
          SELECT MAX(snapshot_revision) INTO previous_revision
            FROM integration_evidence_snapshot
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk;
          IF (previous_revision IS NULL AND NEW.snapshot_revision <> 1)
             OR (
               previous_revision IS NOT NULL
               AND NEW.snapshot_revision <> previous_revision + 1
             ) THEN
            RAISE EXCEPTION
              'snapshot must extend the case snapshot tail'
              USING ERRCODE = '23514';
          END IF;
          IF NOT integration_jsonb_has_exact_keys(
               NEW.snapshot_json, expected_keys
             )
             OR NOT integration_stage_gates_match_stage(
               NEW.stage_gates_json, NEW.computed_stage
             )
             OR NOT integration_text_array_is_canonical(
               NEW.blocker_refs_json, 256
             ) THEN
            RAISE EXCEPTION
              'snapshot canonical shape is invalid'
              USING ERRCODE = '23514';
          END IF;
          WITH heads AS (
            SELECT DISTINCT ON (producer, series_key)
                   producer, series_key, envelope_json
              FROM integration_evidence
             WHERE org_id = NEW.org_id
               AND project_id = NEW.project_id
               AND case_pk = NEW.case_pk
               AND recorded_at <= NEW.cutoff_at
             ORDER BY producer, series_key, revision DESC
          )
          SELECT COALESCE(
                   jsonb_agg(envelope_json ORDER BY producer, series_key),
                   '[]'::JSONB
                 ), COUNT(*)::INTEGER
            INTO expected_evidence, expected_count
            FROM heads;
          IF NEW.snapshot_json->'evidence' IS DISTINCT FROM expected_evidence
             OR NEW.evidence_count IS DISTINCT FROM expected_count
             OR jsonb_array_length(NEW.snapshot_json->'evidence')
                  IS DISTINCT FROM NEW.evidence_count THEN
            RAISE EXCEPTION
              'snapshot does not contain the complete latest evidence heads'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.snapshot_json->>'caseId' <> case_row.case_id::TEXT
             OR (NEW.snapshot_json->>'snapshotRevision')::BIGINT
                  <> NEW.snapshot_revision
             OR (NEW.snapshot_json->>'instanceRevision')::BIGINT
                  <> NEW.instance_revision
             OR (NEW.snapshot_json->>'cutoffAt')::TIMESTAMPTZ
                  IS DISTINCT FROM NEW.cutoff_at
             OR NEW.snapshot_json->>'cutoffAt' !~ '(Z|[+]00:00)$'
             OR (CASE
                  WHEN jsonb_typeof(
                    NEW.snapshot_json->'nextProjectionAt'
                  ) = 'null' THEN NULL
                  ELSE (
                    NEW.snapshot_json->>'nextProjectionAt'
                  )::TIMESTAMPTZ
                END) IS DISTINCT FROM NEW.next_projection_at
             OR (
               jsonb_typeof(NEW.snapshot_json->'nextProjectionAt') <> 'null'
               AND NEW.snapshot_json->>'nextProjectionAt' !~ '(Z|[+]00:00)$'
             )
             OR NEW.snapshot_json->>'snapshotHash' <> NEW.snapshot_hash
             OR NEW.snapshot_json->>'computedStage' <> NEW.computed_stage
             OR NEW.snapshot_json->>'stagePolicyVersion'
                  <> NEW.stage_policy_version
             OR NEW.snapshot_json->'stageGates'
                  IS DISTINCT FROM NEW.stage_gates_json
             OR NEW.snapshot_json->'blockerRefs'
                  IS DISTINCT FROM NEW.blocker_refs_json
             OR NEW.snapshot_hash IS DISTINCT FROM
                  canonical_integration_case_sha256(
                    NEW.snapshot_json - 'snapshotHash'
                  ) THEN
            RAISE EXCEPTION
              'snapshot mirror or canonical hash is invalid'
              USING ERRCODE = '23514';
          END IF;
          IF integration_snapshot_computed_stage(
               NEW.snapshot_json, NEW.cutoff_at
             ) IS DISTINCT FROM NEW.computed_stage THEN
            RAISE EXCEPTION
              'snapshot computed stage does not match fixed claims policy'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_snapshot_insert_guard
        BEFORE INSERT ON integration_evidence_snapshot
        FOR EACH ROW EXECUTE FUNCTION guard_integration_snapshot_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_integration_stage_event_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          previous_event integration_stage_event%ROWTYPE;
          snapshot_stage TEXT;
        BEGIN
          PERFORM 1 FROM integration_case
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
           FOR UPDATE;
          IF NOT FOUND THEN
            RAISE EXCEPTION
              'stage event case is missing'
              USING ERRCODE = '23514';
          END IF;
          SELECT * INTO previous_event
            FROM integration_stage_event
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
           ORDER BY sequence DESC
           LIMIT 1;
          SELECT computed_stage INTO snapshot_stage
            FROM integration_evidence_snapshot
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
             AND snapshot_revision = NEW.snapshot_revision;
          IF snapshot_stage IS NULL
             OR snapshot_stage IS DISTINCT FROM NEW.new_stage
             OR NOT integration_text_array_is_canonical(
               NEW.reason_refs, 128
             ) THEN
            RAISE EXCEPTION
              'stage event does not match its snapshot or canonical refs'
              USING ERRCODE = '23514';
          END IF;
          IF previous_event.sequence IS NULL THEN
            IF NEW.sequence <> 1
               OR NEW.old_stage IS NOT NULL
               OR NEW.new_stage <> 'planned'
               OR NEW.cause <> 'created' THEN
              RAISE EXCEPTION
                'first stage event must create planned stage from null'
                USING ERRCODE = '23514';
            END IF;
          ELSIF NEW.sequence <> previous_event.sequence + 1
             OR NEW.old_stage IS DISTINCT FROM previous_event.new_stage
             OR NEW.new_stage = NEW.old_stage
             OR NEW.snapshot_revision <= previous_event.snapshot_revision
             OR NEW.cause = 'created' THEN
            RAISE EXCEPTION
              'stage event must extend a changed stage tail'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_stage_event_insert_guard
        BEFORE INSERT ON integration_stage_event
        FOR EACH ROW EXECUTE FUNCTION guard_integration_stage_event_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION integration_blockers_are_valid(blockers JSONB)
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
        DECLARE
          blocker JSONB;
        BEGIN
          IF jsonb_typeof(blockers) <> 'array'
             OR jsonb_array_length(blockers) > 256 THEN
            RETURN FALSE;
          END IF;
          FOR blocker IN SELECT value FROM jsonb_array_elements(blockers) LOOP
            IF NOT integration_jsonb_has_exact_keys(
                 blocker,
                 ARRAY[
                   'blockerId','code','severity','status','gate','reasonRefs',
                   'evidenceRefs','owner','firstObservedAt','updatedAt'
                 ]
               )
               OR blocker->>'blockerId' !~
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
               OR blocker->>'code' = ''
               OR blocker->>'severity' NOT IN ('critical','high','medium','low')
               OR blocker->>'status' NOT IN ('open','resolved')
               OR blocker->>'gate' NOT IN (
                 'planned','connection_verified','data_verified',
                 'ontology_verified','logic_verified','workshop_verified',
                 'production_ready','production_active'
               )
               OR NOT integration_text_array_is_canonical(
                 blocker->'reasonRefs', 128
               )
               OR NOT integration_text_array_is_canonical(
                 blocker->'evidenceRefs', 128
               )
               OR NOT (
                 jsonb_typeof(blocker->'owner') = 'null'
                 OR (
                   jsonb_typeof(blocker->'owner') = 'string'
                   AND blocker->>'owner' <> ''
                   AND blocker->>'owner' = btrim(blocker->>'owner')
                   AND char_length(blocker->>'owner') <= 1024
                   AND blocker->>'owner' !~ '[[:cntrl:]]'
                   AND blocker->>'owner' !~*
                     '[A-Z0-9._%+-]+@[A-Z0-9.-]+[.][A-Z]{2,}'
                 )
               )
               OR jsonb_typeof(blocker->'firstObservedAt') <> 'string'
               OR jsonb_typeof(blocker->'updatedAt') <> 'string'
               OR blocker->>'firstObservedAt' !~ '(Z|[+]00:00)$'
               OR blocker->>'updatedAt' !~ '(Z|[+]00:00)$'
               OR (blocker->>'updatedAt')::TIMESTAMPTZ
                    < (blocker->>'firstObservedAt')::TIMESTAMPTZ THEN
              RETURN FALSE;
            END IF;
          END LOOP;
          RETURN TRUE;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_integration_projection_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          case_scope TEXT;
          instance_row integration_instance%ROWTYPE;
          snapshot_row integration_evidence_snapshot%ROWTYPE;
          latest_snapshot BIGINT;
          open_blockers INTEGER;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION
              'integration projections cannot be deleted'
              USING ERRCODE = '23514';
          END IF;
          SELECT scope INTO case_scope
            FROM integration_case
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
           FOR UPDATE;
          IF case_scope IS NULL THEN
            RAISE EXCEPTION
              'integration projection case is missing'
              USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'UPDATE' AND case_scope = 'reference' THEN
            RAISE EXCEPTION
              'reference projections are immutable'
              USING ERRCODE = '23514';
          END IF;
          SELECT * INTO instance_row
            FROM integration_instance
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND instance_pk = NEW.instance_pk
             AND case_pk = NEW.case_pk;
          SELECT * INTO snapshot_row
            FROM integration_evidence_snapshot
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk
             AND snapshot_revision = NEW.snapshot_revision;
          SELECT MAX(snapshot_revision) INTO latest_snapshot
            FROM integration_evidence_snapshot
           WHERE org_id = NEW.org_id
             AND project_id = NEW.project_id
             AND case_pk = NEW.case_pk;
          IF instance_row.instance_pk IS NULL
             OR snapshot_row.case_pk IS NULL
             OR NEW.instance_revision IS DISTINCT FROM
                  instance_row.current_revision
             OR NEW.etag_version IS DISTINCT FROM instance_row.etag_version
             OR NEW.snapshot_revision IS DISTINCT FROM latest_snapshot
             OR snapshot_row.instance_pk IS DISTINCT FROM NEW.instance_pk
             OR snapshot_row.instance_revision IS DISTINCT FROM
                  NEW.instance_revision
             OR snapshot_row.computed_stage IS DISTINCT FROM NEW.computed_stage
             OR snapshot_row.stage_policy_version IS DISTINCT FROM
                  NEW.stage_policy_version
             OR snapshot_row.cutoff_at IS DISTINCT FROM NEW.cutoff_at
             OR snapshot_row.next_projection_at IS DISTINCT FROM
                  NEW.next_projection_at
             OR snapshot_row.stage_gates_json IS DISTINCT FROM
                  NEW.stage_gates_json THEN
            RAISE EXCEPTION
              'projection does not mirror the latest snapshot and instance'
              USING ERRCODE = '23514';
          END IF;
          IF NOT integration_stage_gates_match_stage(
               NEW.stage_gates_json, NEW.computed_stage
             )
             OR NOT integration_blockers_are_valid(NEW.blockers_json) THEN
            RAISE EXCEPTION
              'projection gates or blockers are not canonical'
              USING ERRCODE = '23514';
          END IF;
          SELECT COUNT(*)::INTEGER INTO open_blockers
            FROM jsonb_array_elements(NEW.blockers_json) AS item(value)
           WHERE value->>'status' = 'open';
          IF NEW.blocker_count IS DISTINCT FROM open_blockers THEN
            RAISE EXCEPTION
              'projection blocker count does not match open blockers'
              USING ERRCODE = '23514';
          END IF;
          IF (
               case_scope = 'reference'
               AND num_nonnulls(
                 NEW.connector_count, NEW.pipeline_count,
                 NEW.dataset_row_count, NEW.latency_ms
               ) <> 0
             ) THEN
            RAISE EXCEPTION
              'reference projection metrics must be null'
              USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'UPDATE' AND (
               NEW.org_id IS DISTINCT FROM OLD.org_id
               OR NEW.project_id IS DISTINCT FROM OLD.project_id
               OR NEW.case_pk IS DISTINCT FROM OLD.case_pk
               OR NEW.instance_pk IS DISTINCT FROM OLD.instance_pk
               OR NEW.snapshot_revision <= OLD.snapshot_revision
               OR NEW.etag_version <= OLD.etag_version
               OR NEW.updated_at <= OLD.updated_at
             ) THEN
            RAISE EXCEPTION
              'projection update must advance snapshot, etag, and time'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_projection_mutation_guard
        BEFORE INSERT OR UPDATE OR DELETE ON integration_case_projection
        FOR EACH ROW EXECUTE FUNCTION guard_integration_projection_mutation()
        """
    )


def _create_command_and_consistency_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_integration_command_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          case_scope TEXT;
          current_etag BIGINT;
        BEGIN
          SELECT c.scope, i.etag_version
            INTO case_scope, current_etag
            FROM integration_case AS c
            JOIN integration_instance AS i
              ON i.org_id = c.org_id
             AND i.project_id = c.project_id
             AND i.case_pk = c.case_pk
           WHERE c.org_id = NEW.org_id
             AND c.project_id = NEW.project_id
             AND c.case_pk = NEW.case_pk;
          IF case_scope IS NULL OR case_scope <> 'current' THEN
            RAISE EXCEPTION
              'commands must bind a current integration case'
              USING ERRCODE = '23514';
          END IF;
          IF NEW.response_etag <> '"' || current_etag::TEXT || '"'
             OR (
               NEW.operation = 'integration_cases.create'
               AND current_etag <> 1
             )
             OR (
               NEW.operation = 'integration_cases.project'
               AND NEW.if_match_etag IS DISTINCT FROM current_etag - 1
             ) THEN
            RAISE EXCEPTION
              'command receipt does not match the committed case etag'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_command_insert_guard
        BEFORE INSERT ON integration_case_command
        FOR EACH ROW EXECUTE FUNCTION guard_integration_command_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION assert_integration_case_consistency(
          target_org TEXT,
          target_project TEXT,
          target_case UUID
        )
        RETURNS VOID
        LANGUAGE plpgsql
        AS $$
        DECLARE
          instance_row integration_instance%ROWTYPE;
          projection_row integration_case_projection%ROWTYPE;
          snapshot_row integration_evidence_snapshot%ROWTYPE;
          maximum_instance_revision BIGINT;
          maximum_snapshot_revision BIGINT;
          event_stage TEXT;
          event_snapshot_revision BIGINT;
        BEGIN
          SELECT * INTO instance_row
            FROM integration_instance
           WHERE org_id = target_org
             AND project_id = target_project
             AND case_pk = target_case;
          SELECT * INTO projection_row
            FROM integration_case_projection
           WHERE org_id = target_org
             AND project_id = target_project
             AND case_pk = target_case;
          IF instance_row.instance_pk IS NULL OR projection_row.case_pk IS NULL THEN
            RAISE EXCEPTION
              'case must commit with instance and projection'
              USING ERRCODE = '23514';
          END IF;
          SELECT MAX(revision) INTO maximum_instance_revision
            FROM integration_instance_revision
           WHERE org_id = target_org
             AND project_id = target_project
             AND instance_pk = instance_row.instance_pk;
          SELECT MAX(snapshot_revision) INTO maximum_snapshot_revision
            FROM integration_evidence_snapshot
           WHERE org_id = target_org
             AND project_id = target_project
             AND case_pk = target_case;
          SELECT * INTO snapshot_row
            FROM integration_evidence_snapshot
           WHERE org_id = target_org
             AND project_id = target_project
             AND case_pk = target_case
             AND snapshot_revision = maximum_snapshot_revision;
          SELECT new_stage, snapshot_revision
            INTO event_stage, event_snapshot_revision
            FROM integration_stage_event
           WHERE org_id = target_org
             AND project_id = target_project
             AND case_pk = target_case
           ORDER BY sequence DESC
           LIMIT 1;
          IF maximum_instance_revision IS DISTINCT FROM
               instance_row.current_revision
             OR instance_row.etag_version IS DISTINCT FROM
                  instance_row.current_revision
             OR projection_row.instance_pk IS DISTINCT FROM
                  instance_row.instance_pk
             OR projection_row.instance_revision IS DISTINCT FROM
                  instance_row.current_revision
             OR maximum_snapshot_revision IS NULL
             OR projection_row.snapshot_revision IS DISTINCT FROM
                  maximum_snapshot_revision
             OR projection_row.computed_stage IS DISTINCT FROM
                  snapshot_row.computed_stage
             OR projection_row.etag_version IS DISTINCT FROM
                  instance_row.etag_version
             OR event_stage IS DISTINCT FROM projection_row.computed_stage
             OR event_snapshot_revision > projection_row.snapshot_revision THEN
            RAISE EXCEPTION
              'instance, snapshot, event, and projection tails disagree'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION ensure_integration_case_consistency()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          target_case UUID;
        BEGIN
          IF TG_TABLE_NAME = 'integration_instance' THEN
            target_case := NEW.case_pk;
          ELSIF TG_TABLE_NAME = 'integration_instance_revision' THEN
            SELECT case_pk INTO target_case
              FROM integration_instance
             WHERE org_id = NEW.org_id
               AND project_id = NEW.project_id
               AND instance_pk = NEW.instance_pk;
          ELSE
            target_case := NEW.case_pk;
          END IF;
          PERFORM assert_integration_case_consistency(
            NEW.org_id, NEW.project_id, target_case
          );
          RETURN NULL;
        END;
        $$
        """
    )
    for table, operations in (
        ("integration_instance", "INSERT OR UPDATE"),
        ("integration_instance_revision", "INSERT"),
        ("integration_evidence", "INSERT"),
        ("integration_evidence_snapshot", "INSERT"),
        ("integration_stage_event", "INSERT"),
        ("integration_case_projection", "INSERT OR UPDATE"),
    ):
        op.execute(
            f"""
            CREATE CONSTRAINT TRIGGER trg_{table}_case_consistency
            AFTER {operations} ON {table}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION ensure_integration_case_consistency()
            """
        )


def upgrade() -> None:
    _create_tables()
    _create_canonical_and_stage_functions()
    _create_immutability_and_identity_guards()
    _create_instance_and_evidence_guards()
    _create_snapshot_event_projection_guards()
    _create_command_and_consistency_guards()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM integration_case LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_instance LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_instance_revision LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_evidence LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_evidence_snapshot LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_stage_event LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_case_projection LIMIT 1)
             OR EXISTS (SELECT 1 FROM integration_case_command LIMIT 1) THEN
            RAISE EXCEPTION
              'integration case downgrade blocked: canonical data exists'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        ALTER TABLE integration_instance
          DROP CONSTRAINT fk_integration_instance_current_revision
        """
    )
    op.execute("DROP TABLE integration_case_command")
    op.execute("DROP TABLE integration_case_projection")
    op.execute("DROP TABLE integration_stage_event")
    op.execute("DROP TABLE integration_evidence_snapshot")
    op.execute("DROP TABLE integration_evidence")
    op.execute("DROP TABLE integration_instance_revision")
    op.execute("DROP TABLE integration_instance")
    op.execute("DROP TABLE integration_case")
    op.execute("DROP FUNCTION ensure_integration_case_consistency()")
    op.execute("DROP FUNCTION assert_integration_case_consistency(TEXT, TEXT, UUID)")
    op.execute("DROP FUNCTION guard_integration_command_insert()")
    op.execute("DROP FUNCTION guard_integration_projection_mutation()")
    op.execute("DROP FUNCTION integration_blockers_are_valid(JSONB)")
    op.execute("DROP FUNCTION guard_integration_stage_event_insert()")
    op.execute("DROP FUNCTION guard_integration_snapshot_insert()")
    op.execute("DROP FUNCTION guard_integration_evidence_insert()")
    op.execute("DROP FUNCTION guard_integration_instance_revision_insert()")
    op.execute("DROP FUNCTION guard_integration_instance_mutation()")
    op.execute("DROP FUNCTION guard_integration_case_insert()")
    op.execute("DROP FUNCTION guard_integration_history_immutable()")
    op.execute("DROP FUNCTION integration_stage_gates_match_stage(JSONB, TEXT)")
    op.execute("DROP FUNCTION integration_stage_gates_are_canonical(JSONB)")
    op.execute(
        "DROP FUNCTION integration_snapshot_computed_stage(JSONB, TIMESTAMPTZ)"
    )
    op.execute(
        "DROP FUNCTION integration_snapshot_has_passing_type(JSONB, TEXT, TIMESTAMPTZ)"
    )
    op.execute("DROP FUNCTION integration_claims_pass(TEXT, JSONB)")
    op.execute("DROP FUNCTION integration_claims_shape_valid(TEXT, JSONB)")
    op.execute("DROP FUNCTION integration_jsonb_contains_sensitive_text(JSONB)")
    op.execute("DROP FUNCTION integration_text_array_is_canonical(JSONB, INTEGER)")
    op.execute("DROP FUNCTION integration_jsonb_has_exact_keys(JSONB, TEXT[])")
    op.execute("DROP FUNCTION canonical_integration_case_sha256(JSONB)")
    op.execute("DROP FUNCTION canonical_integration_case_jsonb(JSONB)")
