"""Same-snapshot diagnostic binding of a frozen unknown attempt to its source group."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from aos_api.data_requirement_outbox_store import DataRequirementOutboxClaim
from aos_api.ecommerce_analysis_data_requirement_route import (
    AnalysisDataRequirementRouteReader, HistoricalSourceGroupEvidence,
)
from aos_api.ecommerce_analysis_original_attempt_receipt_resolver import (
    OriginalAttemptReceiptEvidence, OriginalAttemptReceiptResolver,
)
from aos_api.ecommerce_growth_runtime_connection import connect_read_only
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope


class UnknownSourceGroupFrozen(ValueError):
    """One historical lineage field differs; no reconciliation authority."""


@dataclass(frozen=True, slots=True)
class UnknownSourceGroupEvidence:
    receipts: OriginalAttemptReceiptEvidence
    source_group: HistoricalSourceGroupEvidence


class UnknownSourceGroupEvidenceReader:
    def __init__(self, *, claims: PipelineSourceClaimOwner, connect_factory=connect_read_only):
        if type(claims) is not PipelineSourceClaimOwner or not callable(connect_factory):
            raise TypeError('exact original claims and read-only connection factory required')
        self._claims, self._connect = claims, connect_factory

    def resolve(self, scope: TenantScope, claim: DataRequirementOutboxClaim) -> UnknownSourceGroupEvidence:
        if type(scope) is not TenantScope or type(claim) is not DataRequirementOutboxClaim:
            raise TypeError('exact tenant and original unknown attempt required')
        with self._connect(scope) as conn:
            if conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] != 'on':
                raise UnknownSourceGroupFrozen('READ_ONLY_TENANT_BOUNDARY_REQUIRED')

            @contextmanager
            def same_transaction(current_scope):
                if current_scope != scope:
                    raise UnknownSourceGroupFrozen('TENANT_SCOPE_DRIFT')
                yield conn

            receipts = OriginalAttemptReceiptResolver(same_transaction).resolve(scope, claim)
            if receipts.state != 'unknown':
                raise UnknownSourceGroupFrozen('ORIGINAL_ATTEMPT_NOT_UNKNOWN')
            group = AnalysisDataRequirementRouteReader(
                claims=self._claims, connect_factory=same_transaction,
            ).read_unknown_historical(scope, claim)
            root_ref = receipts.original_analysis_ref.model_dump(
                mode='json', by_alias=True, exclude_none=True)
            occurrence_ref = receipts.occurrence_ref.model_dump(
                mode='json', by_alias=True, exclude_none=True)
            if (group.requirement_ref != receipts.requirement_ref
                    or group.run_ref != receipts.run_ref
                    or group.case_ref != receipts.case_ref
                    or group.original_analysis_ref != root_ref
                    or group.occurrence_ref != occurrence_ref
                    or group.occurrence_id != receipts.occurrence_ref.resource_id
                    or (group.source_control_ref,group.source_run_id) not in group.group_bindings):
                raise UnknownSourceGroupFrozen('ORIGINAL_SOURCE_GROUP_LINEAGE_DRIFT')
            return UnknownSourceGroupEvidence(receipts, group)


__all__ = ['UnknownSourceGroupEvidence', 'UnknownSourceGroupEvidenceReader',
    'UnknownSourceGroupFrozen']
