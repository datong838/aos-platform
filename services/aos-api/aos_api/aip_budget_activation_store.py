"""First budget activation preview and independent decision authority.

No method here publishes an active budget or grants a runtime permission.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from aos_api.aip_budget_activation_exposure import (
    BudgetActivationLedgerBlocked,
    read_initial_budget_ledger,
)
from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import canonical_hash
from aos_api.auth import Principal
from aos_api.db import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


class BudgetActivationDenied(ValueError):
    pass


class BudgetActivationConflict(ValueError):
    pass


def _identity(principal: Principal) -> tuple[TenantScope, str]:
    if (type(principal) is not Principal or principal.token_kind != "oidc"
            or type(principal.subject) is not str or not principal.subject
            or principal.subject != principal.subject.strip()):
        raise BudgetActivationDenied("BUDGET_ACTIVATION_FORMAL_IDENTITY_REQUIRED")
    return TenantScope(principal.org_id, principal.project_id), principal.subject


def _key(value: str) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 160
            or value != value.strip() or not value.isprintable()):
        raise BudgetActivationDenied("BUDGET_ACTIVATION_IDEMPOTENCY_KEY_INVALID")
    return value


def _member(conn, scope: TenantScope, subject: str, *, label: str,
            lock: bool = True) -> None:
    rows = conn.execute(
        """SELECT role FROM meta_membership
           WHERE org_id=%s AND project_id=%s AND subject=%s"""
        + (" FOR SHARE" if lock else ""),
        (*scope.key, subject),
    ).fetchall()
    if len(rows) != 1 or rows[0]["role"] not in {"owner", "admin"}:
        raise BudgetActivationDenied(f"BUDGET_ACTIVATION_{label}_MEMBERSHIP_REQUIRED")


def _replay(conn, scope: TenantScope, operation: str, key: str, request_hash: str):
    # The advisory lock serializes same-key contenders before the immutable receipt read.
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"budget-activation:{scope.org_id}:{scope.project_id}:{operation}:{key}",),
    )
    row = conn.execute(
        """SELECT request_hash,result_ref FROM aip_budget_activation_receipt
           WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
        (*scope.key, operation, key),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise BudgetActivationConflict("BUDGET_ACTIVATION_IDEMPOTENCY_DRIFT")
    return row["result_ref"]


def _receipt(conn, scope: TenantScope, operation: str, key: str, request_hash: str,
             result_ref: dict, actor: str) -> None:
    conn.execute(
        """INSERT INTO aip_budget_activation_receipt
           (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
            result_ref,actor_subject)
           VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
        (*scope.key, f"budget-receipt-{uuid4().hex}", operation, key,
         request_hash, json.dumps(result_ref, sort_keys=True), actor),
    )


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _preview_view(row) -> dict:
    return {
        "previewId": row["preview_id"], "previewHash": row["preview_hash"],
        "budgetId": row["budget_id"], "targetRevision": row["target_revision"],
        "targetHash": row["target_hash"], "expectedHeadVersion": row["expected_head_version"],
        "makerSubject": row["maker_subject"], "checkerSubject": row["checker_subject"],
        "externalUsageProven": row["external_usage_proven"],
        "activationEligible": False,
        "target": row["target_payload"],
        "internalLedgerCheckedAt": _instant(row["internal_ledger_checked_at"]),
        "expiresAt": _instant(row["expires_at"]),
    }


def _preview_hash(scope: TenantScope, row) -> str:
    return canonical_hash({
        "scope": scope.key, "budgetId": row["budget_id"],
        "draftRevision": row["draft_revision"],
        "expectedHeadVersion": row["expected_head_version"],
        "targetRevision": row["target_revision"], "targetHash": row["target_hash"],
        "makerSubject": row["maker_subject"], "checkerSubject": row["checker_subject"],
        "internalLedgerCheckedAt": _instant(row["internal_ledger_checked_at"]),
        "externalUsageProven": row["external_usage_proven"],
        "expiresAt": _instant(row["expires_at"]),
    })


def _decision_view(row) -> dict:
    return {
        "decisionId": row["decision_id"], "previewId": row["preview_id"],
        "previewHash": row["preview_hash"], "targetHash": row["target_hash"],
        "checkerSubject": row["checker_subject"], "decision": row["decision"],
        "activationEligible": False,
        "expiresAt": _instant(row["expires_at"]),
    }


def _revocation_view(row) -> dict:
    return {
        "revocationId": row["revocation_id"], "decisionId": row["decision_id"],
        "actorSubject": row["actor_subject"], "reason": row["reason"],
        "createdAt": _instant(row["created_at"]),
    }


class AipBudgetActivationStore:
    def precheck_consumption(
        self, principal: Principal, decision_id: str, *, target_hash: str,
    ) -> None:
        """Recheck an approval in one transaction; never authorize activation.

        The external bill authority and atomic consumer do not exist yet.
        Keeping this read gate separate prevents an approved Decision from
        being mistaken for a usable active BudgetRevision.
        """
        scope, maker = _identity(principal)
        if (type(decision_id) is not str or not decision_id
                or decision_id != decision_id.strip()
                or type(target_hash) is not str or len(target_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in target_hash)):
            raise BudgetActivationDenied("BUDGET_ACTIVATION_CONSUMPTION_REF_INVALID")
        with connect_serializable(scope) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"budget-activation-decision:{scope.org_id}:{scope.project_id}:{decision_id}",),
            )
            rows = conn.execute(
                """SELECT d.decision,d.preview_hash AS decision_preview_hash,
                          d.target_hash AS decision_target_hash,
                          d.checker_subject AS decision_checker,d.expires_at AS decision_expires,
                          p.*
                   FROM aip_budget_activation_decision d
                   JOIN aip_budget_activation_preview p
                     ON p.org_id=d.org_id AND p.project_id=d.project_id
                    AND p.preview_id=d.preview_id
                   WHERE d.org_id=%s AND d.project_id=%s AND d.decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchall()
            if len(rows) != 1:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_DECISION_MISSING")
            row = rows[0]
            if maker != row["maker_subject"] or maker == row["checker_subject"]:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_CONSUMER_NOT_MAKER")
            _member(conn, scope, maker, label="MAKER")
            _member(conn, scope, row["checker_subject"], label="CHECKER")
            if (row["decision"] != "approved"
                    or row["decision_checker"] != row["checker_subject"]):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_DECISION_NOT_APPROVED")
            if (_preview_hash(scope, row) != row["preview_hash"]
                    or row["decision_preview_hash"] != row["preview_hash"]
                    or canonical_hash(row["target_payload"]) != row["target_hash"]
                    or row["decision_target_hash"] != row["target_hash"]
                    or target_hash != row["target_hash"]):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_TARGET_DRIFT")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if row["expires_at"] <= now or row["decision_expires"] <= now:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_DECISION_EXPIRED")
            if conn.execute(
                """SELECT 1 FROM aip_budget_activation_revocation
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone() is not None:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_DECISION_REVOKED")
            try:
                ledger = read_initial_budget_ledger(
                    conn, scope, row["budget_id"],
                    expected_head_version=row["expected_head_version"],
                )
            except BudgetActivationLedgerBlocked as exc:
                raise BudgetActivationDenied(exc.code) from exc
            draft = conn.execute(
                """SELECT payload FROM aip_budget_revision
                   WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s""",
                (*scope.key, row["budget_id"], ledger.current_revision),
            ).fetchone()
            if draft is None or row["draft_revision"] != ledger.current_revision:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_HEAD_DRIFT")
            expected = dict(draft["payload"])
            for field in ("tenant", "contentHash", "createdBy", "createdAt"):
                expected.pop(field, None)
            expected["revision"] = row["target_revision"]
            expected["lifecycle"] = "active"
            if (row["target_revision"] != ledger.current_revision + 1
                    or canonical_hash(expected) != row["target_hash"]):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_TARGET_DRIFT")
            if row["external_usage_proven"] is not True:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_EXTERNAL_USAGE_PROOF_REQUIRED")
            # A future external bill producer must supply an exact, current
            # immutable reference and the DB writer must consume it atomically.
            raise BudgetActivationDenied("BUDGET_ACTIVATION_EXTERNAL_USAGE_AUTHORITY_UNWIRED")

    def create_preview(
        self, principal: Principal, target: BudgetRevisionCreate,
        checker_subject: str, idempotency_key: str, *, expected_head_version: int,
    ) -> dict:
        scope, maker = _identity(principal)
        key = _key(idempotency_key)
        if (type(target) is not BudgetRevisionCreate
                or target.lifecycle is not BudgetLifecycle.ACTIVE
                or type(checker_subject) is not str or not checker_subject
                or checker_subject != checker_subject.strip()
                or checker_subject == maker):
            raise BudgetActivationDenied("BUDGET_ACTIVATION_CHECKER_OR_TARGET_INVALID")
        target_payload = target.model_dump(mode="json", by_alias=True)
        target_hash = canonical_hash(target_payload)
        request_hash = canonical_hash({"target": target_payload, "checker": checker_subject,
                                       "headVersion": expected_head_version, "maker": maker})
        with connect_serializable(scope) as conn:
            _member(conn, scope, maker, label="MAKER")
            _member(conn, scope, checker_subject, label="CHECKER")
            replay = _replay(conn, scope, "preview", key, request_hash)
            if replay is not None:
                row = conn.execute(
                    """SELECT * FROM aip_budget_activation_preview
                       WHERE org_id=%s AND project_id=%s AND preview_id=%s""",
                    (*scope.key, replay["previewId"]),
                ).fetchone()
                if row is None:
                    raise BudgetActivationConflict("BUDGET_ACTIVATION_RECEIPT_DRIFT")
                return _preview_view(row)
            try:
                ledger = read_initial_budget_ledger(
                    conn, scope, target.budget_id,
                    expected_head_version=expected_head_version,
                )
            except BudgetActivationLedgerBlocked as exc:
                raise BudgetActivationDenied(exc.code) from exc
            if target.revision != ledger.current_revision + 1:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_TARGET_REVISION_DRIFT")
            draft_row = conn.execute(
                """SELECT payload FROM aip_budget_revision
                   WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s""",
                (*scope.key, target.budget_id, ledger.current_revision),
            ).fetchone()
            if draft_row is None:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_DRAFT_MISSING")
            draft_payload = dict(draft_row["payload"])
            for field in ("tenant", "contentHash", "createdBy", "createdAt"):
                draft_payload.pop(field, None)
            draft_payload["revision"] = target.revision
            draft_payload["lifecycle"] = "active"
            if canonical_hash(draft_payload) != target_hash:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_TARGET_DRIFT")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if not target.effective_from <= now < target.effective_until:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_WINDOW_INVALID")
            expires_at = min(target.effective_until, now + timedelta(minutes=30))
            preview_content = {
                "scope": scope.key, "budgetId": target.budget_id,
                "draftRevision": ledger.current_revision,
                "expectedHeadVersion": expected_head_version,
                "targetRevision": target.revision, "targetHash": target_hash,
                "makerSubject": maker, "checkerSubject": checker_subject,
                "internalLedgerCheckedAt": _instant(ledger.checked_at),
                "externalUsageProven": False, "expiresAt": _instant(expires_at),
            }
            preview_id = f"budget-preview-{uuid4().hex}"
            inserted = conn.execute(
                """INSERT INTO aip_budget_activation_preview
                   (org_id,project_id,preview_id,budget_id,draft_revision,
                    expected_head_version,target_revision,target_hash,target_payload,
                    preview_hash,maker_subject,checker_subject,internal_ledger_checked_at,
                    external_usage_proven,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (*scope.key, preview_id, target.budget_id, ledger.current_revision,
                 expected_head_version, target.revision, target_hash,
                 json.dumps(target_payload, sort_keys=True), canonical_hash(preview_content),
                 maker, checker_subject, ledger.checked_at, False, expires_at),
            ).fetchone()
            view = _preview_view(inserted)
            _receipt(conn, scope, "preview", key, request_hash,
                     {"previewId": preview_id, "previewHash": view["previewHash"]}, maker)
            conn.commit()
            return view

    def get_preview(self, principal: Principal, preview_id: str) -> dict:
        scope, actor = _identity(principal)
        if type(preview_id) is not str or not preview_id or preview_id != preview_id.strip():
            raise BudgetActivationDenied("BUDGET_ACTIVATION_PREVIEW_ID_INVALID")
        with connect_read_only(scope) as conn:
            row = conn.execute(
                """SELECT * FROM aip_budget_activation_preview
                   WHERE org_id=%s AND project_id=%s AND preview_id=%s""",
                (*scope.key, preview_id),
            ).fetchone()
            if row is None or actor not in {row["maker_subject"], row["checker_subject"]}:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_REVIEWER_INVALID")
            _member(conn, scope, actor, label="REVIEWER", lock=False)
            if (_preview_hash(scope, row) != row["preview_hash"]
                    or canonical_hash(row["target_payload"]) != row["target_hash"]):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_PREVIEW_DRIFT")
            return _preview_view(row)

    def decide(self, principal: Principal, preview_id: str, idempotency_key: str,
               *, decision: str) -> dict:
        scope, checker = _identity(principal)
        key = _key(idempotency_key)
        if (type(preview_id) is not str or not preview_id or preview_id != preview_id.strip()
                or decision not in {"approved", "rejected"}):
            raise BudgetActivationDenied("BUDGET_ACTIVATION_DECISION_INVALID")
        request_hash = canonical_hash({"previewId": preview_id, "decision": decision,
                                       "checker": checker})
        with connect_serializable(scope) as conn:
            _member(conn, scope, checker, label="CHECKER")
            replay = _replay(conn, scope, "decision", key, request_hash)
            if replay is not None:
                row = conn.execute(
                    """SELECT * FROM aip_budget_activation_decision
                       WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                    (*scope.key, replay["decisionId"]),
                ).fetchone()
                if row is None:
                    raise BudgetActivationConflict("BUDGET_ACTIVATION_RECEIPT_DRIFT")
                return _decision_view(row)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"budget-activation-preview:{scope.org_id}:{scope.project_id}:{preview_id}",),
            )
            preview = conn.execute(
                """SELECT * FROM aip_budget_activation_preview
                   WHERE org_id=%s AND project_id=%s AND preview_id=%s""",
                (*scope.key, preview_id),
            ).fetchone()
            if (preview is None or checker != preview["checker_subject"]
                    or checker == preview["maker_subject"]):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_CHECKER_INVALID")
            if (_preview_hash(scope, preview) != preview["preview_hash"]
                    or canonical_hash(preview["target_payload"]) != preview["target_hash"]):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_PREVIEW_DRIFT")
            _member(conn, scope, preview["maker_subject"], label="MAKER")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if preview["expires_at"] <= now:
                raise BudgetActivationDenied("BUDGET_ACTIVATION_PREVIEW_EXPIRED")
            try:
                read_initial_budget_ledger(
                    conn, scope, preview["budget_id"],
                    expected_head_version=preview["expected_head_version"],
                )
            except BudgetActivationLedgerBlocked as exc:
                raise BudgetActivationDenied(exc.code) from exc
            existing = conn.execute(
                """SELECT 1 FROM aip_budget_activation_decision
                   WHERE org_id=%s AND project_id=%s AND preview_id=%s""",
                (*scope.key, preview_id),
            ).fetchone()
            if existing is not None:
                raise BudgetActivationConflict("BUDGET_ACTIVATION_ALREADY_DECIDED")
            decision_id = f"budget-decision-{uuid4().hex}"
            expires_at = min(preview["expires_at"], now + timedelta(minutes=15))
            conn.execute(
                """INSERT INTO aip_budget_activation_decision
                   (org_id,project_id,decision_id,preview_id,preview_hash,target_hash,
                    checker_subject,decision,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, decision_id, preview_id, preview["preview_hash"],
                 preview["target_hash"], checker, decision, expires_at),
            )
            view = {"decisionId": decision_id, "previewId": preview_id,
                    "previewHash": preview["preview_hash"], "targetHash": preview["target_hash"],
                    "checkerSubject": checker, "decision": decision,
                    "activationEligible": False, "expiresAt": _instant(expires_at)}
            _receipt(conn, scope, "decision", key, request_hash,
                     {"decisionId": decision_id}, checker)
            conn.commit()
            return view

    def revoke(self, principal: Principal, decision_id: str, idempotency_key: str,
               *, reason: str) -> dict:
        scope, actor = _identity(principal)
        key = _key(idempotency_key)
        if (type(decision_id) is not str or not decision_id or decision_id != decision_id.strip()
                or type(reason) is not str or not reason.strip() or reason != reason.strip()
                or len(reason) > 500):
            raise BudgetActivationDenied("BUDGET_ACTIVATION_REVOCATION_INVALID")
        request_hash = canonical_hash({"decisionId": decision_id, "reason": reason,
                                       "actor": actor})
        with connect_serializable(scope) as conn:
            _member(conn, scope, actor, label="REVOKER")
            replay = _replay(conn, scope, "revoke", key, request_hash)
            if replay is not None:
                row = conn.execute(
                    """SELECT * FROM aip_budget_activation_revocation
                       WHERE org_id=%s AND project_id=%s AND revocation_id=%s""",
                    (*scope.key, replay["revocationId"]),
                ).fetchone()
                if row is None:
                    raise BudgetActivationConflict("BUDGET_ACTIVATION_RECEIPT_DRIFT")
                return _revocation_view(row)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"budget-activation-decision:{scope.org_id}:{scope.project_id}:{decision_id}",),
            )
            row = conn.execute(
                """SELECT d.decision,d.decision_id,p.maker_subject,p.checker_subject
                   FROM aip_budget_activation_decision d
                   JOIN aip_budget_activation_preview p
                     ON p.org_id=d.org_id AND p.project_id=d.project_id
                    AND p.preview_id=d.preview_id
                   WHERE d.org_id=%s AND d.project_id=%s AND d.decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone()
            if (row is None or row["decision"] != "approved"
                    or actor not in {row["maker_subject"], row["checker_subject"]}):
                raise BudgetActivationDenied("BUDGET_ACTIVATION_REVOKER_INVALID")
            if conn.execute(
                """SELECT 1 FROM aip_budget_activation_revocation
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone() is not None:
                raise BudgetActivationConflict("BUDGET_ACTIVATION_ALREADY_REVOKED")
            revocation_id = f"budget-revocation-{uuid4().hex}"
            result = conn.execute(
                """INSERT INTO aip_budget_activation_revocation
                   (org_id,project_id,revocation_id,decision_id,actor_subject,reason)
                   VALUES(%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (*scope.key, revocation_id, decision_id, actor, reason),
            ).fetchone()
            _receipt(conn, scope, "revoke", key, request_hash,
                     {"revocationId": revocation_id}, actor)
            conn.commit()
            return _revocation_view(result)
