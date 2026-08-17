"""Governed Content Draft registration over the canonical ``aip_artifact`` owner."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Protocol

from aos_api.aip_content_contracts import (
    ContentDraftProjection,
    ContentDraftRegisterRequest,
    ContentDraftRegistrationReceipt,
)
from aos_api.aip_content_draft_readiness import AipContentDraftReadinessService
from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_production_contracts import ContractReadiness
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class ContentDraftRegistrationError(Exception):
    code = "CONTENT_DRAFT_REGISTRATION_FAILED"


class ContentDraftRegistrationBlocked(ContentDraftRegistrationError):
    code = "CONTENT_DRAFT_REGISTRATION_BLOCKED"


class ContentDraftRegistrationConflict(ContentDraftRegistrationError):
    code = "CONTENT_DRAFT_REGISTRATION_CONFLICT"


class GovernedContentObjectVerifier(Protocol):
    def verify(self, scope: TenantScope, body: ContentDraftRegisterRequest) -> None: ...


class UnavailableContentObjectVerifier:
    def verify(self, scope: TenantScope, body: ContentDraftRegisterRequest) -> None:
        del scope, body
        raise ContentDraftRegistrationBlocked(
            "CONTENT_OBJECT_AUTHORITY_UNAVAILABLE: governed object verifier is unavailable"
        )


class AipContentDraftStore:
    def __init__(
        self,
        connect_factory=None,
        *,
        readiness_service: AipContentDraftReadinessService | None = None,
        content_verifier: GovernedContentObjectVerifier | None = None,
    ) -> None:
        self._connect = connect_factory or connect
        self._readiness = readiness_service or AipContentDraftReadinessService()
        self._content_verifier = content_verifier or UnavailableContentObjectVerifier()

    def register(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        body: ContentDraftRegisterRequest,
    ) -> ContentDraftRegistrationReceipt:
        readiness = self._readiness.evaluate(scope, body.readiness_request)
        if readiness.readiness is not ContractReadiness.READY:
            codes = ",".join(blocker.code for blocker in readiness.blockers)
            raise ContentDraftRegistrationBlocked(f"CONTENT_DRAFT_NOT_READY:{codes}")
        self._content_verifier.verify(scope, body)

        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = self._hash(payload)
        stable_hash = self._hash(
            {"tenant": scope.key, "idempotencyKey": idempotency_key}
        )
        artifact_id = f"content-draft-{stable_hash[:24]}"
        receipt_id = f"content-draft-receipt-{stable_hash[:24]}"
        operation = "content_draft.register"

        with self._connect(scope) as conn:
            replay = conn.execute(
                "SELECT request_hash,result_ref FROM aip_production_contract_receipt "
                "WHERE org_id=%s AND project_id=%s AND operation=%s "
                "AND idempotency_key=%s",
                (*scope.key, operation, idempotency_key),
            ).fetchone()
            if replay:
                if replay["request_hash"] != request_hash:
                    raise ContentDraftRegistrationConflict(
                        "idempotency key payload drifted"
                    )
                result = self._load(replay["result_ref"])
                receipt = ContentDraftRegistrationReceipt.model_validate(result)
                artifact = conn.execute(
                    "SELECT content_hash FROM aip_artifact WHERE org_id=%s "
                    "AND project_id=%s AND artifact_id=%s",
                    (*scope.key, receipt.draft.artifact_ref.artifact_id),
                ).fetchone()
                if not artifact or artifact["content_hash"] != receipt.draft.artifact_ref.content_hash:
                    raise ContentDraftRegistrationConflict(
                        "idempotent artifact authority is missing or drifted"
                    )
                return receipt

            self._require_exact_run(
                conn,
                scope,
                "aip_task_run",
                "run_id",
                body.readiness_request.task_run_ref.resource_id,
                body.readiness_request.task_run_ref.revision,
                require_running=False,
            )
            self._require_exact_run(
                conn,
                scope,
                "aip_agent_run",
                "agent_run_id",
                body.readiness_request.agent_run_ref.resource_id,
                body.readiness_request.agent_run_ref.revision,
                require_running=True,
            )
            collision = conn.execute(
                "SELECT content_hash FROM aip_artifact WHERE org_id=%s "
                "AND project_id=%s AND artifact_id=%s",
                (*scope.key, artifact_id),
            ).fetchone()
            if collision:
                raise ContentDraftRegistrationConflict(
                    "deterministic artifact id exists without matching receipt"
                )

            created_at = datetime.now(UTC)
            draft = ContentDraftProjection(
                artifactRef=ArtifactRef(
                    artifactId=artifact_id,
                    artifactType="content_draft",
                    revision="1",
                    contentHash=body.content_object.content_hash,
                ),
                briefRef=body.readiness_request.brief_ref,
                pipeline=body.readiness_request.pipeline,
                variantKey=body.readiness_request.variant_key,
                channel=body.readiness_request.channel,
                sourceAssets=body.source_assets,
                evidenceBundleRef=body.evidence_bundle_ref,
                evalReportRef=None,
                reviewIssueRefs=[],
            )
            receipt = ContentDraftRegistrationReceipt(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                receiptId=receipt_id,
                requestHash=request_hash,
                contentRef=body.content_object.content_ref,
                draft=draft,
                createdAt=created_at,
            )
            conn.execute(
                """INSERT INTO aip_artifact (
                     org_id,project_id,artifact_id,run_id,artifact_type,content_ref,
                     schema_ref,source,evidence_refs,marking,content_hash,metadata,
                     created_by,created_at)
                   VALUES (%s,%s,%s,%s,'content_draft',%s,%s,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s,%s::jsonb,%s,%s)""",
                (
                    *scope.key,
                    artifact_id,
                    body.readiness_request.task_run_ref.resource_id,
                    body.content_object.content_ref,
                    body.content_object.schema_ref.resource_id,
                    self._json(
                        {
                            "kind": "governed_content_object",
                            "agentRunRef": payload["readinessRequest"]["agentRunRef"],
                        }
                    ),
                    self._json([payload["evidenceBundleRef"]]),
                    self._json(body.content_object.marking),
                    body.content_object.content_hash,
                    self._json(
                        {
                            "briefRef": payload["readinessRequest"]["briefRef"],
                            "pipeline": payload["readinessRequest"]["pipeline"],
                            "variantKey": body.readiness_request.variant_key,
                            "channel": body.readiness_request.channel.value,
                            "promptHash": body.prompt_hash,
                            "byteSize": body.content_object.byte_size,
                            "mediaType": body.content_object.media_type,
                        }
                    ),
                    actor,
                    created_at,
                ),
            )
            conn.execute(
                """INSERT INTO aip_production_contract_receipt (
                     org_id,project_id,receipt_id,operation,idempotency_key,
                     request_hash,result_ref,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    *scope.key,
                    receipt_id,
                    operation,
                    idempotency_key,
                    request_hash,
                    self._json(receipt.model_dump(mode="json", by_alias=True)),
                    actor,
                    created_at,
                ),
            )
            conn.commit()
            return receipt

    @staticmethod
    def _require_exact_run(
        conn,
        scope: TenantScope,
        table: str,
        id_column: str,
        identifier: str,
        expected_version: str | None,
        *,
        require_running: bool,
    ) -> None:
        row = conn.execute(
            f"SELECT version,status FROM {table} WHERE org_id=%s AND project_id=%s "
            f"AND {id_column}=%s FOR SHARE",
            (*scope.key, identifier),
        ).fetchone()
        if not row or str(row["version"]) != expected_version:
            raise ContentDraftRegistrationBlocked("runtime exact ref is missing or drifted")
        if require_running and row["status"] != "running":
            raise ContentDraftRegistrationBlocked("AgentRun is not running")

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value):
        return json.loads(value) if isinstance(value, str) else value
