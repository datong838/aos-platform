"""Bounded verification of saved dispositions; no gate/receipt consumer or writes."""
from datetime import datetime
import re
from time import monotonic

import psycopg
from psycopg import IsolationLevel

from aos_api.db import connect_read_only
from aos_api.ecommerce_workshop_price_disposition import (
    CreatePriceCaseRequest, CreatePriceDispositionContractRequest,
    EcommerceWorkshopPriceDispositionService, PreparePriceDispositionRequest,
    PriceCaseRevision, PriceDispositionContractRevision, PriceDispositionObservation,
    PriceDispositionRevision, RecordPriceDispositionObservationRequest,
    REQUIRED_GATE_TYPES, canonical_hash, price_disposition_observation_rules,
    price_disposition_operational_blockers,
)
from aos_api.public_contracts import redact_sensitive

MAX_ROWS = 512
MAX_ROW_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * MAX_ROW_BYTES
_TABLES = (
    ('ecommerce_price_case_revision', 'case_id', PriceCaseRevision),
    ('ecommerce_price_disposition_contract_revision', 'contract_id', PriceDispositionContractRevision),
    ('ecommerce_price_disposition_revision', 'disposition_id', PriceDispositionRevision),
    ('ecommerce_price_disposition_observation', 'observation_id', PriceDispositionObservation),
)
_FREEZE_EXCLUDE = {'revision', 'version', 'lifecycle', 'prior_content_hash', 'content_hash', 'created_by', 'created_at'}
_INTS = {'revision', 'version', 'providerCallCount', 'notificationSendCount', 'repricingCount', 'externalEffectCount'}
_BOOLS = {'executionAllowed', 'externalEffectCapable'}


class PriceDispositionReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deny(suffix):
    raise PriceDispositionReadonlyError('PRICE_DISPOSITION_READ_' + suffix)


def _aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def _strict(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _INTS and type(child) is not int: _deny('AUTHORITY_DRIFT')
            if key in _BOOLS and type(child) is not bool: _deny('AUTHORITY_DRIFT')
            _strict(child)
    elif isinstance(value, list):
        for child in value: _strict(child)


def _visible(value):
    if isinstance(value, dict):
        return {key: _visible(child) for key, child in value.items() if not key.endswith('Hash')}
    if isinstance(value, list): return [_visible(child) for child in value]
    return value


def _request(model, item):
    return model.model_validate({name: getattr(item, name) for name in model.model_fields})


def _matches(ref, item, identity):
    return (ref.resource_id == getattr(item, identity) and ref.revision == item.revision
            and ref.content_hash == 'sha256:' + item.content_hash)


class _ValidatedStore:
    def __init__(self, cases, dispositions, observations):
        self.cases, self.dispositions, self.observations = cases, dispositions, observations
    def list_cases(self, _scope): return self.cases
    def list_dispositions(self, _scope): return self.dispositions
    def list_observations(self, _scope): return self.observations


class EcommercePriceDispositionReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _query(conn, scope, table, identity, payload=False):
        # All interpolated identifiers originate in the fixed _TABLES tuple.
        columns = (f'org_id,project_id,CASE WHEN length({identity})<=200 THEN {identity} ELSE NULL END AS identity,'
                   'revision,CASE WHEN length(content_hash)=64 THEN content_hash ELSE NULL END AS content_hash,'
                   'created_at,octet_length(authority_data::text) AS size')
        if payload:
            columns += f',CASE WHEN octet_length(authority_data::text)<={MAX_ROW_BYTES} THEN authority_data ELSE NULL END AS authority_data'
        return conn.execute(f'SELECT {columns} FROM {table} WHERE org_id=%s AND project_id=%s '
                            f'ORDER BY created_at,revision,{identity} LIMIT 513', scope.key).fetchall()

    @staticmethod
    def _metadata(row, scope, cutoff):
        if (row.get('org_id'), row.get('project_id')) != scope.key: _deny('AUTHORITY_DRIFT')
        if (not isinstance(row.get('identity'), str) or not 0 < len(row['identity']) <= 200
                or type(row.get('revision')) is not int or row['revision'] < 1
                or not isinstance(row.get('content_hash'), str)
                or re.fullmatch('[0-9a-f]{64}', row['content_hash']) is None
                or not _aware(row.get('created_at')) or row['created_at'] > cutoff):
            _deny('AUTHORITY_DRIFT')
        if type(row.get('size')) is not int or row['size'] < 1: _deny('AUTHORITY_DRIFT')
        if row['size'] > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')

    @staticmethod
    def _decode(row, model, identity, scope, cutoff):
        raw = row.get('authority_data')
        if not isinstance(raw, dict): _deny('AUTHORITY_DRIFT')
        _strict(raw)
        item = model.model_validate(raw)
        if item.model_dump(mode='json', by_alias=True) != raw: _deny('AUTHORITY_DRIFT')
        if ((item.tenant.org_id, item.tenant.project_id) != scope.key
                or getattr(item, identity) != row['identity'] or item.revision != row['revision']
                or item.content_hash != row['content_hash']): _deny('AUTHORITY_DRIFT')
        at = item.observed_at if isinstance(item, PriceDispositionObservation) else item.created_at
        if not _aware(at) or at != row['created_at'] or at > cutoff: _deny('AUTHORITY_DRIFT')
        if hasattr(item, 'detected_at') and (not _aware(item.detected_at) or item.detected_at > cutoff): _deny('AUTHORITY_DRIFT')
        visible = _visible(raw)
        if redact_sensitive(visible) != visible: _deny('SENSITIVE_CONTENT')
        return item

    @staticmethod
    def _validate(cases, contracts, dispositions, observations):
        def index(items, identity):
            result = {}
            for item in items:
                key = (getattr(item, identity), item.revision)
                if key in result: _deny('AUTHORITY_DRIFT')
                result[key] = item
            return result
        case_index = index(cases, 'case_id')
        contract_index = index(contracts, 'contract_id')
        disposition_index = index(dispositions, 'disposition_id')
        index(observations, 'observation_id')
        for case in cases:
            request = _request(CreatePriceCaseRequest, case)
            if (case.revision != 1 or case.lifecycle != 'open'
                    or case.content_hash != canonical_hash(request.model_dump(mode='json', by_alias=True))): _deny('AUTHORITY_DRIFT')
        for contract in contracts:
            request = _request(CreatePriceDispositionContractRequest, contract)
            expected = {**request.model_dump(mode='json', by_alias=True),
                'requiredGateTypes': REQUIRED_GATE_TYPES[contract.kind],
                'externalEffectCapable': contract.kind.value in ('external_notice', 'repricing')}
            if contract.content_hash != canonical_hash(expected): _deny('AUTHORITY_DRIFT')
        for item in dispositions:
            request = _request(PreparePriceDispositionRequest, item)
            case = case_index.get((request.case_ref.resource_id, request.case_ref.revision))
            contract = contract_index.get((request.contract_ref.resource_id, request.contract_ref.revision))
            if (case is None or contract is None or not _matches(request.case_ref, case, 'case_id')
                    or not _matches(request.contract_ref, contract, 'contract_id') or item.kind != contract.kind): _deny('AUTHORITY_DRIFT')
            targets = {ref.resource_id: ref for ref in case.target_refs}
            if any(targets.get(ref.resource_id) != ref for ref in item.target_refs): _deny('AUTHORITY_DRIFT')
            if set(item.gate_refs) != set(contract.required_gate_types): _deny('AUTHORITY_DRIFT')
            if any(item.gate_refs[k].resource_type != typ for k, typ in contract.required_gate_types.items()): _deny('AUTHORITY_DRIFT')
            binding = canonical_hash({'case': request.case_ref, 'contract': request.contract_ref,
                'targets': request.target_refs, 'gates': request.gate_refs,
                'purpose': request.purpose, 'requestedOutcome': request.requested_outcome})
            if (item.binding_hash != binding or item.operational_blockers != price_disposition_operational_blockers(item.kind)
                    or item.execution_allowed is not False
                    or (item.provider_call_count, item.notification_send_count, item.repricing_count, item.external_effect_count) != (0, 0, 0, 0)):
                _deny('AUTHORITY_DRIFT')
            if item.lifecycle == 'prepared':
                expected = canonical_hash({**request.model_dump(mode='json', by_alias=True), 'kind': item.kind,
                    'bindingHash': binding, 'operationalBlockers': item.operational_blockers})
                if item.revision != 1 or item.version != 1 or item.prior_content_hash is not None or item.content_hash != expected: _deny('AUTHORITY_DRIFT')
            elif item.lifecycle == 'frozen':
                prior = disposition_index.get((item.disposition_id, item.revision - 1))
                if (prior is None or prior.lifecycle != 'prepared' or prior.revision != 1 or prior.version != 1
                        or item.version != prior.version + 1 or item.prior_content_hash != prior.content_hash
                        or item.created_at < prior.created_at): _deny('AUTHORITY_DRIFT')
                inherited = prior.model_dump(mode='json', by_alias=True, exclude=_FREEZE_EXCLUDE)
                if item.model_dump(mode='json', by_alias=True, exclude=_FREEZE_EXCLUDE) != inherited: _deny('AUTHORITY_DRIFT')
                expected = canonical_hash({**inherited, 'revision': item.revision, 'version': item.version,
                    'lifecycle': 'frozen', 'priorContentHash': prior.content_hash})
                if item.content_hash != expected: _deny('AUTHORITY_DRIFT')
            else: _deny('AUTHORITY_DRIFT')
        for item in observations:
            request = _request(RecordPriceDispositionObservationRequest, item)
            disposition = disposition_index.get((request.disposition_ref.resource_id, request.disposition_ref.revision))
            if (disposition is None or disposition.lifecycle != 'frozen'
                    or not _matches(request.disposition_ref, disposition, 'disposition_id')): _deny('AUTHORITY_DRIFT')
            receipt_type, outcomes = price_disposition_observation_rules(disposition.kind)
            digest = canonical_hash(request.model_dump(mode='json', by_alias=True))
            if (item.revision != 1 or item.receipt_ref.resource_type != receipt_type or item.outcome not in outcomes
                    or item.content_hash != digest or item.observation_id != 'price-disposition-observation-' + digest[:24]): _deny('AUTHORITY_DRIFT')

    def read(self, scope):
        started = monotonic()
        def deadline():
            if monotonic() - started > 10: _deny('LIMIT_EXCEEDED')
        try:
            with self._connect(scope) as conn:
                if (conn.read_only is not True or conn.autocommit is not False
                        or conn.isolation_level != IsolationLevel.REPEATABLE_READ): _deny('AUTHORITY_DRIFT')
                conn.execute("SET LOCAL statement_timeout='3000ms'")
                conn.execute("SET LOCAL lock_timeout='500ms'")
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not _aware(cutoff): _deny('AUTHORITY_DRIFT')
                metadata = []
                total_count = total_size = 0
                for table, identity, _model in _TABLES:
                    deadline()
                    rows = self._query(conn, scope, table, identity)
                    total_count += len(rows)
                    if len(rows) > MAX_ROWS or total_count > MAX_ROWS: _deny('LIMIT_EXCEEDED')
                    for row in rows:
                        self._metadata(row, scope, cutoff)
                        total_size += row['size']
                    if total_size > MAX_TOTAL_BYTES: _deny('LIMIT_EXCEEDED')
                    metadata.append(rows)
                decoded = []
                for (table, identity, model), before in zip(_TABLES, metadata):
                    deadline()
                    rows = self._query(conn, scope, table, identity, payload=True)
                    if [{k: v for k, v in row.items() if k != 'authority_data'} for row in rows] != before: _deny('AUTHORITY_DRIFT')
                    decoded.append([self._decode(row, model, identity, scope, cutoff) for row in rows])
                deadline()
                cases, contracts, dispositions, observations = decoded
                self._validate(cases, contracts, dispositions, observations)
                result = EcommerceWorkshopPriceDispositionService(
                    _ValidatedStore(cases, dispositions, observations), None).contribution_view(scope, now=cutoff)
                result = result.model_copy(update={'allowed_commands': [], 'repricing_enabled': False, 'external_effects_allowed': False})
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')
                deadline()
                return result
        except PriceDispositionReadonlyError:
            raise
        except psycopg.Error:
            _deny('AUTHORITY_UNAVAILABLE')
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            _deny('AUTHORITY_DRIFT')
