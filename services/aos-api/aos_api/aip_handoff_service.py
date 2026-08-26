"""Tenant-scoped one-time AIP Handoff authority with receiver reauthorization."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime

from aos_api.aip_agent_registry_contracts import (
    HandoffEnvelope,
    IssueHandoffRequest,
    IssuedHandoff,
    RegistryReceipt,
    VersionedAssetRef,
    CreateHandoffDecisionRequest,
    DecidedHandoff,
    HandoffDecisionKind,
    HandoffDecisionListResponse,
    HandoffDecisionRevision,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import HandoffResourceRef, ResourceRef, TenantContext
from aos_api.tenant_scope import TenantScope

RefAuthorizer = Callable[[TenantScope, HandoffResourceRef, VersionedAssetRef], bool]
EnvelopeAuthorizer = Callable[[TenantScope, Mapping[str, object], VersionedAssetRef], bool]


class AipHandoffService(AipAgentRegistryStore):
    def __init__(self, connect_factory=None, *, ref_authorizer: RefAuthorizer | None = None, envelope_authorizer: EnvelopeAuthorizer | None = None) -> None:
        super().__init__(connect_factory)
        self._ref_authorizer = ref_authorizer
        self._envelope_authorizer = envelope_authorizer

    def issue(
        self,
        scope: TenantScope,
        request: IssueHandoffRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> IssuedHandoff:
        self._validate_command(scope, idempotency_key, actor)
        if request.envelope.expires_at <= occurred_at:
            raise AipAgentRegistryTransitionBlocked("handoff expiry must be in the future")
        operation = "handoff.issue"
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    handoff = self._from_row(
                        scope, self._row(conn, scope, replay["result_ref"]["resourceId"])
                    )
                    return IssuedHandoff(
                        handoff=handoff,
                        bearer_token=None,
                        receipt=self._receipt_from_row(scope, replay),
                    )
                if self._row(conn, scope, request.handoff_id) is not None:
                    raise AipAgentRegistryConflict("handoff id already exists")
                envelope = request.envelope
                task_id, run_id = self._require_task_run(
                    conn, scope, envelope.task_ref, envelope.run_ref
                )
                sender = self._require_exact_active_instance(conn, scope, envelope.sender_instance)
                receiver = self._require_exact_active_instance(conn, scope, envelope.receiver_instance)
                if sender["instance_id"] == receiver["instance_id"]:
                    raise AipAgentRegistryConflict("handoff sender and receiver must differ")
                bearer = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(bearer.encode()).hexdigest()
                row = conn.execute(
                    """INSERT INTO aip_handoff_envelope
                       (org_id,project_id,handoff_id,task_id,task_run_id,
                        task_ref,task_run_ref,sender_instance_id,receiver_instance_id,sender_instance_ref,
                        receiver_instance_ref,object_refs,artifact_refs,evidence_refs,
                        context_payload,allowed_context_fields,markings,token_hash,
                        status,version,expires_at,created_at)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                        %s::jsonb,%s,'issued',1,%s,%s) RETURNING *""",
                    (
                        *scope.key,
                        request.handoff_id,
                        task_id,
                        run_id,
                        self._json(envelope.task_ref),
                        self._json(envelope.run_ref),
                        sender["instance_id"],
                        receiver["instance_id"],
                        self._json(envelope.sender_instance),
                        self._json(envelope.receiver_instance),
                        self._json(envelope.object_refs),
                        self._json(envelope.artifact_refs),
                        self._json(envelope.evidence_refs),
                        self._json(envelope.context),
                        self._json(envelope.allowed_context_fields),
                        self._json(envelope.markings),
                        token_hash,
                        envelope.expires_at,
                        occurred_at,
                    ),
                ).fetchone()
                self._append_event(
                    conn,
                    scope,
                    request.handoff_id,
                    sequence=1,
                    event_type="issued",
                    from_status=None,
                    to_status="issued",
                    actor=actor,
                    reason_code=None,
                    occurred_at=occurred_at,
                )
                receipt = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    "TaskRun",
                    run_id,
                    "HandoffEnvelope",
                    request.handoff_id,
                    actor,
                    occurred_at,
                )
                conn.commit()
                return IssuedHandoff(
                    handoff=self._from_row(scope, row),
                    bearer_token=bearer,
                    receipt=receipt,
                )
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("handoff issue failed") from exc

    def consume(
        self,
        scope: TenantScope,
        handoff_id: str,
        *,
        bearer_token: str,
        receiver_instance: VersionedAssetRef,
        actor: str,
        occurred_at: datetime,
    ) -> HandoffEnvelope:
        if not bearer_token or not actor.strip():
            raise ValueError("bearer token and actor are required")
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT * FROM aip_handoff_envelope
                       WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                       FOR UPDATE""",
                    (*scope.key, handoff_id),
                ).fetchone()
                if row is None:
                    raise AipAgentRegistryNotFound("handoff not found")
                if row["status"] != "issued":
                    raise AipAgentRegistryTransitionBlocked("handoff is no longer consumable")
                if row["expires_at"] <= occurred_at:
                    self._terminal_transition(
                        conn, scope, row, "expired", actor, "TOKEN_EXPIRED", occurred_at
                    )
                    conn.commit()
                    raise AipAgentRegistryTransitionBlocked("handoff has expired")
                if not secrets.compare_digest(
                    row["token_hash"], hashlib.sha256(bearer_token.encode()).hexdigest()
                ):
                    raise AipAgentRegistryNotFound("handoff token is invalid")
                stored_receiver = VersionedAssetRef.model_validate(row["receiver_instance_ref"])
                if receiver_instance != stored_receiver:
                    raise AipAgentRegistryTransitionBlocked("handoff receiver exact revision drifted")
                self._require_exact_active_instance(conn, scope, receiver_instance)
                self._reauthorize_refs(scope, row, receiver_instance)
                if self._envelope_authorizer is not None and not self._envelope_authorizer(scope, row, receiver_instance):
                    raise AipAgentRegistryTransitionBlocked(
                        "receiver responsibility binding drifted after handoff compilation"
                    )
                updated = self._terminal_transition(
                    conn, scope, row, "consumed", actor, None, occurred_at
                )
                conn.commit()
                return self._from_row(scope, updated)
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("handoff consume failed") from exc

    def revoke(
        self,
        scope: TenantScope,
        handoff_id: str,
        *,
        expected_version: int,
        actor: str,
        reason_code: str,
        occurred_at: datetime,
    ) -> HandoffEnvelope:
        if not actor.strip() or not reason_code.strip():
            raise ValueError("actor and reason code are required")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT * FROM aip_handoff_envelope
                   WHERE org_id=%s AND project_id=%s AND handoff_id=%s FOR UPDATE""",
                (*scope.key, handoff_id),
            ).fetchone()
            if row is None:
                raise AipAgentRegistryNotFound("handoff not found")
            if row["status"] != "issued" or int(row["version"]) != expected_version:
                raise AipAgentRegistryConflict("handoff version or status changed")
            updated = self._terminal_transition(
                conn, scope, row, "revoked", actor, reason_code.strip(), occurred_at
            )
            conn.commit()
            return self._from_row(scope, updated)

    def get(self, scope: TenantScope, handoff_id: str) -> HandoffEnvelope:
        with self._connect_factory(scope) as conn:
            row = self._row(conn, scope, handoff_id)
        if row is None:
            raise AipAgentRegistryNotFound("handoff not found")
        return self._from_row(scope, row)

    def decide(
        self,
        scope: TenantScope,
        handoff_id: str,
        request: CreateHandoffDecisionRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> DecidedHandoff:
        self._validate_command(scope, idempotency_key, actor)
        operation = "handoff.decision"
        request_hash = hashlib.sha256(
            self._json(
                {
                    "actor": actor.strip(),
                    "request": {
                        "handoffId": handoff_id,
                        **request.model_dump(mode="json", by_alias=True),
                    },
                }
            ).encode()
        ).hexdigest()
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    decision = self.get_decision(
                        scope, replay["result_ref"]["resourceId"], conn=conn
                    )
                    return DecidedHandoff(
                        decision=decision,
                        receipt=self._receipt_from_row(scope, replay),
                    )
                envelope = conn.execute(
                    """SELECT * FROM aip_handoff_envelope
                       WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                       FOR UPDATE""",
                    (*scope.key, handoff_id),
                ).fetchone()
                if envelope is None:
                    raise AipAgentRegistryNotFound("handoff not found")
                if envelope["status"] != "consumed":
                    raise AipAgentRegistryTransitionBlocked(
                        "handoff decision requires consumed envelope"
                    )
                stored_receiver = VersionedAssetRef.model_validate(
                    envelope["receiver_instance_ref"]
                )
                if request.receiver_instance != stored_receiver:
                    raise AipAgentRegistryTransitionBlocked(
                        "handoff decision receiver exact revision drifted"
                    )
                self._require_exact_active_instance(
                    conn, scope, request.receiver_instance
                )
                head = conn.execute(
                    """SELECT * FROM aip_handoff_decision_head
                       WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                       FOR UPDATE""",
                    (*scope.key, handoff_id),
                ).fetchone()
                current_version = 0 if head is None else int(head["version"])
                if current_version != request.expected_head_version:
                    raise AipAgentRegistryConflict(
                        "handoff decision head version conflict"
                    )
                if head is not None and head["terminal_decision"] is not None:
                    raise AipAgentRegistryConflict(
                        "handoff decision already terminal"
                    )
                if (
                    head is not None
                    and request.decision is not HandoffDecisionKind.RETURNED
                    and head["terminal_decision"] is None
                    and int(head["current_revision"]) >= 1
                ):
                    # after request_more only returned may append; after no head, any first decision ok
                    last = conn.execute(
                        """SELECT decision FROM aip_handoff_decision_revision
                           WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                           ORDER BY revision DESC LIMIT 1""",
                        (*scope.key, handoff_id),
                    ).fetchone()
                    if last is not None and last["decision"] == "request_more":
                        if request.decision is not HandoffDecisionKind.RETURNED:
                            raise AipAgentRegistryTransitionBlocked(
                                "after request_more only returned is allowed"
                            )
                    elif last is not None:
                        raise AipAgentRegistryConflict(
                            "handoff decision already recorded"
                        )
                revision = 1 if head is None else int(head["current_revision"]) + 1
                decision_id = f"handoff-decision-{uuid.uuid4().hex[:20]}"
                envelope_ref = ResourceRef(
                    resource_type="HandoffEnvelope",
                    resource_id=handoff_id,
                    revision=str(envelope["version"]),
                    authority="postgresql",
                )
                payload = {
                    "handoffId": handoff_id,
                    "revision": revision,
                    "envelopeRef": envelope_ref.model_dump(mode="json", by_alias=True),
                    "decision": request.decision.value,
                    "reasonCode": request.reason_code,
                    "gapCodes": request.gap_codes,
                    "returnRefs": [
                        item.model_dump(mode="json", by_alias=True)
                        for item in request.return_refs
                    ],
                    "correlationRef": None
                    if request.correlation_ref is None
                    else request.correlation_ref.model_dump(mode="json", by_alias=True),
                    "receiverInstance": request.receiver_instance.model_dump(
                        mode="json", by_alias=True
                    ),
                }
                content_hash = self._hash(payload)
                conn.execute(
                    """INSERT INTO aip_handoff_decision_revision
                       (org_id,project_id,decision_id,handoff_id,revision,envelope_ref,
                        decision,reason_code,gap_codes,return_refs,correlation_ref,
                        receiver_instance_ref,content_hash,actor,created_at)
                       VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,
                              %s::jsonb,%s::jsonb,%s,%s,%s)""",
                    (
                        *scope.key,
                        decision_id,
                        handoff_id,
                        revision,
                        self._json(envelope_ref),
                        request.decision.value,
                        request.reason_code,
                        self._json(request.gap_codes),
                        self._json(
                            [
                                item.model_dump(mode="json", by_alias=True)
                                for item in request.return_refs
                            ]
                        ),
                        None
                        if request.correlation_ref is None
                        else self._json(request.correlation_ref),
                        self._json(request.receiver_instance),
                        content_hash,
                        actor,
                        occurred_at,
                    ),
                )
                terminal = (
                    request.decision.value
                    if request.decision
                    in {
                        HandoffDecisionKind.ACCEPTED,
                        HandoffDecisionKind.REJECTED,
                        HandoffDecisionKind.RETURNED,
                    }
                    else None
                )
                if head is None:
                    conn.execute(
                        """INSERT INTO aip_handoff_decision_head
                           (org_id,project_id,handoff_id,current_revision,version,
                            terminal_decision,updated_at)
                           VALUES(%s,%s,%s,%s,1,%s,%s)""",
                        (
                            *scope.key,
                            handoff_id,
                            revision,
                            terminal,
                            occurred_at,
                        ),
                    )
                else:
                    conn.execute(
                        """UPDATE aip_handoff_decision_head
                           SET current_revision=%s, version=version+1,
                               terminal_decision=%s, updated_at=%s
                           WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                             AND version=%s""",
                        (
                            revision,
                            terminal,
                            occurred_at,
                            *scope.key,
                            handoff_id,
                            request.expected_head_version,
                        ),
                    )
                # Envelope transport status must stay consumed — never reopen.
                still = conn.execute(
                    """SELECT status FROM aip_handoff_envelope
                       WHERE org_id=%s AND project_id=%s AND handoff_id=%s""",
                    (*scope.key, handoff_id),
                ).fetchone()
                if still is None or still["status"] != "consumed":
                    raise AipAgentRegistryPersistenceError(
                        "handoff envelope transport integrity failed"
                    )
                receipt = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    "HandoffEnvelope",
                    handoff_id,
                    "HandoffDecisionRevision",
                    decision_id,
                    actor,
                    occurred_at,
                )
                conn.commit()
                return DecidedHandoff(
                    decision=self.get_decision(scope, decision_id),
                    receipt=receipt,
                )
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("handoff decision failed") from exc

    def get_decision(
        self,
        scope: TenantScope,
        decision_id: str,
        *,
        conn=None,
    ) -> HandoffDecisionRevision:
        def read(c) -> HandoffDecisionRevision:
            row = c.execute(
                """SELECT * FROM aip_handoff_decision_revision
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone()
            if row is None:
                raise AipAgentRegistryNotFound("handoff decision not found")
            return self._decision_from_row(scope, row)

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as c:
            return read(c)

    def list_decisions(
        self, scope: TenantScope, handoff_id: str
    ) -> HandoffDecisionListResponse:
        with self._connect_factory(scope) as conn:
            if self._row(conn, scope, handoff_id) is None:
                raise AipAgentRegistryNotFound("handoff not found")
            rows = conn.execute(
                """SELECT * FROM aip_handoff_decision_revision
                   WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                   ORDER BY revision ASC""",
                (*scope.key, handoff_id),
            ).fetchall()
            head = conn.execute(
                """SELECT version FROM aip_handoff_decision_head
                   WHERE org_id=%s AND project_id=%s AND handoff_id=%s""",
                (*scope.key, handoff_id),
            ).fetchone()
            items = [self._decision_from_row(scope, row) for row in rows]
            return HandoffDecisionListResponse(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                handoff_id=handoff_id,
                items=items,
                count=len(items),
                head_version=0 if head is None else int(head["version"]),
            )

    @staticmethod
    def _decision_from_row(scope: TenantScope, row) -> HandoffDecisionRevision:
        return HandoffDecisionRevision(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            decision_id=row["decision_id"],
            handoff_id=row["handoff_id"],
            revision=int(row["revision"]),
            envelope_ref=row["envelope_ref"],
            decision=row["decision"],
            reason_code=row["reason_code"],
            gap_codes=row["gap_codes"] or [],
            return_refs=row["return_refs"] or [],
            correlation_ref=row["correlation_ref"],
            receiver_instance=row["receiver_instance_ref"],
            content_hash=row["content_hash"],
            created_by=row["actor"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row(conn, scope: TenantScope, handoff_id: str):
        return conn.execute(
            """SELECT * FROM aip_handoff_envelope
               WHERE org_id=%s AND project_id=%s AND handoff_id=%s""",
            (*scope.key, handoff_id),
        ).fetchone()

    @staticmethod
    def _require_task_run(
        conn, scope: TenantScope, task_ref: ResourceRef, run_ref: ResourceRef
    ) -> tuple[str, str]:
        if task_ref.resource_type != "Task" or run_ref.resource_type != "TaskRun":
            raise AipAgentRegistryConflict("handoff task and run refs have invalid kinds")
        row = conn.execute(
            """SELECT r.task_id,r.run_id,r.version AS run_version,t.version AS task_version
               FROM aip_task_run r JOIN aip_task t
                ON t.org_id=r.org_id AND t.project_id=r.project_id AND t.task_id=r.task_id
               WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
            (*scope.key, run_ref.resource_id),
        ).fetchone()
        if row is None:
            raise AipAgentRegistryNotFound("canonical task run not found")
        if row["task_id"] != task_ref.resource_id:
            raise AipAgentRegistryConflict("task run belongs to another task")
        if task_ref.revision != str(row["task_version"]) or run_ref.revision != str(row["run_version"]):
            raise AipAgentRegistryConflict("handoff task or run exact revision drifted")
        return row["task_id"], row["run_id"]

    def _require_exact_active_instance(
        self, conn, scope: TenantScope, exact_ref: VersionedAssetRef
    ):
        if exact_ref.asset_type != "AgentInstance":
            raise AipAgentRegistryConflict("handoff instance ref has invalid kind")
        row = self._instance_row(conn, scope, exact_ref.asset_id)
        if row is None or self._instance_from_row(scope, row).instance_ref != exact_ref:
            raise AipAgentRegistryNotFound("exact agent instance revision not found")
        if row["status"] != "active":
            raise AipAgentRegistryTransitionBlocked("agent instance is not active")
        return row

    def _reauthorize_refs(
        self, scope: TenantScope, row, receiver_instance: VersionedAssetRef
    ) -> None:
        refs = [
            *[HandoffResourceRef.model_validate(item) for item in row["object_refs"]],
            *[HandoffResourceRef.model_validate(item) for item in row["artifact_refs"]],
            *[HandoffResourceRef.model_validate(item) for item in row["evidence_refs"]],
        ]
        if refs and self._ref_authorizer is None:
            raise AipAgentRegistryTransitionBlocked(
                "receiver reference authorizer is not configured"
            )
        if self._ref_authorizer is not None and any(
            not self._ref_authorizer(scope, ref, receiver_instance) for ref in refs
        ):
            raise AipAgentRegistryTransitionBlocked(
                "receiver is not authorized to resolve all handoff refs"
            )

    def _terminal_transition(
        self,
        conn,
        scope: TenantScope,
        row,
        to_status: str,
        actor: str,
        reason_code: str | None,
        occurred_at: datetime,
    ):
        updated = conn.execute(
            """UPDATE aip_handoff_envelope SET status=%s,version=version+1,
               consumed_at=CASE WHEN %s='consumed' THEN %s ELSE consumed_at END
               WHERE org_id=%s AND project_id=%s AND handoff_id=%s
                AND version=%s AND status='issued' RETURNING *""",
            (
                to_status,
                to_status,
                occurred_at,
                *scope.key,
                row["handoff_id"],
                row["version"],
            ),
        ).fetchone()
        if updated is None:
            raise AipAgentRegistryConflict("handoff version or status changed")
        self._append_event(
            conn,
            scope,
            row["handoff_id"],
            sequence=int(row["version"]) + 1,
            event_type=to_status,
            from_status="issued",
            to_status=to_status,
            actor=actor,
            reason_code=reason_code,
            occurred_at=occurred_at,
        )
        return updated

    def _append_event(
        self,
        conn,
        scope: TenantScope,
        handoff_id: str,
        *,
        sequence: int,
        event_type: str,
        from_status: str | None,
        to_status: str,
        actor: str,
        reason_code: str | None,
        occurred_at: datetime,
    ) -> None:
        actor_ref = ResourceRef(
            resource_type="Principal",
            resource_id=actor.strip(),
            revision=None,
            authority="aos-authn",
        )
        payload = {
            "handoffId": handoff_id,
            "sequence": sequence,
            "eventType": event_type,
            "fromStatus": from_status,
            "toStatus": to_status,
            "actorRef": actor_ref.model_dump(mode="json", by_alias=True),
            "reasonCode": reason_code,
            "occurredAt": occurred_at.isoformat(),
        }
        conn.execute(
            """INSERT INTO aip_handoff_event
               (org_id,project_id,event_id,handoff_id,sequence,event_type,
                from_status,to_status,actor_ref,reason_code,event_hash,occurred_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (
                *scope.key,
                f"aip6he-{uuid.uuid4().hex}",
                handoff_id,
                sequence,
                event_type,
                from_status,
                to_status,
                self._json(actor_ref),
                reason_code,
                self._hash(payload),
                occurred_at,
            ),
        )

    @staticmethod
    def _from_row(scope: TenantScope, row) -> HandoffEnvelope:
        if row is None:
            raise AipAgentRegistryNotFound("handoff not found")
        envelope = {
            "taskRef": row["task_ref"],
            "runRef": row["task_run_ref"],
            "senderInstance": row["sender_instance_ref"],
            "receiverInstance": row["receiver_instance_ref"],
            "objectRefs": row["object_refs"],
            "artifactRefs": row["artifact_refs"],
            "evidenceRefs": row["evidence_refs"],
            "context": row["context_payload"],
            "allowedContextFields": row["allowed_context_fields"],
            "markings": row["markings"],
            "expiresAt": row["expires_at"],
        }
        return HandoffEnvelope(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            handoff_id=row["handoff_id"],
            envelope=envelope,
            status=row["status"],
            version=row["version"],
            consumed_at=row["consumed_at"],
            created_at=row["created_at"],
        )
