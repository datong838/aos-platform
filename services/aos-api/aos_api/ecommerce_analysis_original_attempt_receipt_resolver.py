"""Read-only evidence for one frozen original Analysis DataRequirement attempt.

This is diagnostic evidence, never a delivery transition or replay authority.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_fulfillment_store import DataFulfillmentStore
from aos_api.data_requirement_outbox_store import DataRequirementOutboxClaim
from aos_api.ecommerce_analysis_snapshot_coordinator import snapshot_route_key
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore
from aos_api.ecommerce_growth_runtime_connection import connect_read_only
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class OriginalAttemptReceiptEvidence:
    state: str
    outbox_id: str
    attempt: int
    lease_token: str
    fulfillment_ref: InvestigationExactRef
    analysis_ref: InvestigationExactRef


class OriginalAttemptReceiptFrozen(ValueError):
    """The original attempt has insufficient or contradictory persisted evidence."""


class OriginalAttemptReceiptResolver:
    def __init__(self, connect_factory=connect_read_only):
        if not callable(connect_factory):
            raise TypeError('read-only connection factory required')
        self._connect = connect_factory

    @staticmethod
    def _required(value: Any, expected: Any, reason: str) -> None:
        if value != expected:
            raise OriginalAttemptReceiptFrozen(reason)

    def resolve(self, scope: TenantScope, claim: DataRequirementOutboxClaim) -> OriginalAttemptReceiptEvidence:
        if type(scope) is not TenantScope or type(claim) is not DataRequirementOutboxClaim:
            raise TypeError('exact tenant and persisted original attempt required')
        expected_payload = dict(eventId=claim.event_id, requirementId=claim.requirement_id,
            revision=claim.requirement_revision, contentHash=claim.content_hash)
        if claim.topic != 'data.requirement.request' or claim.payload != expected_payload:
            raise OriginalAttemptReceiptFrozen('OUTBOX_PAYLOAD_DRIFT')
        requirement_ref = InvestigationExactRef(resource_type='DataRequirementRevision',
            resource_id=claim.requirement_id, revision=claim.requirement_revision,
            content_hash=claim.content_hash)
        requirement_json = requirement_ref.model_dump(mode='json', by_alias=True, exclude_none=True)
        key = snapshot_route_key(scope, requirement_json)
        with self._connect(scope) as conn:
            identity = conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id,"
                "current_setting('transaction_read_only') AS read_only").fetchone()
            if (identity['role'], identity['org_id'], identity['project_id'], identity['read_only']) != (
                'aos_runtime', *scope.key, 'on'):
                raise OriginalAttemptReceiptFrozen('READ_ONLY_TENANT_BOUNDARY_REQUIRED')
            row = conn.execute('''SELECT o.requirement_id,o.requirement_revision,o.event_id,o.topic,
                    o.payload,o.content_hash,d.state,d.attempt,d.lease_token,d.lease_expires_at,
                    d.completion_fulfillment_ref,d.completion_analysis_ref,q.run_ref,q.case_ref
                FROM public.data_requirement_outbox o
                JOIN public.data_requirement_outbox_delivery d
                  USING(org_id,project_id,outbox_id)
                JOIN public.data_requirement_revision q ON q.org_id=o.org_id
                  AND q.project_id=o.project_id AND q.requirement_id=o.requirement_id
                  AND q.revision=o.requirement_revision
                WHERE o.org_id=%s AND o.project_id=%s AND o.outbox_id=%s''',
                (*scope.key, claim.outbox_id)).fetchone()
            if row is None:
                raise OriginalAttemptReceiptFrozen('OUTBOX_NOT_FOUND')
            if (row['requirement_id'] != claim.requirement_id
                    or row['requirement_revision'] != claim.requirement_revision
                    or row['event_id'] != claim.event_id or row['topic'] != claim.topic
                    or row['payload'] != claim.payload
                    or 'sha256:' + row['content_hash'].strip() != claim.content_hash
                    or row['attempt'] != claim.attempt or row['lease_token'] != claim.lease_token
                    or row['lease_expires_at'] != claim.lease_expires_at):
                raise OriginalAttemptReceiptFrozen('ORIGINAL_ATTEMPT_DRIFT')
            if row['state'] not in ('unknown', 'claimed'):
                raise OriginalAttemptReceiptFrozen('NOT_FROZEN_ATTEMPT')
            if row['state'] == 'claimed':
                expired = conn.execute('SELECT %s::timestamptz<=clock_timestamp() AS expired',
                    (claim.lease_expires_at,)).fetchone()['expired']
                if not expired:
                    raise OriginalAttemptReceiptFrozen('CLAIM_STILL_LIVE')
            if row['completion_fulfillment_ref'] is not None or row['completion_analysis_ref'] is not None:
                raise OriginalAttemptReceiptFrozen('UNEXPECTED_COMPLETION_REFS')
            run_ref = row['run_ref']
            if type(run_ref) is not dict or run_ref.get('receiptId', object()) is not None:
                raise OriginalAttemptReceiptFrozen('ORIGINAL_RUN_REF_DRIFT')
            run_ref = {name: value for name, value in run_ref.items() if name != 'receiptId'}
            transaction = HostTransaction(conn)
            receipt_store = _HostAnalysisReceiptStore(transaction, scope)
            saved = receipt_store.read(key)
            if saved is None:
                raise OriginalAttemptReceiptFrozen('ANALYSIS_RECEIPT_MISSING')
            analysis_ref = InvestigationExactRef.model_validate(saved.get('receiptRef'))
            analysis_json = analysis_ref.model_dump(mode='json', by_alias=True, exclude_none=True)
            exact = receipt_store.read_exact(analysis_json)
            self._required(exact, saved, 'ANALYSIS_RECEIPT_NOT_UNIQUE_OR_DRIFTED')
            persisted = conn.execute('''SELECT idempotency_key,request_hash,target_receipt_ref
                FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_analysis_advance'
                  AND target_receipt_ref=%s::jsonb''',
                (*scope.key, Jsonb(analysis_json))).fetchall()
            if (len(persisted) != 1 or persisted[0]['idempotency_key'] != key
                    or persisted[0]['request_hash'] != saved.get('requestHash')
                    or persisted[0]['target_receipt_ref'] != analysis_json):
                raise OriginalAttemptReceiptFrozen('ANALYSIS_KEY_OR_TARGET_DRIFT')
            if (saved.get('phase') != 'RUNNING' or saved.get('completed') is not False
                    or saved.get('requirementRef') != requirement_json
                    or saved.get('runRef') != run_ref):
                raise OriginalAttemptReceiptFrozen('ANALYSIS_LINEAGE_DRIFT')
            originals = conn.execute('''SELECT target_receipt_ref,response
                FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_analysis_advance'
                  AND response->'runRef'=%s::jsonb
                  AND response->>'phase'='PREPARING'
                  AND response->'completed'='false'::jsonb
                  AND response->'requirementRef'='null'::jsonb''',
                (*scope.key, Jsonb(run_ref))).fetchall()
            if len(originals) != 1:
                raise OriginalAttemptReceiptFrozen('ORIGINAL_SOURCE_RECEIPT_NOT_UNIQUE')
            prior = receipt_store.read_exact(originals[0]['target_receipt_ref'])
            if (prior is None or prior != originals[0]['response']
                    or prior.get('receiptRef') != originals[0]['target_receipt_ref']
                    or prior.get('phase') != 'PREPARING' or prior.get('completed') is not False
                    or prior.get('runRef') != run_ref
                    or prior.get('caseRef') != {k: v for k, v in row['case_ref'].items() if k != 'receiptId'}
                    or prior.get('requirementRef') is not None
                    or any(saved.get(name) != prior.get(name) for name in (
                        'occurrenceRef', 'caseRef', 'profileRef', 'cutoffAt', 'compilationRef'))):
                raise OriginalAttemptReceiptFrozen('ORIGINAL_SOURCE_LINEAGE_DRIFT')
            fulfillment_ref = InvestigationExactRef.model_validate(saved.get('fulfillmentRef'))
            fulfillment_json = fulfillment_ref.model_dump(mode='json', by_alias=True, exclude_none=True)
            if fulfillment_ref.resource_type != 'DataFulfillmentReceipt':
                raise OriginalAttemptReceiptFrozen('FULFILLMENT_REF_TYPE_DRIFT')

            @contextmanager
            def same_transaction(_scope):
                if _scope != scope:
                    raise OriginalAttemptReceiptFrozen('FULFILLMENT_TENANT_DRIFT')
                yield conn

            fulfillment = DataFulfillmentStore(same_transaction).read_exact(scope, fulfillment_ref)
            if (fulfillment is None or fulfillment.status.value != 'fulfilled'
                    or fulfillment.requirement_ref != requirement_ref
                    or (fulfillment.tenant.org_id, fulfillment.tenant.project_id) != scope.key
                    or saved.get('fulfillmentRef') != fulfillment_json):
                raise OriginalAttemptReceiptFrozen('FULFILLMENT_LINEAGE_DRIFT')
            return OriginalAttemptReceiptEvidence(row['state'], claim.outbox_id, claim.attempt,
                claim.lease_token, fulfillment_ref, analysis_ref)


__all__ = ['OriginalAttemptReceiptEvidence', 'OriginalAttemptReceiptFrozen',
    'OriginalAttemptReceiptResolver']
