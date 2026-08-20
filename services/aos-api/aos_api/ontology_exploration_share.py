"""SavedExploration ShareGrant authority (W-L16 / W4-06)."""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_exploration_assets import get_asset
from aos_api.ontology_operational_authority import canonical_hash
from aos_api.tenant_scope import TenantScope

GranteeScope = Literal["workspace", "link"]
GrantStatus = Literal["active", "expired", "revoked"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CreateShareGrantRequest(StrictModel):
    expires_at: datetime = Field(alias="expiresAt")
    grantee_scope: GranteeScope = Field(default="link", alias="granteeScope")
    purpose: str = Field(default="exploration_read", min_length=1, max_length=120)
    markings: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("expires_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("expiresAt must be timezone-aware")
        return value


class RevokeShareGrantRequest(StrictModel):
    expected_version: int = Field(ge=1, alias="expectedVersion")
    reason: str = Field(default="revoked_by_owner", min_length=1, max_length=500)


class ShareGrantView(StrictModel):
    tenant: dict[str, str]
    grant_id: str = Field(alias="grantId")
    opaque_ref: str = Field(alias="opaqueRef")
    asset_id: str = Field(alias="assetId")
    asset_revision: int = Field(alias="assetRevision", ge=1)
    asset_payload_hash: str = Field(alias="assetPayloadHash", pattern=r"^[0-9a-f]{64}$")
    grantor_subject: str = Field(alias="grantorSubject")
    grantee_scope: GranteeScope = Field(alias="granteeScope")
    purpose: str
    markings: list[str]
    status: GrantStatus
    issued_at: datetime = Field(alias="issuedAt")
    expires_at: datetime = Field(alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    revoke_reason: str | None = Field(default=None, alias="revokeReason")
    version: int = Field(ge=1)
    blocker: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _view(scope: TenantScope, row: Any, *, blocker: str | None = None) -> ShareGrantView:
    status = row["status"]
    now = _now()
    if status == "active" and row["expires_at"] <= now:
        status = "expired"
        blocker = blocker or "share_grant_expired"
    return ShareGrantView(
        tenant={"orgId": scope.org_id, "projectId": scope.project_id},
        grant_id=row["grant_id"],
        opaque_ref=row["opaque_ref"],
        asset_id=row["asset_id"],
        asset_revision=int(row["asset_revision"]),
        asset_payload_hash=row["asset_payload_hash"],
        grantor_subject=row["grantor_subject"],
        grantee_scope=row["grantee_scope"],
        purpose=row["purpose"],
        markings=list(row["markings"] or []),
        status=status,
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        revoke_reason=row["revoke_reason"],
        version=int(row["version"]),
        blocker=blocker,
    )


def create_share_grant(
    scope: TenantScope,
    *,
    asset_id: str,
    actor: str,
    body: CreateShareGrantRequest,
    idempotency_key: str,
    expected_revision: int,
) -> ShareGrantView:
    if body.expires_at <= _now():
        raise ApiError(
            code="SHARE_GRANT_EXPIRED_INPUT",
            message="share grant expiry must be in the future",
            status_code=400,
        )
    current = get_asset(scope, kind="exploration", asset_id=asset_id, actor=actor)
    if current is None:
        raise ApiError(
            code="EXPLORATION_NOT_FOUND",
            message="exploration not found",
            status_code=404,
        )
    asset, _etag = current
    if int(asset["revision"]) != expected_revision:
        raise ApiError(
            code="REVISION_CONFLICT",
            message="exploration revision changed",
            status_code=412,
            details={"expected": expected_revision, "actual": asset["revision"]},
        )
    if asset.get("archived"):
        raise ApiError(
            code="EXPLORATION_ARCHIVED",
            message="archived exploration cannot be shared",
            status_code=409,
        )
    if asset["owner"] != actor:
        raise ApiError(
            code="SHARE_GRANT_FORBIDDEN",
            message="only the asset owner may create share grants",
            status_code=403,
        )
    payload = {
        "assetId": asset_id,
        "assetRevision": expected_revision,
        "expiresAt": body.expires_at.isoformat(),
        "granteeScope": body.grantee_scope,
        "purpose": body.purpose,
        "markings": body.markings,
    }
    request_hash = canonical_hash(
        {"scope": scope.key, "command": "create", "actor": actor, "payload": payload}
    )
    with connect(scope) as conn:
        receipt = conn.execute(
            """SELECT request_hash, grant_id FROM ontology_exploration_share_grant_receipt
               WHERE org_id=%s AND workspace_id=%s AND command='create'
                 AND idempotency_key=%s""",
            (*scope.key, idempotency_key),
        ).fetchone()
        if receipt is not None:
            if receipt["request_hash"] != request_hash:
                raise ApiError(
                    code="IDEMPOTENCY_CONFLICT",
                    message="share grant idempotency key reused with different payload",
                    status_code=409,
                )
            replay = conn.execute(
                """SELECT * FROM ontology_exploration_share_grant
                   WHERE org_id=%s AND workspace_id=%s AND grant_id=%s""",
                (*scope.key, receipt["grant_id"]),
            ).fetchone()
            return _view(scope, replay)

        grant_id = f"share-grant-{uuid.uuid4().hex[:20]}"
        opaque_ref = secrets.token_urlsafe(24)
        issued_at = _now()
        conn.execute(
            """INSERT INTO ontology_exploration_share_grant
               (org_id,workspace_id,grant_id,opaque_ref,asset_id,asset_revision,
                asset_payload_hash,grantor_subject,grantee_scope,purpose,markings,
                status,issued_at,expires_at,version)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'active',%s,%s,1)""",
            (
                *scope.key,
                grant_id,
                opaque_ref,
                asset_id,
                expected_revision,
                asset["payloadHash"],
                actor,
                body.grantee_scope,
                body.purpose,
                _json(body.markings),
                issued_at,
                body.expires_at,
            ),
        )
        conn.execute(
            """INSERT INTO ontology_exploration_share_grant_receipt
               (org_id,workspace_id,receipt_id,grant_id,command,idempotency_key,
                request_hash,actor)
               VALUES(%s,%s,%s,%s,'create',%s,%s,%s)""",
            (
                *scope.key,
                f"share-receipt-{uuid.uuid4().hex[:20]}",
                grant_id,
                idempotency_key,
                request_hash,
                actor,
            ),
        )
        row = conn.execute(
            """SELECT * FROM ontology_exploration_share_grant
               WHERE org_id=%s AND workspace_id=%s AND grant_id=%s""",
            (*scope.key, grant_id),
        ).fetchone()
        conn.commit()
        return _view(scope, row)


def revoke_share_grant(
    scope: TenantScope,
    *,
    opaque_ref: str,
    actor: str,
    body: RevokeShareGrantRequest,
    idempotency_key: str,
) -> ShareGrantView:
    request_hash = canonical_hash(
        {
            "scope": scope.key,
            "command": "revoke",
            "opaqueRef": opaque_ref,
            "expectedVersion": body.expected_version,
            "reason": body.reason,
            "actor": actor,
        }
    )
    with connect(scope) as conn:
        receipt = conn.execute(
            """SELECT request_hash,grant_id FROM ontology_exploration_share_grant_receipt
               WHERE org_id=%s AND workspace_id=%s AND command='revoke'
                 AND idempotency_key=%s""",
            (*scope.key, idempotency_key),
        ).fetchone()
        if receipt is not None:
            if receipt["request_hash"] != request_hash:
                raise ApiError(
                    code="IDEMPOTENCY_CONFLICT",
                    message="revoke idempotency key reused with different payload",
                    status_code=409,
                )
            row = conn.execute(
                """SELECT * FROM ontology_exploration_share_grant
                   WHERE org_id=%s AND workspace_id=%s AND grant_id=%s""",
                (*scope.key, receipt["grant_id"]),
            ).fetchone()
            return _view(scope, row, blocker="share_grant_revoked")

        row = conn.execute(
            """SELECT * FROM ontology_exploration_share_grant
               WHERE org_id=%s AND workspace_id=%s AND opaque_ref=%s
               FOR UPDATE""",
            (*scope.key, opaque_ref),
        ).fetchone()
        if row is None:
            raise ApiError(
                code="SHARE_GRANT_NOT_FOUND",
                message="share grant not found",
                status_code=404,
            )
        if row["grantor_subject"] != actor:
            raise ApiError(
                code="SHARE_GRANT_FORBIDDEN",
                message="only the grantor may revoke",
                status_code=403,
            )
        if int(row["version"]) != body.expected_version:
            raise ApiError(
                code="VERSION_CONFLICT",
                message="share grant version changed",
                status_code=412,
            )
        if row["status"] == "revoked":
            return _view(scope, row, blocker="share_grant_revoked")
        revoked_at = _now()
        conn.execute(
            """UPDATE ontology_exploration_share_grant
               SET status='revoked', revoked_at=%s, revoke_reason=%s, version=version+1
               WHERE org_id=%s AND workspace_id=%s AND grant_id=%s AND version=%s""",
            (revoked_at, body.reason, *scope.key, row["grant_id"], body.expected_version),
        )
        conn.execute(
            """INSERT INTO ontology_exploration_share_grant_receipt
               (org_id,workspace_id,receipt_id,grant_id,command,idempotency_key,
                request_hash,actor)
               VALUES(%s,%s,%s,%s,'revoke',%s,%s,%s)""",
            (
                *scope.key,
                f"share-receipt-{uuid.uuid4().hex[:20]}",
                row["grant_id"],
                idempotency_key,
                request_hash,
                actor,
            ),
        )
        updated = conn.execute(
            """SELECT * FROM ontology_exploration_share_grant
               WHERE org_id=%s AND workspace_id=%s AND grant_id=%s""",
            (*scope.key, row["grant_id"]),
        ).fetchone()
        conn.commit()
        return _view(scope, updated, blocker="share_grant_revoked")


def resolve_share_grant(scope: TenantScope, opaque_ref: str) -> ShareGrantView:
    with connect(scope) as conn:
        row = conn.execute(
            """SELECT * FROM ontology_exploration_share_grant
               WHERE org_id=%s AND workspace_id=%s AND opaque_ref=%s""",
            (*scope.key, opaque_ref),
        ).fetchone()
    if row is None:
        raise ApiError(
            code="SHARE_GRANT_NOT_FOUND",
            message="share grant not found",
            status_code=404,
        )
    if row["status"] == "revoked":
        raise ApiError(
            code="SHARE_GRANT_REVOKED",
            message="share grant revoked",
            status_code=410,
        )
    if row["expires_at"] <= _now():
        raise ApiError(
            code="SHARE_GRANT_EXPIRED",
            message="share grant expired",
            status_code=410,
        )
    # Re-verify exact exploration revision/hash and not archived
    head = None
    with connect(scope) as conn:
        head = conn.execute(
            """SELECT h.archived_at,h.owner_subject,r.revision,r.payload_hash
               FROM ontology_exploration_asset_head h
               JOIN ontology_exploration_asset_revision r
                 ON r.org_id=h.org_id AND r.workspace_id=h.workspace_id
                AND r.asset_id=h.asset_id AND r.revision=h.active_revision
               WHERE h.org_id=%s AND h.workspace_id=%s AND h.asset_id=%s""",
            (*scope.key, row["asset_id"]),
        ).fetchone()
    if head is None:
        raise ApiError(
            code="SHARE_GRANT_ASSET_MISSING",
            message="shared exploration missing",
            status_code=410,
        )
    if head["archived_at"] is not None:
        raise ApiError(
            code="SHARE_GRANT_ASSET_ARCHIVED",
            message="shared exploration archived",
            status_code=410,
        )
    if int(head["revision"]) != int(row["asset_revision"]) or head["payload_hash"] != row[
        "asset_payload_hash"
    ]:
        raise ApiError(
            code="SHARE_GRANT_HASH_DRIFTED",
            message="shared exploration revision drifted",
            status_code=409,
        )
    return _view(scope, row)
