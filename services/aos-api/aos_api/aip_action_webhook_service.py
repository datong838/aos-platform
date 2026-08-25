"""Canonical Action webhook ingress: verify, deduplicate, bind and reduce."""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_action_webhook_models import (
    ActionWebhookInboxSnapshot,
    ActionWebhookObservationSnapshot,
    ActionWebhookReducerView,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class ActionWebhookError(Exception):
    code = "ACTION_WEBHOOK_REJECTED"
    status_code = 422


class ActionWebhookNotFound(ActionWebhookError):
    code = "ACTION_WEBHOOK_ENDPOINT_UNAVAILABLE"
    status_code = 404


class ActionWebhookUnauthorized(ActionWebhookError):
    code = "ACTION_WEBHOOK_VERIFICATION_FAILED"
    status_code = 401


class ActionWebhookTooLarge(ActionWebhookError):
    code = "ACTION_WEBHOOK_BODY_TOO_LARGE"
    status_code = 413


SecretResolver = Callable[[TenantScope, str, str], bytes]


def _unconfigured_secret_resolver(_scope: TenantScope, _secret_ref: str, _key_revision: str) -> bytes:
    raise ActionWebhookUnauthorized("webhook key resolver is unavailable")


class AipActionWebhookService:
    def __init__(self, secret_resolver: SecretResolver = _unconfigured_secret_resolver) -> None:
        self._secret_resolver = secret_resolver

    def receive(
        self,
        endpoint_key: str,
        headers: Mapping[str, str],
        body: bytes,
        *,
        received_at: datetime | None = None,
    ) -> ActionWebhookInboxSnapshot:
        received_at = received_at or datetime.now(timezone.utc)
        directory = self._resolve_directory(endpoint_key)
        scope = TenantScope(directory["org_id"], directory["project_id"])
        endpoint = self._load_endpoint(scope, directory)
        normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
        body_hash = hashlib.sha256(body).hexdigest()
        headers_hash = canonical_hash({
            key: normalized_headers.get(key)
            for key in sorted(set(endpoint["signature_policy"].get("signedHeaders") or []))
        })
        if len(body) > endpoint["max_body_bytes"]:
            snapshot = self._reject(
                scope, endpoint, body_hash, headers_hash, received_at, "body_too_large"
            )
            raise ActionWebhookTooLarge(snapshot.id)
        try:
            nonce, key_revision = self._verify(
                scope, endpoint, normalized_headers, body_hash, received_at
            )
        except ActionWebhookUnauthorized as exc:
            snapshot = self._reject(
                scope, endpoint, body_hash, headers_hash, received_at, "signature_rejected"
            )
            raise ActionWebhookUnauthorized(snapshot.id) from exc

        # JSON parsing is deliberately after body limit and signature verification.
        schema_reason: str | None = None
        try:
            event = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            event = None
            schema_reason = "INVALID_JSON_AFTER_VERIFICATION"
        if not isinstance(event, dict):
            schema_reason = schema_reason or "EVENT_MUST_BE_OBJECT"
        provider_event_id = (
            str(event.get("providerEventId") or "") if isinstance(event, dict) else ""
        )
        event_key = provider_event_id or nonce
        if isinstance(event, dict) and not self._schema_valid(endpoint["event_schema"], event):
            schema_reason = "EVENT_SCHEMA_DRIFT"

        # Serialize one endpoint/event key without committing a replay claim ahead
        # of its immutable receipt. This prevents an orphan claim and also makes
        # same-key/different-body races fail closed.
        with self._replay_lock(scope, endpoint["endpoint_id"], event_key):
            existing = self._find_replay(scope, endpoint, event_key)
            if existing is not None:
                if existing["body_hash"] == body_hash:
                    return self._snapshot(
                        scope, existing["receipt_id"], replay_override="duplicate"
                    )
                return self._quarantine(
                    scope, endpoint, body_hash, headers_hash, received_at,
                    provider_event_id=provider_event_id or None, event_key=event_key,
                    case_type="replay_drift", reason_code="REPLAY_KEY_BODY_DRIFT",
                    replay_status="drift",
                )
            if schema_reason is not None:
                result = self._quarantine(
                    scope, endpoint, body_hash, headers_hash, received_at,
                    provider_event_id=provider_event_id or None, event_key=event_key,
                    case_type="schema_drift", reason_code=schema_reason,
                )
            else:
                assert isinstance(event, dict)
                result = self._accept_verified(
                    scope, endpoint, body_hash, headers_hash, received_at,
                    provider_event_id, event_key, event, key_revision,
                )
            self._record_replay(
                scope, endpoint, event_key, body_hash, result.id, received_at
            )
            return result

    @staticmethod
    def _resolve_directory(endpoint_key: str) -> Any:
        with connect(inherit_scope=False) as conn:
            row = conn.execute(
                """SELECT * FROM aip_action_webhook_endpoint_directory
                   WHERE endpoint_key=%s AND status='active'""",
                (endpoint_key,),
            ).fetchone()
        if row is None:
            raise ActionWebhookNotFound("webhook endpoint is unavailable")
        return row

    @staticmethod
    def _load_endpoint(scope: TenantScope, directory: Any) -> Any:
        with connect(scope) as conn:
            row = conn.execute(
                """SELECT * FROM aip_action_webhook_endpoint_revision
                   WHERE org_id=%s AND project_id=%s AND endpoint_id=%s AND revision=%s
                     AND lifecycle='published' AND valid_from<=NOW()
                     AND (expires_at IS NULL OR expires_at>NOW())""",
                (*scope.key, directory["endpoint_id"], directory["active_revision"]),
            ).fetchone()
        if row is None:
            raise ActionWebhookNotFound("webhook endpoint is unavailable")
        return row

    def _verify(
        self,
        scope: TenantScope,
        endpoint: Any,
        headers: Mapping[str, str],
        body_hash: str,
        received_at: datetime,
    ) -> tuple[str, str]:
        policy = endpoint["signature_policy"]
        if policy.get("algorithm") != "hmac-sha256":
            raise ActionWebhookUnauthorized("unsupported signature algorithm")
        timestamp_header = str(policy.get("timestampHeader") or "x-aos-timestamp").lower()
        nonce_header = str(policy.get("nonceHeader") or "x-aos-nonce").lower()
        signature_header = str(policy.get("signatureHeader") or "x-aos-signature").lower()
        key_header = str(policy.get("keyRevisionHeader") or "x-aos-key-revision").lower()
        timestamp_value = headers.get(timestamp_header, "")
        nonce = headers.get(nonce_header, "")
        signature = headers.get(signature_header, "")
        key_revision = headers.get(key_header, "")
        if not timestamp_value or not nonce or not signature or not key_revision:
            raise ActionWebhookUnauthorized("required signature headers are missing")
        allowed_keys = {str(item) for item in policy.get("allowedKeyRevisions") or []}
        if allowed_keys and key_revision not in allowed_keys:
            raise ActionWebhookUnauthorized("key revision is unavailable")
        try:
            timestamp = int(timestamp_value)
        except ValueError as exc:
            raise ActionWebhookUnauthorized("invalid callback timestamp") from exc
        max_skew = int(policy.get("maxSkewSeconds") or 300)
        if abs(int(received_at.timestamp()) - timestamp) > max_skew:
            raise ActionWebhookUnauthorized("callback timestamp is outside the allowed window")
        secret = self._secret_resolver(scope, endpoint["secret_ref"], key_revision)
        signed_headers = [
            str(item).lower()
            for item in policy.get("signedHeaders")
            or [timestamp_header, nonce_header, key_header]
        ]
        canonical_headers = "\n".join(
            f"{name}:{headers.get(name, '')}" for name in sorted(set(signed_headers))
        )
        signed = f"{canonical_headers}\nbody-sha256:{body_hash}".encode()
        expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ActionWebhookUnauthorized("callback signature is invalid")
        return nonce, key_revision

    @staticmethod
    def _schema_valid(schema: dict[str, Any], event: dict[str, Any]) -> bool:
        required = set(schema.get("required") or [
            "providerEventId", "providerRequestId", "eventType", "providerOutcome"
        ])
        if not required.issubset(event):
            return False
        if any(not isinstance(event.get(field), str) or not event[field].strip() for field in required):
            return False
        allowed_outcomes = set(schema.get("allowedOutcomes") or [
            "accepted", "applied", "failed", "partial", "unknown"
        ])
        if event.get("providerOutcome") not in allowed_outcomes:
            return False
        allowed_types = set(schema.get("allowedEventTypes") or [])
        if allowed_types and event.get("eventType") not in allowed_types:
            return False
        sequence = event.get("providerSequence")
        if sequence is not None and (
            isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1
        ):
            return False
        event_at = event.get("providerEventAt")
        return event_at is None or AipActionWebhookService._parse_datetime(event_at) is not None

    @staticmethod
    @contextmanager
    def _replay_lock(
        scope: TenantScope, endpoint_id: str, event_key: str
    ) -> Iterator[None]:
        lock_key = f"aip-action-webhook:{scope.org_id}:{scope.project_id}:{endpoint_id}:{event_key}"
        with connect(scope) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
            try:
                yield
            finally:
                conn.commit()

    @staticmethod
    def _find_replay(scope: TenantScope, endpoint: Any, event_key: str) -> Any | None:
        with connect(scope) as conn:
            return conn.execute(
                """SELECT body_hash,receipt_id FROM aip_action_webhook_replay_key
                   WHERE org_id=%s AND project_id=%s AND endpoint_id=%s AND event_key=%s""",
                (*scope.key, endpoint["endpoint_id"], event_key),
            ).fetchone()

    @staticmethod
    def _record_replay(
        scope: TenantScope, endpoint: Any, event_key: str, body_hash: str,
        receipt_id: str, received_at: datetime,
    ) -> None:
        with connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_action_webhook_replay_key
                   (org_id,project_id,endpoint_id,event_key,body_hash,receipt_id,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, endpoint["endpoint_id"], event_key, body_hash,
                 receipt_id, received_at),
            )
            conn.commit()

    def _accept_verified(
        self, scope: TenantScope, endpoint: Any, body_hash: str, headers_hash: str,
        received_at: datetime, provider_event_id: str, event_key: str,
        event: dict[str, Any], key_revision: str,
    ) -> ActionWebhookInboxSnapshot:
        matches = self._match_attempt(scope, endpoint, event)
        if len(matches) != 1:
            return self._quarantine(
                scope, endpoint, body_hash, headers_hash, received_at,
                provider_event_id=provider_event_id, event_key=event_key,
                case_type="unmatched" if not matches else "multi_match",
                reason_code="ATTEMPT_NOT_EXACTLY_RESOLVED",
            )
        match = matches[0]
        event_binding = event.get("actionBindingHash")
        if event_binding and event_binding != match["action_binding_hash"]:
            return self._quarantine(
                scope, endpoint, body_hash, headers_hash, received_at,
                provider_event_id=provider_event_id, event_key=event_key,
                case_type="binding_drift", reason_code="ACTION_BINDING_HASH_DRIFT",
            )
        receipt_id = self._id("webhook-receipt", endpoint["endpoint_id"], event_key, body_hash)
        observation_id = self._id("webhook-observation", match["attempt_id"], provider_event_id)
        provider_event_at = self._parse_datetime(event.get("providerEventAt"))
        provider_sequence = event.get("providerSequence")
        if provider_sequence is not None and (
            isinstance(provider_sequence, bool)
            or not isinstance(provider_sequence, int)
            or provider_sequence < 1
        ):
            return self._quarantine(
                scope, endpoint, body_hash, headers_hash, received_at,
                provider_event_id=provider_event_id, event_key=event_key,
                case_type="schema_drift", reason_code="INVALID_PROVIDER_SEQUENCE",
            )
        source_fact = {
            "endpointId": endpoint["endpoint_id"], "endpointRevision": endpoint["revision"],
            "bodyHash": body_hash, "headersHash": headers_hash,
            "providerEventId": provider_event_id, "attemptId": match["attempt_id"],
            "keyRevision": key_revision,
        }
        with connect(scope) as conn:
            self._insert_receipt(
                conn, scope, endpoint, receipt_id, body_hash, headers_hash, received_at,
                "verified", "signature_valid", "new", "accepted",
                provider_event_id, event_key, canonical_hash(source_fact), None,
            )
            conn.execute(
                """INSERT INTO aip_action_webhook_observation
                   (org_id,project_id,observation_id,receipt_id,attempt_id,provider_event_id,
                    event_type,provider_outcome,provider_sequence,provider_event_at,
                    payload_hash,adapter_schema_ref,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT (org_id,project_id,attempt_id,provider_event_id) DO NOTHING""",
                (*scope.key, observation_id, receipt_id, match["attempt_id"], provider_event_id,
                 str(event["eventType"]), str(event["providerOutcome"]), provider_sequence,
                 provider_event_at, body_hash, json.dumps({
                     "adapterRevisionRef": endpoint["adapter_revision_ref"],
                     "endpointRevision": endpoint["revision"],
                     "schemaHash": canonical_hash(endpoint["event_schema"]),
                 }), received_at),
            )
            conn.commit()
        reducer = self._reduce(scope, match["attempt_id"], receipt_id)
        return self._snapshot(scope, receipt_id, reducer_override=reducer)

    @staticmethod
    def _match_attempt(scope: TenantScope, endpoint: Any, event: dict[str, Any]) -> list[Any]:
        provider_request_id = str(event.get("providerRequestId") or "")
        with connect(scope) as conn:
            return conn.execute(
                """SELECT r.receipt_id,r.attempt_id,r.action_binding_hash
                   FROM aip_action_receipt r
                   WHERE r.org_id=%s AND r.project_id=%s AND r.receipt_kind='initial'
                     AND r.provider_request_id=%s AND r.account_binding_ref=%s::jsonb""",
                (*scope.key, provider_request_id, json.dumps(endpoint["account_binding_ref"])),
            ).fetchall()

    def _reduce(
        self, scope: TenantScope, attempt_id: str, source_receipt_id: str
    ) -> ActionWebhookReducerView:
        with connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_action_webhook_observation
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s
                   ORDER BY provider_event_at NULLS LAST,created_at,provider_event_id""",
                (*scope.key, attempt_id),
            ).fetchall()
            sequence_groups: dict[int, list[Any]] = {}
            for row in rows:
                if row["provider_sequence"] is not None:
                    sequence_groups.setdefault(int(row["provider_sequence"]), []).append(row)
            sequenced = {number: group[0] for number, group in sequence_groups.items()}
            sequence_conflict = any(
                len({row["provider_outcome"] for row in group}) > 1
                for group in sequence_groups.values()
            )
            highest = max(sequenced, default=0)
            missing = [number for number in range(1, highest + 1) if number not in sequenced]
            contiguous = 0
            while contiguous + 1 in sequenced:
                contiguous += 1
            considered = (
                [sequenced[number] for number in range(1, contiguous + 1)]
                if sequenced else list(rows)
            )
            terminal = {row["provider_outcome"] for row in considered
                        if row["provider_outcome"] in {"applied", "failed", "partial"}}
            conflict = sequence_conflict or (
                "failed" in terminal and bool(terminal.intersection({"applied", "partial"}))
            )
            if conflict:
                status, outcome = "disputed", None
            elif missing:
                status = "awaiting_gap"
                outcome = considered[-1]["provider_outcome"] if considered else None
            elif terminal:
                outcome = "partial" if "partial" in terminal else next(iter(terminal))
                status = outcome
            else:
                status = "pending"
                outcome = considered[-1]["provider_outcome"] if considered else None
            existing = conn.execute(
                """SELECT version FROM aip_action_webhook_reducer_view
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (*scope.key, attempt_id),
            ).fetchone()
            version = int(existing["version"]) + 1 if existing else 1
            conn.execute(
                """INSERT INTO aip_action_webhook_reducer_view
                   (org_id,project_id,attempt_id,status,provider_outcome,
                    latest_contiguous_sequence,highest_observed_sequence,missing_sequences,
                    observation_count,version,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,NOW())
                   ON CONFLICT (org_id,project_id,attempt_id) DO UPDATE SET
                     status=EXCLUDED.status,provider_outcome=EXCLUDED.provider_outcome,
                     latest_contiguous_sequence=EXCLUDED.latest_contiguous_sequence,
                     highest_observed_sequence=EXCLUDED.highest_observed_sequence,
                     missing_sequences=EXCLUDED.missing_sequences,
                     observation_count=EXCLUDED.observation_count,version=EXCLUDED.version,
                     updated_at=NOW()""",
                (*scope.key, attempt_id, status, outcome, contiguous, highest,
                 json.dumps(missing), len(rows), version),
            )
            if conflict:
                self._insert_case(
                    conn, scope, source_receipt_id, "terminal_conflict",
                    "TERMINAL_OUTCOME_CONFLICT", {"attemptId": attempt_id},
                )
            conn.commit()
        return self._load_reducer(scope, attempt_id)

    def _quarantine(
        self, scope: TenantScope, endpoint: Any, body_hash: str, headers_hash: str,
        received_at: datetime, *, provider_event_id: str | None, event_key: str,
        case_type: str, reason_code: str, replay_status: str = "new",
    ) -> ActionWebhookInboxSnapshot:
        receipt_id = self._id("webhook-receipt", endpoint["endpoint_id"], event_key, body_hash)
        case_id = self._id("webhook-case", receipt_id, case_type)
        quarantine_ref = {
            "resourceType": "WebhookQuarantine",
            "resourceId": self._id("quarantine", receipt_id),
            "revision": body_hash,
            "authority": "aip_action_webhook_inbox",
        }
        with connect(scope) as conn:
            self._insert_receipt(
                conn, scope, endpoint, receipt_id, body_hash, headers_hash, received_at,
                "verified", "signature_valid", replay_status, "quarantined",
                provider_event_id, event_key,
                canonical_hash({"receiptId": receipt_id, "reason": reason_code}), quarantine_ref,
            )
            self._insert_case(
                conn, scope, receipt_id, case_type, reason_code,
                {"providerEventId": provider_event_id, "bodyHash": body_hash}, case_id=case_id,
            )
            conn.commit()
        return self._snapshot(scope, receipt_id, case_override=case_id)

    def _reject(
        self, scope: TenantScope, endpoint: Any, body_hash: str, headers_hash: str,
        received_at: datetime, reason: str,
    ) -> ActionWebhookInboxSnapshot:
        receipt_id = self._id("webhook-receipt", endpoint["endpoint_id"], reason, body_hash)
        with connect(scope) as conn:
            self._insert_receipt(
                conn, scope, endpoint, receipt_id, body_hash, headers_hash, received_at,
                "rejected", reason, "not_checked", "rejected", None, None,
                canonical_hash({"receiptId": receipt_id, "reason": reason}), None,
            )
            conn.commit()
        return self._snapshot(scope, receipt_id)

    @staticmethod
    def _insert_receipt(
        conn: Any, scope: TenantScope, endpoint: Any, receipt_id: str, body_hash: str,
        headers_hash: str, received_at: datetime, verification_status: str,
        verification_reason: str, replay_status: str, processing_status: str,
        provider_event_id: str | None, event_key: str | None, source_hash: str,
        quarantine_ref: dict[str, Any] | None,
    ) -> None:
        conn.execute(
            """INSERT INTO aip_action_webhook_inbox_receipt
               (org_id,project_id,receipt_id,endpoint_id,endpoint_revision,endpoint_hash,
                body_hash,headers_hash,verification_status,verification_reason,replay_status,
                processing_status,provider_event_id,event_key,quarantine_ref,received_at,source_hash)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
               ON CONFLICT (org_id,project_id,receipt_id) DO NOTHING""",
            (*scope.key, receipt_id, endpoint["endpoint_id"], endpoint["revision"],
             endpoint["content_hash"], body_hash, headers_hash, verification_status,
             verification_reason, replay_status, processing_status, provider_event_id,
             event_key, json.dumps(quarantine_ref) if quarantine_ref else None,
             received_at, source_hash),
        )

    @staticmethod
    def _insert_case(
        conn: Any, scope: TenantScope, receipt_id: str, case_type: str,
        reason_code: str, safe_facts: dict[str, Any], *, case_id: str | None = None,
    ) -> str:
        case_id = case_id or AipActionWebhookService._id("webhook-case", receipt_id, case_type)
        conn.execute(
            """INSERT INTO aip_action_webhook_case
               (org_id,project_id,case_id,receipt_id,case_type,reason_code,safe_facts)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT (org_id,project_id,case_id) DO NOTHING""",
            (*scope.key, case_id, receipt_id, case_type, reason_code, json.dumps(safe_facts)),
        )
        return case_id

    def _snapshot(
        self, scope: TenantScope, receipt_id: str, *, replay_override: str | None = None,
        reducer_override: ActionWebhookReducerView | None = None,
        case_override: str | None = None,
    ) -> ActionWebhookInboxSnapshot:
        with connect(scope) as conn:
            receipt = conn.execute(
                """SELECT * FROM aip_action_webhook_inbox_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            observation = conn.execute(
                """SELECT * FROM aip_action_webhook_observation
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            case = conn.execute(
                """SELECT case_id FROM aip_action_webhook_case
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s
                   ORDER BY created_at DESC LIMIT 1""",
                (*scope.key, receipt_id),
            ).fetchone()
        observation_model = None
        reducer = reducer_override
        if observation:
            observation_model = ActionWebhookObservationSnapshot(
                id=observation["observation_id"], receipt_id=observation["receipt_id"],
                attempt_id=observation["attempt_id"], provider_event_id=observation["provider_event_id"],
                event_type=observation["event_type"], provider_outcome=observation["provider_outcome"],
                provider_sequence=observation["provider_sequence"],
                provider_event_at=observation["provider_event_at"],
                payload_hash=observation["payload_hash"], created_at=observation["created_at"],
            )
            reducer = reducer or self._load_reducer(scope, observation["attempt_id"])
        return ActionWebhookInboxSnapshot(
            id=receipt["receipt_id"], endpoint_revision=receipt["endpoint_revision"],
            body_hash=receipt["body_hash"], verification_status=receipt["verification_status"],
            verification_reason=receipt["verification_reason"],
            replay_status=replay_override or receipt["replay_status"],
            processing_status=receipt["processing_status"],
            provider_event_id=receipt["provider_event_id"], observation=observation_model,
            reducer=reducer, case_id=case_override or (case["case_id"] if case else None),
            received_at=receipt["received_at"],
        )

    @staticmethod
    def _load_reducer(scope: TenantScope, attempt_id: str) -> ActionWebhookReducerView:
        with connect(scope) as conn:
            row = conn.execute(
                """SELECT * FROM aip_action_webhook_reducer_view
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (*scope.key, attempt_id),
            ).fetchone()
        return ActionWebhookReducerView(
            attempt_id=row["attempt_id"], status=row["status"],
            provider_outcome=row["provider_outcome"],
            latest_contiguous_sequence=row["latest_contiguous_sequence"],
            highest_observed_sequence=row["highest_observed_sequence"],
            missing_sequences=row["missing_sequences"], observation_count=row["observation_count"],
            version=row["version"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _id(prefix: str, *parts: Any) -> str:
        return f"{prefix}-{canonical_hash(list(parts))[:24]}"


_SERVICE = AipActionWebhookService()


def get_action_webhook_service() -> AipActionWebhookService:
    return _SERVICE
