"""Verify saved contact governance before its original side-effect-free projection."""
from datetime import datetime
import json
import re
from time import monotonic

import psycopg
from psycopg import IsolationLevel

from aos_api.db import connect_read_only
from aos_api import ecommerce_workshop_customer_contact as d
from aos_api import ecommerce_workshop_customer_lifecycle as lifecycle
from aos_api import ecommerce_customer_lifecycle_readonly as life
from aos_api.public_contracts import redact_sensitive

MAX_ROW_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * MAX_ROW_BYTES
MAX_ROWS = 1280
MAX_OBSERVATIONS = 256
_FREQUENCY = 'ecommerce_customer_frequency_policy_revision'
_WITHDRAWAL = 'ecommerce_customer_consent_withdrawal_observation'
_START = 'ecommerce_customer_batch_start_decision_revision'
_RESERVATION = 'ecommerce_customer_frequency_reservation_revision'
_OBSERVATION = 'ecommerce_customer_dispatch_observation'
_SPECS = {
    table: (identity, model, 'created_at', ()) for table, identity, model, _request, _key in life.POLICIES
}
_SPECS.update({
    life.BATCH_TABLE: ('batch_id', lifecycle.CustomerDialogueBatchRevision, 'created_at', ()),
    _FREQUENCY: ('policy_id', d.CustomerFrequencyPolicyRevision, 'created_at', ()),
    _WITHDRAWAL: ('observation_id', d.CustomerConsentWithdrawalObservation, 'observed_at', ('customer_id', 'consent_policy_id', 'sequence')),
    _START: ('decision_id', d.CustomerBatchStartDecisionRevision, 'started_at', ('batch_id',)),
    _RESERVATION: ('reservation_id', d.CustomerFrequencyReservationRevision, 'created_at', ('customer_id', 'policy_id', 'sequence', 'status')),
    _OBSERVATION: ('observation_id', d.CustomerDispatchObservation, 'observed_at', ('decision_id', 'item_key')),
})
_REFS = {'consentPolicy': 'consent_policy_ref', 'frequencyPolicy': 'frequency_policy_ref',
         'actionType': 'action_type_ref', 'impactPreview': 'impact_preview_ref',
         'approvalPolicy': 'approval_policy_ref', 'accountBinding': 'account_binding_ref',
         'adapterCapability': 'adapter_capability_ref', 'content': 'content_ref'}
_BLOCKERS = ['CUSTOMER_CONTACT_PERMIT_REDEMPTION_NOT_AUTHORIZED', 'CUSTOMER_PROVIDER_DISPATCH_NOT_AUTHORIZED', 'CUSTOMER_EXTERNAL_EFFECT_NOT_AUTHORIZED']
_INTS = {'revision', 'version', 'startSequence', 'sequence', 'withdrawalSequence', 'rollingWindowHours',
         'maximumContacts', 'frozenEligible', 'reserved', 'skippedWithdrawn', 'cancelled', 'accepted',
         'applied', 'failed', 'unknown', 'disputed', 'rawContactCount', 'contactResolutionCount',
         'providerCallCount', 'sendCount', 'externalEffectCount'}


class CustomerContactReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deny(suffix):
    raise CustomerContactReadonlyError('CUSTOMER_CONTACT_READ_' + suffix)


def _aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def _strict(raw):
    life._strict(raw)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in _INTS and type(value) is not int and not (key == 'withdrawalSequence' and value is None):
                _deny('AUTHORITY_DRIFT')
            if key.endswith('Hash') and value is not None:
                if not isinstance(value, str) or re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', value) is None:
                    _deny('AUTHORITY_DRIFT')
            if key.endswith('Hashes'):
                if not isinstance(value, list) or any(not isinstance(v, str) or re.fullmatch('[0-9a-f]{64}', v) is None for v in value):
                    _deny('AUTHORITY_DRIFT')
            _strict(value)
    elif isinstance(raw, list):
        for value in raw: _strict(value)


def _privacy(raw):
    visible = life._visible(raw)
    if redact_sensitive(visible) != visible: _deny('SENSITIVE_CONTENT')
    serialized = json.dumps(visible, ensure_ascii=False).lower()
    if any(word in serialized for word in ('mobile', 'openid', 'email', 'address', 'nickname', 'avatar', 'rawmessage', 'providerpayload', 'contactvalue', 'contactdetail')):
        _deny('SENSITIVE_CONTENT')


def _camel(value):
    head, *tail = value.split('_')
    return head + ''.join(part.title() for part in tail)


class _ValidatedStore:
    def __init__(self, counts, start, observations):
        self.counts, self.start, self.observations = counts, start, observations
    def authority_counts(self, _scope): return self.counts
    def latest_start_for_tenant_or_none(self, _scope): return self.start
    def list_dispatch_observations(self, _scope, _identity): return self.observations


class CustomerContactReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _count(conn, scope, table):
        if table not in (_FREQUENCY, _WITHDRAWAL): _deny('AUTHORITY_DRIFT')
        identity, _model, date, _extras = _SPECS[table]
        valid = (f'length({identity}) BETWEEN 1 AND 200 AND revision>=1 '
                 "AND content_hash ~ '^[0-9a-f]{64}$' "
                 "AND jsonb_typeof(authority_data)='object' "
                 "AND authority_data->'tenant'->'orgId'=to_jsonb(org_id) "
                 "AND authority_data->'tenant'->'projectId'=to_jsonb(project_id) "
                 f"AND authority_data->'{_camel(identity)}'=to_jsonb({identity}) "
                 "AND authority_data->>'revision'=revision::text "
                 "AND authority_data->'contentHash'=to_jsonb(content_hash::text) "
                 f"AND jsonb_typeof(authority_data->'{_camel(date)}')='string' "
                 f"AND authority_data->>'{_camel(date)}' ~ '(Z|[+-][0-9]{{2}}:[0-9]{{2}})$' "
                 f"AND (authority_data->>'{_camel(date)}')::timestamptz=created_at")
        if table == _WITHDRAWAL:
            valid += (" AND revision=1 AND authority_data->'customerRef'->'resourceId'=to_jsonb(customer_id)"
                      " AND authority_data->'consentPolicyRef'->'resourceId'=to_jsonb(consent_policy_id)"
                      " AND authority_data->>'sequence'=sequence::text")
        return conn.execute(f'SELECT COUNT(*) AS count,SUM(CASE WHEN {valid} THEN 0 ELSE 1 END) AS invalid_count,'
                            f'MAX(created_at) AS latest_created_at FROM {table} '
                            'WHERE org_id=%s AND project_id=%s', scope.key).fetchone()

    @staticmethod
    def _rows(conn, scope, table, *, exact=None, selection=None, payload=False, limit=1):
        if table not in _SPECS or limit not in (1, 257, 1001): _deny('AUTHORITY_DRIFT')
        identity, _model, _date, extras = _SPECS[table]
        columns = (f'org_id,project_id,CASE WHEN length({identity})<=200 THEN {identity} ELSE NULL END AS identity,'
                   'revision,CASE WHEN length(content_hash)=64 THEN content_hash ELSE NULL END AS content_hash,'
                   'created_at,octet_length(authority_data::text) AS size')
        for key in extras:
            if key == 'sequence': columns += ',sequence'
            else: columns += f',CASE WHEN length({key})<=200 THEN {key} ELSE NULL END AS {key}'
        if payload:
            columns += f',CASE WHEN octet_length(authority_data::text)<={MAX_ROW_BYTES} THEN authority_data ELSE NULL END AS authority_data'
        query = f'SELECT {columns} FROM {table} WHERE org_id=%s AND project_id=%s '
        params = scope.key
        if exact is not None:
            query += f'AND {identity}=%s AND revision=%s '
            params = (*params, *exact)
        if selection is not None:
            if table == _RESERVATION:
                query += 'AND reservation_id=ANY(%s) '
                params = (*params, selection)
            elif table == _WITHDRAWAL:
                customers, sequences, policy = selection
                query += 'AND (customer_id,sequence) IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) AND consent_policy_id=%s '
                params = (*params, customers, sequences, policy)
            elif table == _OBSERVATION:
                query += 'AND decision_id=%s '
                params = (*params, selection)
            else: _deny('AUTHORITY_DRIFT')
        order = f'created_at DESC,revision DESC,{identity}' if limit == 1 else f'created_at,{identity},revision'
        result = conn.execute(query + f'ORDER BY {order} LIMIT {limit}', params)
        return result.fetchone() if limit == 1 else result.fetchall()

    @staticmethod
    def _metadata(row, scope, cutoff):
        if ((row.get('org_id'), row.get('project_id')) != scope.key
                or not isinstance(row.get('identity'), str) or not 0 < len(row['identity']) <= 200
                or type(row.get('revision')) is not int or row['revision'] < 1
                or not isinstance(row.get('content_hash'), str) or re.fullmatch('[0-9a-f]{64}', row['content_hash']) is None
                or not _aware(row.get('created_at')) or row['created_at'] > cutoff): _deny('AUTHORITY_DRIFT')
        if type(row.get('size')) is not int or row['size'] < 1: _deny('AUTHORITY_DRIFT')
        if row['size'] > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')

    @staticmethod
    def _decode(row, table, scope, cutoff):
        identity, model, date, _extras = _SPECS[table]
        raw = row.get('authority_data')
        if not isinstance(raw, dict): _deny('AUTHORITY_DRIFT')
        _strict(raw); _privacy(raw)
        if table in {entry[0] for entry in life.POLICIES} or table == life.BATCH_TABLE:
            return life.CustomerLifecycleReadonlyReader._decode(row, model, identity, scope, cutoff)
        item = model.model_validate(raw)
        expected = d.customer_start_authority_data(item) if table == _START else item.model_dump(mode='json', by_alias=True)
        if expected != raw: _deny('AUTHORITY_DRIFT')
        if ((item.tenant.org_id, item.tenant.project_id) != scope.key or getattr(item, identity) != row['identity']
                or getattr(item, 'revision', 1) != row['revision'] or item.content_hash != row['content_hash']
                or not _aware(getattr(item, date)) or getattr(item, date) != row['created_at']): _deny('AUTHORITY_DRIFT')
        return item

    @staticmethod
    def _validate_start(start, batch, frequency, policies):
        if start.reason is None: _deny('SIGNING_MATERIAL_UNAVAILABLE')
        if (start.revision != 1 or start.lifecycle != 'governance_prepared'
                or start.decision_id != 'customer-start-' + d.canonical_hash([start.tenant.org_id, start.tenant.project_id, batch.batch_id])[:24]
                or start.operational_blockers != _BLOCKERS
                or any(getattr(start, key) != 0 for key in ('contact_resolution_count', 'provider_call_count', 'send_count', 'external_effect_count'))
                or start.content_hash != d.customer_start_signing_hash(start)):
            _deny('AUTHORITY_DRIFT')
        if (start.batch_ref.resource_type != 'CustomerDialogueBatchRevision' or batch.lifecycle != 'frozen'
                or not life._matches(start.batch_ref, batch, 'batch_id') or batch.created_at > start.started_at
                or set(start.exact_refs) != set(_REFS)):
            _deny('AUTHORITY_DRIFT')
        args = {attr: start.exact_refs[key] for key, attr in _REFS.items()}
        items = [d.StartCustomerDialogueItem(itemKey=item.item_key, itemHash=item.item_hash, customerRef=item.customer_ref) for item in start.items]
        request = d.StartCustomerDialogueBatchRequest(expectedVersion=batch.version, expectedContentHash=batch.content_hash,
                    startSequence=start.start_sequence, items=items, reason=start.reason, **args)
        if (request.consent_policy_ref != batch.consent_policy_ref or request.frequency_policy_ref != batch.frequency_policy_ref
                or not life._matches(request.frequency_policy_ref, frequency, 'policy_id')
                or frequency.created_at > start.started_at): _deny('AUTHORITY_DRIFT')
        expected = {(i.item_key, batch.item_hashes[n], d.canonical_hash(i.customer_ref.model_dump(mode='json', by_alias=True)))
                    for n, i in enumerate(batch.items) if i.disposition.value == 'eligible'}
        actual = {(i.item_key, i.item_hash, d.canonical_hash(i.customer_ref.model_dump(mode='json', by_alias=True))) for i in items}
        if actual != expected or [i.item_key for i in start.items] != sorted(i.item_key for i in start.items): _deny('AUTHORITY_DRIFT')
        if (policies['segment'].consent_policy_ref != batch.consent_policy_ref
                or policies['journey'].segment_ref != batch.segment_ref
                or policies['dialogue'].journey_ref != batch.journey_ref
                or policies['dialogue'].eval_ref != policies['journey'].eval_ref
                or start.ledger != d._ledger(start.items)):
            _deny('AUTHORITY_DRIFT')
        for item, request_item in zip(start.items, items):
            binding = d.canonical_hash({'batchRef': start.batch_ref, 'item': request_item, 'exactRefs': start.exact_refs, 'startSequence': start.start_sequence})
            if item.binding_hash != binding or item.action_receipt_ref is not None or item.resolved_state is not None: _deny('AUTHORITY_DRIFT')
            if item.state is d.CustomerContactItemState.SKIPPED_WITHDRAWN:
                if (item.withdrawal_sequence is None or item.withdrawal_sequence > start.start_sequence
                        or any(value is not None for value in (item.reservation, item.permit, item.attempt))): _deny('AUTHORITY_DRIFT')
            elif item.state is d.CustomerContactItemState.RESERVED:
                reservation, permit, attempt = item.reservation, item.permit, item.attempt
                if item.withdrawal_sequence is not None or reservation is None or permit is None or attempt is None: _deny('AUTHORITY_DRIFT')
                if ((reservation.tenant.org_id, reservation.tenant.project_id) != (start.tenant.org_id, start.tenant.project_id)
                        or reservation.reservation_id != 'customer-frequency-' + binding[:24]
                        or reservation.batch_ref != start.batch_ref or reservation.item_key != item.item_key
                        or reservation.customer_ref != item.customer_ref or reservation.frequency_policy_ref != request.frequency_policy_ref
                        or reservation.sequence != start.start_sequence or reservation.status != 'held'
                        or reservation.content_hash != d.canonical_hash({'bindingHash': binding, 'kind': 'frequency'})
                        or not _aware(reservation.created_at) or reservation.created_at > start.started_at): _deny('AUTHORITY_DRIFT')
                if (permit.permit_id != 'customer-permit-' + binding[:24] or permit.customer_ref != item.customer_ref
                        or permit.sequence != start.start_sequence or permit.status != 'not_redeemable'
                        or permit.binding_hash != binding or permit.raw_contact_count != 0): _deny('AUTHORITY_DRIFT')
                if (attempt.attempt_id != 'customer-attempt-' + binding[:24] or attempt.customer_ref != item.customer_ref
                        or attempt.sequence != start.start_sequence or attempt.status != 'prepared'
                        or attempt.binding_hash != binding or attempt.provider_call_count != 0
                        or attempt.outbox_intent_hash != d.canonical_hash({'bindingHash': binding, 'kind': 'outbox-intent'})): _deny('AUTHORITY_DRIFT')
            else: _deny('AUTHORITY_DRIFT')

    def read(self, scope):
        started = monotonic()
        def deadline():
            if monotonic() - started > 10: _deny('LIMIT_EXCEEDED')
        try:
            with self._connect(scope) as conn:
                if conn.read_only is not True or conn.autocommit is not False or conn.isolation_level != IsolationLevel.REPEATABLE_READ:
                    _deny('AUTHORITY_DRIFT')
                conn.execute("SET LOCAL statement_timeout='3000ms'")
                conn.execute("SET LOCAL lock_timeout='500ms'")
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not _aware(cutoff): _deny('AUTHORITY_DRIFT')
                counts = {}
                for table, key in [(_FREQUENCY, 'frequency_policy'), (_WITHDRAWAL, 'withdrawal')]:
                    deadline(); aggregate = self._count(conn, scope, table)
                    count, invalid, latest = (aggregate[k] for k in ('count', 'invalid_count', 'latest_created_at'))
                    if type(count) is not int or not 0 <= count <= 2**53 - 1: _deny('AUTHORITY_DRIFT')
                    if not ((count == 0 and invalid is None) or (type(invalid) is int and invalid == 0)): _deny('AUTHORITY_DRIFT')
                    if count == 0 and latest is not None: _deny('AUTHORITY_DRIFT')
                    if count and (not _aware(latest) or latest > cutoff): _deny('AUTHORITY_DRIFT')
                    counts[key] = count
                total_rows = total_bytes = 0
                def load(table, *, exact=None, selection=None, limit=1, required=True):
                    nonlocal total_rows, total_bytes
                    deadline()
                    first = self._rows(conn, scope, table, exact=exact, selection=selection, limit=limit)
                    before = ([] if first is None else [first]) if limit == 1 else first
                    if limit == 257 and len(before) > MAX_OBSERVATIONS: _deny('LIMIT_EXCEEDED')
                    if limit == 1001 and len(before) > 1000: _deny('LIMIT_EXCEEDED')
                    if not before:
                        if limit == 1 and required: _deny('AUTHORITY_DRIFT')
                        return None if limit == 1 else []
                    for row in before: deadline(); self._metadata(row, scope, cutoff)
                    total_rows += len(before); total_bytes += sum(row['size'] for row in before)
                    if total_rows > MAX_ROWS or total_bytes > MAX_TOTAL_BYTES: _deny('LIMIT_EXCEEDED')
                    # Metadata/aggregate limits are proven before any bulk payload transfer.
                    deadline()
                    second = self._rows(conn, scope, table, exact=exact, selection=selection, limit=limit, payload=True)
                    after = ([] if second is None else [second]) if limit == 1 else second
                    metadata = lambda rows: [{k: v for k, v in row.items() if k != 'authority_data'} for row in rows]
                    if metadata(before) != metadata(after): _deny('AUTHORITY_DRIFT')
                    result = []
                    for row in after:
                        deadline(); result.append((self._decode(row, table, scope, cutoff), row))
                    return result[0] if limit == 1 else result
                selected = load(_START, required=False)
                start = None; observations = []
                if selected is not None:
                    start, start_row = selected
                    if start.reason is None: _deny('SIGNING_MATERIAL_UNAVAILABLE')
                    if start_row['batch_id'] != start.batch_ref.resource_id: _deny('AUTHORITY_DRIFT')
                    batch, _ = load(life.BATCH_TABLE, exact=(start.batch_ref.resource_id, start.batch_ref.revision))
                    prior, _ = load(life.BATCH_TABLE, exact=(batch.batch_id, batch.revision - 1))
                    life.CustomerLifecycleReadonlyReader._validate_batch(batch, prior)
                    policies = {}
                    for table, identity, _model, request_model, key in life.POLICIES:
                        ref = getattr(batch, key + '_ref')
                        item, _ = load(table, exact=(ref.resource_id, ref.revision))
                        if not life._matches(ref, item, identity) or item.created_at > start.started_at: _deny('AUTHORITY_DRIFT')
                        if item.content_hash != d.canonical_hash(life._request(request_model, item).model_dump(mode='json', by_alias=True)): _deny('AUTHORITY_DRIFT')
                        policies[key] = item
                    ref = batch.frequency_policy_ref
                    frequency, _ = load(_FREQUENCY, exact=(ref.resource_id, ref.revision))
                    if counts['frequency_policy'] < 1 or frequency.content_hash != d.canonical_hash(life._request(d.CreateCustomerFrequencyPolicyRequest, frequency).model_dump(mode='json', by_alias=True)):
                        _deny('AUTHORITY_DRIFT')
                    self._validate_start(start, batch, frequency, policies)
                    reserved = {item.reservation.reservation_id: item for item in start.items if item.reservation is not None}
                    if reserved:
                        saved = load(_RESERVATION, selection=list(reserved), limit=1001)
                        if len(saved) != len(reserved) or len({item.reservation_id for item, _ in saved}) != len(saved): _deny('AUTHORITY_DRIFT')
                        for item, row in saved:
                            expected = reserved.get(item.reservation_id)
                            if (expected is None or item != expected.reservation or row['revision'] != 1
                                    or row['customer_id'] != item.customer_ref.resource_id or row['policy_id'] != item.frequency_policy_ref.resource_id
                                    or row['sequence'] != item.sequence or type(row['sequence']) is not int or row['status'] != 'held'):
                                _deny('AUTHORITY_DRIFT')
                    skipped = [item for item in start.items if item.state is d.CustomerContactItemState.SKIPPED_WITHDRAWN]
                    if skipped:
                        if counts['withdrawal'] < 1: _deny('AUTHORITY_DRIFT')
                        saved = load(_WITHDRAWAL, selection=([i.customer_ref.resource_id for i in skipped], [i.withdrawal_sequence for i in skipped], batch.consent_policy_ref.resource_id), limit=1001)
                        witnesses = set()
                        for item, row in saved:
                            request = life._request(d.RecordCustomerConsentWithdrawalRequest, item)
                            digest = d.canonical_hash(request.model_dump(mode='json', by_alias=True))
                            if (item.revision != 1 or item.content_hash != digest or item.observation_id != 'customer-withdrawal-' + digest[:24]
                                    or row['customer_id'] != item.customer_ref.resource_id or row['consent_policy_id'] != item.consent_policy_ref.resource_id
                                    or row['sequence'] != item.sequence or type(row['sequence']) is not int or item.observed_at > start.started_at): _deny('AUTHORITY_DRIFT')
                            for binding in skipped:
                                if item.customer_ref == binding.customer_ref and item.consent_policy_ref == batch.consent_policy_ref and item.sequence == binding.withdrawal_sequence:
                                    witnesses.add(binding.item_key)
                        if witnesses != {item.item_key for item in skipped}: _deny('AUTHORITY_DRIFT')
                    by_key = {item.item_key: item for item in start.items}
                    seen = set()
                    for item, row in load(_OBSERVATION, selection=start.decision_id, limit=257):
                        deadline()
                        request = life._request(d.RecordCustomerDispatchObservationRequest, item)
                        digest = d.canonical_hash(request.model_dump(mode='json', by_alias=True))
                        binding = by_key.get(item.item_key)
                        if (item.revision != 1 or item.observation_id in seen or item.content_hash != digest
                                or item.observation_id != 'customer-dispatch-observation-' + digest[:24]
                                or not life._matches(item.start_decision_ref, start, 'decision_id')
                                or binding is None or binding.state is d.CustomerContactItemState.SKIPPED_WITHDRAWN
                                or row['decision_id'] != start.decision_id or row['item_key'] != item.item_key
                                or item.observed_at < start.started_at): _deny('AUTHORITY_DRIFT')
                        seen.add(item.observation_id); observations.append(item)
                deadline()
                view = d.EcommerceWorkshopCustomerContactService(_ValidatedStore(counts, start, observations), None).contribution_view(scope, now=cutoff)
                payload = view.model_dump(mode='json', by_alias=True); payload['allowedCommands'] = []
                result = d.CustomerContactContributionView.model_validate(payload)
                if result.model_dump(mode='json', by_alias=True) != payload: _deny('AUTHORITY_DRIFT')
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')
                deadline(); return result
        except CustomerContactReadonlyError:
            raise
        except life.CustomerLifecycleReadonlyError as error:
            _deny(error.code.removeprefix('CUSTOMER_LIFECYCLE_READ_'))
        except d.CustomerContactBlocked as error:
            _deny('SIGNING_MATERIAL_UNAVAILABLE' if str(error) == 'CUSTOMER_START_SIGNING_MATERIAL_UNAVAILABLE' else 'AUTHORITY_DRIFT')
        except psycopg.Error:
            _deny('AUTHORITY_UNAVAILABLE')
        except RecursionError:
            _deny('LIMIT_EXCEEDED')
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            _deny('AUTHORITY_DRIFT')
