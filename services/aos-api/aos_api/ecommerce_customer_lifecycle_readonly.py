"""Read saved customer revisions without contact resolution or operational admission."""
from datetime import datetime
import json
import re
from time import monotonic

import psycopg
from psycopg import IsolationLevel

from aos_api.db import connect_read_only
from aos_api import ecommerce_workshop_customer_lifecycle as domain
from aos_api.public_contracts import redact_sensitive

MAX_ROW_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * MAX_ROW_BYTES
BATCH_TABLE = 'ecommerce_customer_dialogue_batch_revision'
POLICIES = (
    ('ecommerce_customer_consent_policy_revision', 'policy_id', domain.CustomerConsentPolicyRevision, domain.CreateCustomerConsentPolicyRequest, 'consent_policy'),
    ('ecommerce_customer_segment_revision', 'segment_id', domain.CustomerSegmentRevision, domain.CreateCustomerSegmentRequest, 'segment'),
    ('ecommerce_customer_journey_revision', 'journey_id', domain.CustomerJourneyRevision, domain.CreateCustomerJourneyRequest, 'journey'),
    ('ecommerce_customer_dialogue_strategy_revision', 'dialogue_id', domain.CustomerDialogueStrategyRevision, domain.CreateCustomerDialogueRequest, 'dialogue'),
)
_FREEZE_EXCLUDE = {'revision', 'version', 'lifecycle', 'prior_content_hash', 'content_hash', 'created_by', 'created_at'}
_INTS = {'revision', 'version', 'retentionDays', 'kAnonymityMinimum', 'input', 'eligible', 'excluded',
         'needsReview', 'unknown', 'deduplicated', 'contactResolutionCount', 'actionCount',
         'providerCallCount', 'sendCount', 'externalEffectCount'}
_BOOLS = {'originalsReachable', 'retentionActive', 'kAnonymitySatisfied'}
_NULLABLE_BOOLS = {'retentionActive', 'kAnonymitySatisfied'}
_REFS = {'segment': 'segment_ref', 'journey': 'journey_ref', 'dialogue': 'dialogue_ref',
         'consentPolicy': 'consent_policy_ref', 'frequencyPolicy': 'frequency_policy_ref',
         'channelCapability': 'channel_capability_ref'}


class CustomerLifecycleReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deny(suffix):
    raise CustomerLifecycleReadonlyError('CUSTOMER_LIFECYCLE_READ_' + suffix)


def _aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def _strict(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _INTS and type(child) is not int: _deny('AUTHORITY_DRIFT')
            if key in _BOOLS and type(child) is not bool and not (key in _NULLABLE_BOOLS and child is None):
                _deny('AUTHORITY_DRIFT')
            _strict(child)
    elif isinstance(value, list):
        for child in value: _strict(child)


def _visible(value):
    # Hash syntax and full producer hashes are checked separately; avoid matching
    # accidental digit sequences inside hashes as if they were phone numbers.
    if isinstance(value, dict):
        return {k: _visible(v) for k, v in value.items() if not k.endswith(('Hash', 'Hashes'))}
    if isinstance(value, list): return [_visible(v) for v in value]
    return value


def _privacy(raw):
    visible = _visible(raw)
    if redact_sensitive(visible) != visible: _deny('SENSITIVE_CONTENT')
    serialized = json.dumps(visible, ensure_ascii=False).lower()
    if any(word in serialized for word in ('mobile', 'openid', 'email', 'address', 'nickname', 'avatar', 'rawmessage', 'providerpayload')):
        _deny('SENSITIVE_CONTENT')


def _request(model, item):
    return model.model_validate({name: getattr(item, name) for name in model.model_fields})


def _matches(ref, item, identity):
    return (ref.resource_id == getattr(item, identity) and ref.revision == item.revision
            and ref.content_hash == 'sha256:' + item.content_hash)


class _ValidatedStore:
    def __init__(self, counts, batch): self.counts, self.batch = counts, batch
    def authority_counts(self, _scope): return self.counts
    def latest_batch_or_none_any(self, _scope): return self.batch


class CustomerLifecycleReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _count(conn, scope, table, identity):
        # Identifiers are fixed POLICIES constants, never request input. These
        # are counts of ALL stored revisions, not distinct or active customers.
        alias = ''.join(part.title() if index else part for index, part in enumerate(identity.split('_')))
        valid = (f"length({identity}) BETWEEN 1 AND 200 AND revision>=1 "
                 f"AND content_hash ~ '^[0-9a-f]{{64}}$' "
                 "AND jsonb_typeof(authority_data)='object' "
                 "AND authority_data->'tenant'->'orgId'=to_jsonb(org_id) "
                 "AND authority_data->'tenant'->'projectId'=to_jsonb(project_id) "
                 f"AND authority_data->'{alias}'=to_jsonb({identity}) "
                 "AND authority_data->'revision'=to_jsonb(revision) "
                 "AND authority_data->'contentHash'=to_jsonb(content_hash::text) "
                 "AND jsonb_typeof(authority_data->'createdAt')='string' "
                 "AND authority_data->>'createdAt' ~ '(Z|[+-][0-9]{2}:[0-9]{2})$' "
                 "AND (authority_data->>'createdAt')::timestamptz=created_at")
        return conn.execute(f'SELECT COUNT(*) AS count, '
                            f'SUM(CASE WHEN {valid} THEN 0 ELSE 1 END) AS invalid_count, '
                            f'MAX(created_at) AS latest_created_at FROM {table} '
                            'WHERE org_id=%s AND project_id=%s', scope.key).fetchone()

    @staticmethod
    def _row(conn, scope, table, identity, exact=None):
        # At most one payload per query, bounded in SQL before transfer.
        sql = (f'SELECT org_id,project_id,CASE WHEN length({identity})<=200 THEN {identity} ELSE NULL END AS identity,'
               'revision,CASE WHEN length(content_hash)=64 THEN content_hash ELSE NULL END AS content_hash,'
               'created_at,octet_length(authority_data::text) AS size,'
               f'CASE WHEN octet_length(authority_data::text)<={MAX_ROW_BYTES} THEN authority_data ELSE NULL END AS authority_data '
               f'FROM {table} WHERE org_id=%s AND project_id=%s ')
        params = scope.key
        if exact is not None:
            sql += f'AND {identity}=%s AND revision=%s '
            params = (*params, *exact)
        return conn.execute(sql + f'ORDER BY created_at DESC,revision DESC,{identity} LIMIT 1', params).fetchone()

    @staticmethod
    def _decode(row, model, identity, scope, cutoff):
        if row is None: _deny('AUTHORITY_DRIFT')
        if ((row.get('org_id'), row.get('project_id')) != scope.key
                or not isinstance(row.get('identity'), str) or not 0 < len(row['identity']) <= 200
                or type(row.get('revision')) is not int or row['revision'] < 1
                or not isinstance(row.get('content_hash'), str) or re.fullmatch('[0-9a-f]{64}', row['content_hash']) is None
                or not _aware(row.get('created_at')) or row['created_at'] > cutoff): _deny('AUTHORITY_DRIFT')
        if type(row.get('size')) is not int or row['size'] < 1: _deny('AUTHORITY_DRIFT')
        if row['size'] > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')
        raw = row.get('authority_data')
        if not isinstance(raw, dict): _deny('AUTHORITY_DRIFT')
        _strict(raw)
        item = model.model_validate(raw)
        if item.model_dump(mode='json', by_alias=True) != raw: _deny('AUTHORITY_DRIFT')
        if ((item.tenant.org_id, item.tenant.project_id) != scope.key or getattr(item, identity) != row['identity']
                or item.revision != row['revision'] or item.content_hash != row['content_hash']
                or not _aware(item.created_at) or item.created_at != row['created_at']
                or item.created_at > cutoff): _deny('AUTHORITY_DRIFT')
        if hasattr(item, 'cutoff') and (not _aware(item.cutoff) or item.cutoff > cutoff): _deny('AUTHORITY_DRIFT')
        _privacy(raw)
        return item

    @staticmethod
    def _validate_batch(item, prior=None):
        request = _request(domain.PrepareCustomerDialogueBatchRequest, item)
        refs = {key: getattr(request, attr) for key, attr in _REFS.items()}
        hashes = [domain.canonical_hash(value.model_dump(mode='json', by_alias=True)) for value in request.items]
        counts = {kind: sum(value.disposition == kind for value in request.items) for kind in domain.CustomerBatchDisposition}
        ledger = domain.CustomerDialogueBatchLedger(input=len(request.items), **{key.value: value for key, value in counts.items()})
        binding = domain.canonical_hash({'refs': refs, 'itemHashes': hashes})
        if item.item_hashes != hashes or item.binding_hash != binding or item.ledger != ledger: _deny('AUTHORITY_DRIFT')
        if any(getattr(item, field) != 0 for field in ('contact_resolution_count', 'action_count', 'provider_call_count', 'send_count', 'external_effect_count')):
            _deny('AUTHORITY_DRIFT')
        if item.lifecycle == 'prepared':
            expected = domain.canonical_hash({**request.model_dump(mode='json', by_alias=True), 'ledger': ledger, 'bindingHash': binding})
            if item.revision != 1 or item.version != 1 or item.prior_content_hash is not None or item.content_hash != expected:
                _deny('AUTHORITY_DRIFT')
        elif item.lifecycle == 'frozen':
            if prior is None or prior.lifecycle != 'prepared': _deny('AUTHORITY_DRIFT')
            CustomerLifecycleReadonlyReader._validate_batch(prior)
            if (item.revision != prior.revision + 1 or item.version != prior.version + 1
                    or item.prior_content_hash != prior.content_hash or item.created_at < prior.created_at): _deny('AUTHORITY_DRIFT')
            inherited = prior.model_dump(mode='json', by_alias=True, exclude=_FREEZE_EXCLUDE)
            if item.model_dump(mode='json', by_alias=True, exclude=_FREEZE_EXCLUDE) != inherited: _deny('AUTHORITY_DRIFT')
            expected = domain.canonical_hash({**inherited, 'revision': item.revision, 'version': item.version,
                                              'lifecycle': 'frozen', 'priorContentHash': prior.content_hash})
            if item.content_hash != expected: _deny('AUTHORITY_DRIFT')
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
                for table, identity, _model, _request_model, key in POLICIES:
                    deadline()
                    aggregate = self._count(conn, scope, table, identity)
                    count, invalid, latest = (aggregate[k] for k in ('count', 'invalid_count', 'latest_created_at'))
                    if type(count) is not int or not 0 <= count <= 2**53 - 1: _deny('AUTHORITY_DRIFT')
                    # SUM over no rows is SQL NULL; all other aggregates must be strict integers.
                    if not ((count == 0 and invalid is None) or (type(invalid) is int and invalid == 0)): _deny('AUTHORITY_DRIFT')
                    if count == 0 and latest is not None: _deny('AUTHORITY_DRIFT')
                    if count and (not _aware(latest) or latest > cutoff): _deny('AUTHORITY_DRIFT')
                    counts[key] = count
                deadline()
                selected = self._row(conn, scope, BATCH_TABLE, 'batch_id')
                batch = None
                if selected is not None:
                    total = 0
                    def decode(row, model, identity):
                        nonlocal total
                        item = self._decode(row, model, identity, scope, cutoff)
                        total += row['size']
                        if total > MAX_TOTAL_BYTES: _deny('LIMIT_EXCEEDED')
                        return item
                    batch = decode(selected, domain.CustomerDialogueBatchRevision, 'batch_id')
                    prior = None
                    if batch.lifecycle == 'frozen':
                        deadline()
                        prior = decode(self._row(conn, scope, BATCH_TABLE, 'batch_id', (batch.batch_id, batch.revision - 1)),
                                       domain.CustomerDialogueBatchRevision, 'batch_id')
                    self._validate_batch(batch, prior)
                    facts = {}
                    for table, identity, model, request_model, key in POLICIES:
                        deadline()
                        if counts[key] < 1: _deny('AUTHORITY_DRIFT')
                        ref = getattr(batch, key + '_ref')
                        fact = decode(self._row(conn, scope, table, identity, (ref.resource_id, ref.revision)), model, identity)
                        if not _matches(ref, fact, identity): _deny('AUTHORITY_DRIFT')
                        request = _request(request_model, fact)
                        if fact.content_hash != domain.canonical_hash(request.model_dump(mode='json', by_alias=True)): _deny('AUTHORITY_DRIFT')
                        facts[key] = fact
                    if (facts['segment'].consent_policy_ref != batch.consent_policy_ref
                            or facts['journey'].segment_ref != batch.segment_ref
                            or facts['dialogue'].journey_ref != batch.journey_ref
                            or facts['dialogue'].eval_ref != facts['journey'].eval_ref): _deny('AUTHORITY_DRIFT')
                deadline()
                view = domain.EcommerceWorkshopCustomerLifecycleService(_ValidatedStore(counts, batch)).contribution_view(scope, now=cutoff)
                payload = view.model_dump(mode='json', by_alias=True)
                payload['allowedCommands'] = []
                result = domain.CustomerLifecycleContributionView.model_validate(payload)
                if result.model_dump(mode='json', by_alias=True) != payload: _deny('AUTHORITY_DRIFT')
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_ROW_BYTES: _deny('LIMIT_EXCEEDED')
                deadline()
                return result
        except CustomerLifecycleReadonlyError:
            raise
        except psycopg.Error:
            _deny('AUTHORITY_UNAVAILABLE')
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            _deny('AUTHORITY_DRIFT')
