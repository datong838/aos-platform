"""Verify saved price batch evidence without preparing, freezing or executing it."""
from datetime import datetime

import psycopg
from psycopg import IsolationLevel

from aos_api.db import connect_read_only
from aos_api.ecommerce_workshop_price_research import (
    EcommerceWorkshopPriceResearchService, PreparePriceResearchBatchRequest,
    PriceResearchBatchLedger, PriceResearchBatchRevision, canonical_hash,
)
from aos_api.public_contracts import redact_sensitive

MAX_ROW_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 2 * MAX_ROW_BYTES
_REFS = {
    'briefRef': 'brief', 'evalRef': 'eval', 'responsibilityPlanRef': 'responsibilityPlan',
    'profileRef': 'profile', 'monitoringPolicyRef': 'monitoringPolicy',
    'capacitySnapshotRef': 'capacitySnapshot', 'budgetSnapshotRef': 'budgetSnapshot',
    'logicRef': 'logic', 'agentBindingRef': 'agentBinding',
}
_MUTABLE_FREEZE = {'revision', 'version', 'lifecycle', 'priorContentHash',
                   'contentHash', 'createdBy', 'createdAt'}
_INTEGER_FIELDS = {'revision', 'version', 'input', 'eligible', 'excluded', 'needsReview',
                   'unknown', 'deduplicated', 'providerCallCount', 'researchJobCount',
                   'notificationCount', 'actionProposalCount', 'repricingCount', 'externalEffectCount'}
_BOOLEAN_FIELDS = {'licenseEligible', 'freshnessEligible', 'rateEligible',
                   'capacityEligible', 'budgetEligible'}


class PriceResearchReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deny(suffix):
    raise PriceResearchReadonlyError('PRICE_RESEARCH_READ_' + suffix)


def _aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def _strict(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _INTEGER_FIELDS and type(child) is not int:
                _deny('AUTHORITY_DRIFT')
            if key in _BOOLEAN_FIELDS and type(child) is not bool:
                _deny('AUTHORITY_DRIFT')
            _strict(child)
    elif isinstance(value, list):
        for child in value: _strict(child)


def _visible(value):
    # These hashes are independently validated/recomputed, not contact numbers.
    if isinstance(value, dict):
        return {key: _visible(child) for key, child in value.items()
                if key not in {'contentHash', 'priorContentHash', 'itemHashes'}}
    if isinstance(value, list): return [_visible(child) for child in value]
    return value


class _SavedBatch:
    def __init__(self, batch): self.batch = batch
    def latest_batch_or_none(self, scope): return self.batch


class PriceResearchReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _row(conn, scope, batch_id=None):
        predicate = '' if batch_id is None else ' AND batch_id=%s AND revision=%s'
        params = scope.key if batch_id is None else (*scope.key, batch_id, 1)
        return conn.execute(
            f'''SELECT org_id,project_id,batch_id,revision,content_hash,created_at,
                octet_length(authority_data::text) AS payload_bytes,
                CASE WHEN octet_length(authority_data::text)<={MAX_ROW_BYTES}
                     THEN authority_data ELSE NULL END AS authority_data
                FROM ecommerce_price_research_batch_revision
                WHERE org_id=%s AND project_id=%s{predicate}
                ORDER BY created_at DESC,revision DESC,batch_id ASC LIMIT 1''', params,
        ).fetchone()

    @staticmethod
    def _size(row):
        size = row['payload_bytes']
        if type(size) is not int or size < 1: _deny('AUTHORITY_DRIFT')
        if size > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')
        return size

    @staticmethod
    def _decode(row, scope, cutoff):
        if ((row['org_id'], row['project_id']) != scope.key
                or type(row['revision']) is not int
                or not _aware(row['created_at']) or row['created_at'] > cutoff):
            _deny('AUTHORITY_DRIFT')
        raw = row['authority_data']
        if type(raw) is not dict: _deny('AUTHORITY_DRIFT')
        expected_fields = {field.alias or name for name, field in PriceResearchBatchRevision.model_fields.items()}
        if set(raw) != expected_fields: _deny('AUTHORITY_DRIFT')
        _strict(raw)
        batch = PriceResearchBatchRevision.model_validate(raw)
        if ((batch.tenant.org_id, batch.tenant.project_id) != scope.key
                or batch.batch_id != row['batch_id'] or batch.revision != row['revision']
                or batch.content_hash != row['content_hash']
                or not _aware(batch.created_at) or batch.created_at != row['created_at']):
            _deny('AUTHORITY_DRIFT')
        if set(batch.exact_refs) != set(_REFS.values()): _deny('AUTHORITY_DRIFT')
        request = PreparePriceResearchBatchRequest(
            batchId=batch.batch_id, skillRefs=batch.skill_refs, items=batch.items,
            **{field: batch.exact_refs[key] for field, key in _REFS.items()},
        )
        hashes = [canonical_hash(item.model_dump(mode='json', by_alias=True)) for item in request.items]
        counts = dict(eligible=0, excluded=0, needs_review=0, unknown=0, deduplicated=0)
        for item in request.items: counts[item.disposition.value] += 1
        if (batch.item_hashes != hashes
                or batch.ledger != PriceResearchBatchLedger(input=len(request.items), **counts)):
            _deny('AUTHORITY_DRIFT')
        visible = _visible(batch.model_dump(mode='json', by_alias=True))
        if redact_sensitive(visible) != visible: _deny('PRIVACY_UNAVAILABLE')
        return batch, request, hashes

    @staticmethod
    def _prepared(batch, request, hashes):
        if (batch.lifecycle != 'prepared' or batch.revision != 1 or batch.version != 1
                or batch.prior_content_hash is not None
                or batch.content_hash != canonical_hash({
                    **request.model_dump(mode='json', by_alias=True), 'itemHashes': hashes})):
            _deny('AUTHORITY_DRIFT')

    def read(self, scope):
        try:
            with self._connect(scope) as conn:
                if (conn.read_only is not True or conn.autocommit is not False
                        or conn.isolation_level != IsolationLevel.REPEATABLE_READ):
                    _deny('UNAVAILABLE')
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not _aware(cutoff): _deny('AUTHORITY_DRIFT')
                row = self._row(conn, scope)
                batch = None
                if row is not None:
                    total = self._size(row)
                    batch, request, hashes = self._decode(row, scope, cutoff)
                    if batch.lifecycle == 'prepared':
                        self._prepared(batch, request, hashes)
                    elif batch.lifecycle == 'frozen' and batch.revision == batch.version == 2:
                        prior_row = self._row(conn, scope, batch.batch_id)
                        if prior_row is None: _deny('AUTHORITY_DRIFT')
                        total += self._size(prior_row)
                        if total > MAX_TOTAL_BYTES: _deny('LIMIT_EXCEEDED')
                        prior, prior_request, prior_hashes = self._decode(prior_row, scope, cutoff)
                        self._prepared(prior, prior_request, prior_hashes)
                        current_data = batch.model_dump(mode='json', by_alias=True)
                        prior_data = prior.model_dump(mode='json', by_alias=True)
                        if (batch.batch_id != prior.batch_id or batch.created_at < prior.created_at
                                or batch.prior_content_hash != prior.content_hash
                                or {k: v for k, v in current_data.items() if k not in _MUTABLE_FREEZE}
                                != {k: v for k, v in prior_data.items() if k not in _MUTABLE_FREEZE}
                                or batch.content_hash != canonical_hash({
                                    'prior': prior.content_hash, 'exactRefs': current_data['exactRefs'],
                                    'lifecycle': 'frozen'})):
                            _deny('AUTHORITY_DRIFT')
                    else:
                        _deny('AUTHORITY_DRIFT')
                view = EcommerceWorkshopPriceResearchService(_SavedBatch(batch)).contribution_view(scope, now=cutoff)
                data = view.model_dump(mode='json', by_alias=True)
                data.update(allowedCommands=[], externalEffectsAllowed=False)
                result = type(view).model_validate(data)
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_ROW_BYTES:
                    _deny('LIMIT_EXCEEDED')
                return result
        except PriceResearchReadonlyError:
            raise
        except psycopg.Error:
            _deny('UNAVAILABLE')
        except (ValueError, TypeError, KeyError, AttributeError):
            _deny('AUTHORITY_DRIFT')
