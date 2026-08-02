"""Persist immutable evidence snapshots with lifecycle events.

Revision ID: 228assetevidence
Revises: 228assetinvariants
Create Date: 2026-08-03
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from alembic import op
from sqlalchemy import text

revision: str = "228assetevidence"
down_revision: str | Sequence[str] | None = "228assetinvariants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
_SIGNATURE_HASH_PROFILE = "canonical-envelope-v1"


def _canonical_signature_hash(signature: dict[str, Any]) -> str:
    payload = json.dumps(
        signature,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _normalize_mutable_signature_evidence() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        text(
            """
            SELECT v.version_pk, v.signature, e.artifact_hash
              FROM asset_bundle_version v
              JOIN asset_bundle_evidence e USING (version_pk)
             WHERE v.status IN ('draft', 'validated')
               AND v.signature IS NOT NULL
               AND e.evidence_type = 'signature_verification'
            """
        )
    ).mappings()
    for row in rows:
        signature = row["signature"]
        if not isinstance(signature, dict):
            continue
        canonical_hash = _canonical_signature_hash(signature)
        connection.execute(
            text(
                """
                UPDATE asset_bundle_evidence
                   SET artifact_hash = :artifact_hash,
                       metadata = metadata || jsonb_build_object(
                         'signatureHashProfile', CAST(:hash_profile AS TEXT)
                       ),
                       updated_at = NOW(),
                       updated_by = 'system:migration',
                       status_reason = 'canonicalized signature envelope hash'
                 WHERE version_pk = :version_pk
                   AND evidence_type = 'signature_verification'
                """
            ),
            {
                "artifact_hash": canonical_hash,
                "hash_profile": _SIGNATURE_HASH_PROFILE,
                "version_pk": row["version_pk"],
            },
        )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
    op.execute(
        """
        ALTER TABLE asset_bundle_version_event
          ADD COLUMN evidence_snapshot JSONB
          CHECK (
            evidence_snapshot IS NULL
            OR jsonb_typeof(evidence_snapshot) = 'array'
          )
        """
    )
    _normalize_mutable_signature_evidence()
    op.execute(
        """
        CREATE OR REPLACE FUNCTION canonical_asset_registry_jsonb(input_value JSONB)
        RETURNS TEXT
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
        DECLARE
          value_type TEXT;
          rendered TEXT;
        BEGIN
          value_type := jsonb_typeof(input_value);
          CASE value_type
            WHEN 'object' THEN
              SELECT '{' || COALESCE(
                       string_agg(
                         to_jsonb(item.key)::TEXT || ':' ||
                           canonical_asset_registry_jsonb(item.value),
                         ',' ORDER BY item.key COLLATE "C"
                       ),
                       ''
                     ) || '}'
                INTO rendered
                FROM jsonb_each(input_value) AS item;
              RETURN rendered;
            WHEN 'array' THEN
              SELECT '[' || COALESCE(
                       string_agg(
                         canonical_asset_registry_jsonb(item.value),
                         ',' ORDER BY item.ordinality
                       ),
                       ''
                     ) || ']'
                INTO rendered
                FROM jsonb_array_elements(input_value)
                     WITH ORDINALITY AS item(value, ordinality);
              RETURN rendered;
            WHEN 'number' THEN
              rendered := input_value::TEXT;
              IF POSITION('.' IN rendered) > 0 THEN
                rendered := (rendered::DOUBLE PRECISION)::TEXT;
                IF POSITION('.' IN rendered) = 0
                   AND POSITION('e' IN rendered) = 0 THEN
                  rendered := rendered || '.0';
                END IF;
              END IF;
              RETURN rendered;
            ELSE
              RETURN input_value::TEXT;
          END CASE;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_asset_bundle_version_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          previous_status TEXT;
          expected_sequence BIGINT;
          current_version_status TEXT;
          current_evidence_snapshot JSONB;
          expected_evidence_revision TEXT;
        BEGIN
          IF TG_OP IN ('UPDATE', 'DELETE', 'TRUNCATE') THEN
            RAISE EXCEPTION
              'asset bundle lifecycle events are append-only'
              USING ERRCODE = '23514';
          END IF;
          SELECT COALESCE(MAX(sequence), 0) + 1,
                 (ARRAY_AGG(to_status ORDER BY sequence DESC))[1]
            INTO expected_sequence, previous_status
            FROM asset_bundle_version_event
           WHERE version_pk = NEW.version_pk;
          IF NEW.sequence <> expected_sequence
             OR (NEW.sequence = 1 AND NEW.from_status <> 'draft')
             OR (
               NEW.sequence > 1
               AND NEW.from_status IS DISTINCT FROM previous_status
             ) THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event does not extend the event tail'
              USING ERRCODE = '23514';
          END IF;
          SELECT status
            INTO current_version_status
            FROM asset_bundle_version
           WHERE version_pk = NEW.version_pk;
          IF current_version_status IS NULL
             OR NEW.to_status <> current_version_status THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event does not match version status'
              USING ERRCODE = '23514';
          END IF;
          SELECT COALESCE(
                   jsonb_agg(
                     jsonb_build_object(
                       'type', evidence_type,
                       'artifactRef', artifact_ref,
                       'artifactHash', artifact_hash,
                       'status', status,
                       'observedAt', observed_at,
                       'expiresAt', expires_at,
                       'revokedAt', revoked_at,
                       'metadata', metadata
                     )
                     ORDER BY evidence_type, artifact_ref
                   ),
                   '[]'::JSONB
                 )
            INTO current_evidence_snapshot
            FROM asset_bundle_evidence
           WHERE version_pk = NEW.version_pk;
          IF NEW.evidence_snapshot IS NULL
             OR NEW.evidence_snapshot IS DISTINCT FROM current_evidence_snapshot THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event evidence snapshot is invalid'
              USING ERRCODE = '23514';
          END IF;
          expected_evidence_revision := 'sha256:' || encode(
            public.digest(
              convert_to(
                canonical_asset_registry_jsonb(NEW.evidence_snapshot),
                'UTF8'
              ),
              'sha256'
            ),
            'hex'
          );
          IF NEW.evidence_revision IS DISTINCT FROM expected_evidence_revision THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event evidence revision is invalid'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM asset_bundle_evidence
             WHERE evidence_type = 'signature_verification'
               AND metadata ->> 'signatureHashProfile'
                   = 'canonical-envelope-v1'
          ) THEN
            RAISE EXCEPTION
              'asset evidence snapshot downgrade blocked: signature hashes normalized'
              USING ERRCODE = '23514';
          END IF;
          IF EXISTS (
            SELECT 1
              FROM asset_bundle_version_event
             WHERE evidence_snapshot IS NOT NULL
          ) THEN
            RAISE EXCEPTION
              'asset evidence snapshot downgrade blocked: snapshots exist'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_asset_bundle_version_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          previous_status TEXT;
          expected_sequence BIGINT;
          current_version_status TEXT;
        BEGIN
          IF TG_OP IN ('UPDATE', 'DELETE', 'TRUNCATE') THEN
            RAISE EXCEPTION
              'asset bundle lifecycle events are append-only'
              USING ERRCODE = '23514';
          END IF;
          SELECT COALESCE(MAX(sequence), 0) + 1,
                 (ARRAY_AGG(to_status ORDER BY sequence DESC))[1]
            INTO expected_sequence, previous_status
            FROM asset_bundle_version_event
           WHERE version_pk = NEW.version_pk;
          IF NEW.sequence <> expected_sequence
             OR (NEW.sequence = 1 AND NEW.from_status <> 'draft')
             OR (
               NEW.sequence > 1
               AND NEW.from_status IS DISTINCT FROM previous_status
             ) THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event does not extend the event tail'
              USING ERRCODE = '23514';
          END IF;
          SELECT status
            INTO current_version_status
            FROM asset_bundle_version
           WHERE version_pk = NEW.version_pk;
          IF current_version_status IS NULL
             OR NEW.to_status <> current_version_status THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event does not match version status'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute("ALTER TABLE asset_bundle_version_event DROP COLUMN evidence_snapshot")
    op.execute("DROP FUNCTION IF EXISTS canonical_asset_registry_jsonb(JSONB)")
