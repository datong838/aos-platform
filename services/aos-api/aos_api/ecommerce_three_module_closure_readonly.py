"""Bounded saved closure evidence, never compile/bind/consume authority."""
from datetime import datetime
import json
import math
from time import monotonic

import psycopg
from psycopg import IsolationLevel

from aos_api.aip_contracts import HandoffResourceRef, ResourceRef
from aos_api.db import connect_read_only
from aos_api.ecommerce_workshop_three_module_closure import (
    CompileThreeModuleClosureRequest, EcommerceWorkshopThreeModuleClosureService,
    ThreeModule, ThreeModuleClosureRevision, ThreeModuleEffectBindingRevision,
    ThreeModuleHandoffBindingRevision, ThreeModuleUsageBindingRevision,
    _ledger, canonical_hash,
)
from aos_api.ecommerce_workshop_three_module_closure_store import _STATUS
from aos_api.public_contracts import redact_sensitive

MAX_ITEM_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
_TABLES = {
    'closure': ('ecommerce_three_module_closure_revision', ThreeModuleClosureRevision),
    'usage': ('ecommerce_three_module_usage_binding_revision', ThreeModuleUsageBindingRevision),
    'effect': ('ecommerce_three_module_effect_binding_revision', ThreeModuleEffectBindingRevision),
    'handoff': ('ecommerce_three_module_handoff_binding_revision', ThreeModuleHandoffBindingRevision),
}


class CreatorClosureReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class PriceClosureReadonlyError(CreatorClosureReadonlyError):
    """Stable price-specific boundary around the shared saved-record codec."""


def _deny(suffix):
    raise CreatorClosureReadonlyError('CREATOR_CLOSURE_READ_' + suffix)


def _time(value, cutoff):
    return isinstance(value, datetime) and value.utcoffset() is not None and value <= cutoff


def _ref_revision(raw):
    if type(raw) is not dict or type(raw.get('revision')) is not int or raw['revision'] < 1:
        _deny('AUTHORITY_DRIFT')


def _strict_price_raw(value):
    integers = {'revision', 'total', 'inProgress', 'succeeded', 'failed', 'unknown',
                'disputed', 'skipped', 'sampleCount', 'minSample', 'disclosureRefCount'}
    if isinstance(value, dict):
        for key, child in value.items():
            # Task/TaskRun use the public ResourceRef contract with a STRING
            # revision; the existing typed handoff validator checks them below.
            if key in {'taskRef', 'taskRunRef'}: continue
            if key in integers and type(child) is not int: _deny('AUTHORITY_DRIFT')
            if key in {'accepted', 'effectCompleted'} and type(child) is not bool: _deny('AUTHORITY_DRIFT')
            if key in {'quantity', 'adjustmentTotal'} and child is not None:
                if type(child) not in (int, float) or not math.isfinite(child): _deny('AUTHORITY_DRIFT')
            _strict_price_raw(child)
    elif isinstance(value, list):
        for child in value: _strict_price_raw(child)


def _visible(value):
    # Typed hashes and derived identities are checked separately; hash digits are
    # not contact numbers. Every other public string retains the existing guard.
    if isinstance(value, dict):
        return {key: _visible(child) for key, child in value.items()
                if key not in {'contentHash', 'closureId', 'bindingId'}}
    if isinstance(value, list):
        return [_visible(child) for child in value]
    return value


class _SavedBindings:
    def __init__(self, bindings): self.bindings = bindings
    def latest_bindings(self, scope, module): return self.bindings


class CreatorClosureReadonlyReader:
    _module = ThreeModule.CREATOR

    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _row(conn, scope, kind, closure_id=None, module=ThreeModule.CREATOR):
        table, _ = _TABLES[kind]
        identity = 'closure_id' if kind == 'closure' else 'binding_id'
        source = 'source_id' if kind == 'closure' else 'NULL AS source_id'
        resource = f'{identity} AS resource_id'
        closure_column = 'closure_id'
        if module is ThreeModule.PRICE:
            resource = f'CASE WHEN length({identity})<=240 THEN {identity} ELSE NULL END AS resource_id'
            closure_column = 'CASE WHEN length(closure_id)<=240 THEN closure_id ELSE NULL END AS closure_id'
            if kind == 'closure': source = 'CASE WHEN length(source_id)<=240 THEN source_id ELSE NULL END AS source_id'
        predicate = 'module=%s' if kind == 'closure' else 'closure_id=%s'
        return conn.execute(
            f'''SELECT org_id,project_id,{resource},{closure_column},
                revision,module,{source},content_hash,created_at,
                octet_length(authority_data::text) AS payload_bytes,
                CASE WHEN octet_length(authority_data::text)<={MAX_ITEM_BYTES}
                     THEN authority_data ELSE NULL END AS authority_data
                FROM {table} WHERE org_id=%s AND project_id=%s AND {predicate}
                ORDER BY created_at DESC,{identity} LIMIT 1''',
            (*scope.key, module.value if kind == 'closure' else closure_id),
        ).fetchone()

    @staticmethod
    def _decode(row, scope, kind, cutoff, closure=None, module=ThreeModule.CREATOR):
        if (row['org_id'], row['project_id']) != scope.key:
            _deny('AUTHORITY_DRIFT')
        if (type(row['revision']) is not int or row['revision'] != 1
                or not _time(row['created_at'], cutoff)):
            _deny('AUTHORITY_DRIFT')
        raw = row['authority_data']
        if type(raw) is not dict or type(raw.get('revision')) is not int or raw['revision'] != 1:
            _deny('AUTHORITY_DRIFT')
        model = _TABLES[kind][1]
        if module is ThreeModule.PRICE: _strict_price_raw(raw)
        item = model.model_validate(raw)
        if module is ThreeModule.PRICE and item.model_dump(mode='json', by_alias=True) != raw:
            _deny('AUTHORITY_DRIFT')
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            _deny('AUTHORITY_DRIFT')
        if item.content_hash != row['content_hash']:
            _deny('AUTHORITY_DRIFT')
        if kind == 'closure':
            _ref_revision(raw['sourceRef'])
            CompileThreeModuleClosureRequest(module=module, sourceRef=item.source_ref)
            identity = 'three-module-closure-' + canonical_hash(
                [*scope.key, module, item.source_ref.resource_id])[:24]
            if (item.module is not module or row['module'] != module.value
                    or row['resource_id'] != identity or item.closure_id != identity
                    or row['closure_id'] != identity or row['source_id'] != item.source_ref.resource_id
                    or item.compiled_at != row['created_at'] or not _time(item.compiled_at, cutoff)
                    or item.ledger != _ledger(item.items)):
                _deny('AUTHORITY_DRIFT')
            keys = set()
            for original, source in zip(item.items, raw['items'], strict=True):
                _ref_revision(source['originalRef'])
                if source.get('receiptRef') is not None: _ref_revision(source['receiptRef'])
                expected = item.source_ref.model_copy(update={
                    'resource_id': item.source_ref.resource_id + ':' + original.item_key})
                if (original.item_key in keys or original.original_ref != expected
                        or _STATUS.get(original.original_status) != original.canonical_outcome):
                    _deny('AUTHORITY_DRIFT')
                keys.add(original.item_key)
            payload = dict(module=item.module, sourceRef=item.source_ref, items=item.items)
        else:
            _ref_revision(raw['closureRef'])
            exact = EcommerceWorkshopThreeModuleClosureService._ref(
                'ThreeModuleClosureRevision', closure.closure_id, closure.content_hash)
            if (row['module'] not in (None, module.value) or row['closure_id'] != closure.closure_id
                    or item.closure_ref != exact or item.bound_at != row['created_at']
                    or not _time(item.bound_at, cutoff) or item.bound_at < closure.compiled_at):
                _deny('AUTHORITY_DRIFT')
            payload = {'closureRef': item.closure_ref}
            if kind == 'usage':
                _ref_revision(raw['usageReceiptRef'])
                if item.usage_receipt_ref.resource_type != 'UsageReceipt': _deny('AUTHORITY_DRIFT')
                if module is ThreeModule.PRICE and item.settlement != item.quality: _deny('AUTHORITY_DRIFT')
                payload.update(usageReceiptRef=item.usage_receipt_ref, lineageId=item.lineage_id,
                               quality=item.quality, quantity=item.quantity, unit=item.unit,
                               adjustmentTotal=item.adjustment_total, settlement=item.settlement)
            elif kind == 'effect':
                _ref_revision(raw['effectReviewRef'])
                if item.effect_review_ref.resource_type != 'EffectReviewRevision': _deny('AUTHORITY_DRIFT')
                if (not _time(item.observed_at, item.bound_at)
                        or item.cutoff_at.utcoffset() is None
                        or (item.maturity_status == 'mature' and item.cutoff_at > item.observed_at)
                        or type(raw['accepted']) is not bool or type(raw['effectCompleted']) is not bool):
                    _deny('AUTHORITY_DRIFT')
                payload.update(effectReviewRef=item.effect_review_ref, maturityStatus=item.maturity_status,
                               accepted=item.accepted, effectCompleted=item.effect_completed,
                               sampleCount=item.sample_count, minSample=item.min_sample,
                               cutoffAt=item.cutoff_at, observedAt=item.observed_at)
            else:
                _ref_revision(raw['handoffRef'])
                if item.handoff_ref.resource_type != 'HandoffEnvelope': _deny('AUTHORITY_DRIFT')
                for value, expected_type in [(item.task_ref, 'Task'), (item.task_run_ref, 'TaskRun')]:
                    ref_model = HandoffResourceRef if 'contentHash' in value else ResourceRef
                    public_ref = ref_model.model_validate(value)
                    if public_ref.resource_type != expected_type:
                        _deny('CONTENT_UNSUPPORTED')
                payload.update(handoffRef=item.handoff_ref, transportStatus=item.transport_status,
                               businessDecision=item.business_decision, taskRef=item.task_ref,
                               taskRunRef=item.task_run_ref, disclosureRefCount=item.disclosure_ref_count)
            identity = 'three-module-' + kind + '-' + canonical_hash(payload)[:24]
            if row['resource_id'] != identity or item.binding_id != identity:
                _deny('AUTHORITY_DRIFT')
        if canonical_hash(payload) != item.content_hash:
            _deny('AUTHORITY_DRIFT')
        visible = _visible(item.model_dump(mode='json', by_alias=True))
        if redact_sensitive(visible) != visible:
            _deny('PRIVACY_UNAVAILABLE')
        if module is ThreeModule.PRICE:
            serialized = json.dumps(visible, ensure_ascii=False).lower()
            if any(word in serialized for word in ('mobile', 'openid', 'email', 'address', 'contactvalue', 'providerpayload')):
                _deny('CONTENT_UNSUPPORTED')
        return item

    def read(self, scope):
        started = monotonic()
        def deadline():
            if self._module is ThreeModule.PRICE and monotonic() - started > 10: _deny('LIMIT_EXCEEDED')
        try:
            if self._module not in (ThreeModule.CREATOR, ThreeModule.PRICE): _deny('CONTENT_UNSUPPORTED')
            with self._connect(scope) as conn:
                if (conn.read_only is not True or conn.autocommit is not False
                        or conn.isolation_level != IsolationLevel.REPEATABLE_READ):
                    _deny('UNAVAILABLE')
                if self._module is ThreeModule.PRICE:
                    conn.execute("SET LOCAL statement_timeout='3000ms'")
                    conn.execute("SET LOCAL lock_timeout='500ms'")
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not _time(cutoff, cutoff): _deny('AUTHORITY_DRIFT')
                bindings, total = dict(closure=None, usage=None, effect=None, handoff=None), 0
                for kind in _TABLES:
                    deadline()
                    if kind != 'closure' and bindings['closure'] is None: break
                    row = self._row(conn, scope, kind, getattr(bindings['closure'], 'closure_id', None), self._module)
                    if row is None: continue
                    size = row['payload_bytes']
                    if type(size) is not int or size < 1: _deny('AUTHORITY_DRIFT')
                    total += size
                    if size > MAX_ITEM_BYTES or total > MAX_TOTAL_BYTES: _deny('LIMIT_EXCEEDED')
                    bindings[kind] = self._decode(row, scope, kind, cutoff, bindings['closure'], self._module)
                view = EcommerceWorkshopThreeModuleClosureService(_SavedBindings(bindings)).contribution_view(
                    scope, self._module, now=cutoff)
                # Revalidate a complete public DTO; no validation-bypassing copy.
                data = view.model_dump(mode='json', by_alias=True)
                data.update(allowedCommands=[], handoffConsumeAllowed=False,
                            memoryPromotionAllowed=False, externalEffectsAllowed=False)
                result = type(view).model_validate(data)
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_TOTAL_BYTES:
                    _deny('LIMIT_EXCEEDED')
                deadline()
                return result
        except CreatorClosureReadonlyError:
            raise
        except psycopg.Error:
            _deny('UNAVAILABLE')
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            _deny('AUTHORITY_DRIFT')


class PriceClosureReadonlyReader(CreatorClosureReadonlyReader):
    _module = ThreeModule.PRICE

    def read(self, scope):
        try:
            return super().read(scope)
        except CreatorClosureReadonlyError as exc:
            raise PriceClosureReadonlyError(exc.code.replace('CREATOR_CLOSURE_READ_', 'PRICE_CLOSURE_READ_', 1)) from exc
