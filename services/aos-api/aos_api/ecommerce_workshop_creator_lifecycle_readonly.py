"""Bounded saved-authority projection; never admits creator operations."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg
from psycopg import IsolationLevel

from aos_api.db import connect_read_only
from aos_api.ecommerce_workshop_creator_lifecycle import (
    CreatorBatchStartDecisionRevision, CreatorContractRevision,
    CreatorDeliveryObservation, CreatorLaneObservation, CreatorLifecycleView,
    CreatorRelationshipRevision, _ledger,
)
from aos_api.tenant_scope import TenantScope

MAX_ROWS = 1000
MAX_ITEM_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 1024 * 1024

# Server-owned identifiers. Neither requests nor stored JSON choose a query.
_SPECS = {
    'start': ('ecommerce_creator_batch_start_decision_revision', 'decision_id',
              CreatorBatchStartDecisionRevision, 'started_at'),
    'lane': ('ecommerce_creator_lane_observation', 'observation_id',
             CreatorLaneObservation, 'observed_at'),
    'contract': ('ecommerce_creator_contract_revision', 'collaboration_id',
                 CreatorContractRevision, 'created_at'),
    'delivery': ('ecommerce_creator_delivery_observation', 'observation_id',
                 CreatorDeliveryObservation, 'observed_at'),
    'relationship': ('ecommerce_creator_relationship_revision', 'relationship_id',
                     CreatorRelationshipRevision, 'created_at'),
}


class CreatorLifecycleReadonlyError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _deny(suffix: str):
    raise CreatorLifecycleReadonlyError('CREATOR_LIFECYCLE_READ_' + suffix)


class CreatorLifecycleReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _rows(conn, scope, cutoff, kind, decision_id=None):
        table, identity, _, _ = _SPECS[kind]
        extra_column = 'decision_id,' if kind == 'lane' else ''
        extra_filter = ' AND decision_id=%s' if kind == 'lane' else ''
        direction = ' DESC' if kind == 'start' else ''
        limit = 1 if kind == 'start' else MAX_ROWS + 1
        sql = (
            f'SELECT org_id,project_id,{identity} AS entity_id,revision,content_hash,created_at,'
            f'{extra_column}octet_length(authority_data::text) AS authority_bytes,'
            f'CASE WHEN octet_length(authority_data::text)<={MAX_ITEM_BYTES} '
            'THEN authority_data ELSE NULL END AS authority_data '
            f'FROM {table} WHERE org_id=%s AND project_id=%s AND created_at<=%s'
            f'{extra_filter} ORDER BY created_at{direction},revision{direction},{identity}{direction} LIMIT %s'
        )
        params = (*scope.key, cutoff)
        if kind == 'lane':
            params = (*params, decision_id)
        rows = conn.execute(sql, (*params, limit)).fetchall()
        if len(rows) > MAX_ROWS or kind == 'start' and len(rows) > 1:
            _deny('LIMIT_EXCEEDED')
        return rows

    @staticmethod
    def _decode(row, kind, scope, cutoff, total):
        _, _, model, timestamp = _SPECS[kind]
        size = row['authority_bytes']
        if type(size) is not int or size < 1:
            _deny('AUTHORITY_DRIFT')
        if size > MAX_ITEM_BYTES or total + size > MAX_TOTAL_BYTES:
            _deny('LIMIT_EXCEEDED')
        value = model.model_validate(row['authority_data'])
        # Delivery observations are append-only v1; their DTO has no revision.
        revision = 1 if kind == 'delivery' else value.revision
        if ((row['org_id'], row['project_id']) != scope.key
                or (value.tenant.org_id, value.tenant.project_id) != scope.key
                or value.content_hash != row['content_hash']
                or type(row['revision']) is not int or revision != row['revision']):
            _deny('AUTHORITY_DRIFT')
        identity = {
            'start': 'decision_id', 'lane': 'observation_id',
            'contract': 'collaboration_id', 'delivery': 'observation_id',
            'relationship': 'relationship_id',
        }[kind]
        created = row['created_at']
        observed = getattr(value, timestamp)
        if (getattr(value, identity) != row['entity_id']
                or not isinstance(created, datetime) or created.utcoffset() is None
                or observed.utcoffset() is None or observed != created or created > cutoff):
            _deny('AUTHORITY_DRIFT')
        return value, total + size

    def read(self, scope: TenantScope) -> CreatorLifecycleView:
        try:
            with self._connect(scope) as conn:
                if (conn.read_only is not True or conn.autocommit is not False
                        or conn.isolation_level != IsolationLevel.REPEATABLE_READ):
                    _deny('CONNECTION_INVALID')
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not isinstance(cutoff, datetime) or cutoff.utcoffset() is None:
                    _deny('AUTHORITY_DRIFT')
                total = 0
                values: dict[str, list[Any]] = {}
                for kind in _SPECS:
                    start = values.get('start', [])
                    rows = ([] if kind == 'lane' and not start else
                            self._rows(conn, scope, cutoff, kind,
                                       start[0].decision_id if kind == 'lane' else None))
                    values[kind] = []
                    for row in rows:
                        value, total = self._decode(row, kind, scope, cutoff, total)
                        if kind == 'lane':
                            current = start[0]
                            ref = value.start_decision_ref
                            if (row['decision_id'] != current.decision_id
                                    or ref.resource_type != 'CreatorBatchStartDecisionRevision'
                                    or ref.resource_id != current.decision_id
                                    or ref.revision != current.revision
                                    or ref.content_hash != current.content_hash
                                    or value.lane_id not in {lane.lane_id for lane in current.lanes}):
                                _deny('AUTHORITY_DRIFT')
                        values[kind].append(value)
                start = values['start'][0] if values['start'] else None
                lanes = list(start.lanes) if start else []
                latest = {observation.lane_id: observation for observation in values['lane']}
                if start:
                    lanes = [lane.model_copy(update={
                        'outcome': latest[lane.lane_id].outcome,
                        'resolved_outcome': latest[lane.lane_id].resolved_outcome,
                        'action_receipt_ref': latest[lane.lane_id].action_receipt_ref,
                    }) if lane.lane_id in latest else lane for lane in lanes]
                    start = start.model_copy(update={
                        'lanes': lanes, 'ledger': _ledger(lanes, start.ledger.eligible_items),
                    })
                result = CreatorLifecycleView(
                    tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                    evaluatedAt=cutoff, latestStart=start,
                    ledger=_ledger(lanes, start.ledger.eligible_items if start else 0),
                    contracts=values['contract'], deliveries=values['delivery'],
                    relationships=values['relationship'],
                    blockers=list(start.operational_blockers) if start else ['CREATOR_BATCH_START_NOT_AVAILABLE'],
                    allowedCommands=[], externalEffectsAllowed=False,
                )
                if len(result.model_dump_json(by_alias=True).encode('utf-8')) > MAX_TOTAL_BYTES:
                    _deny('LIMIT_EXCEEDED')
                return result
        except CreatorLifecycleReadonlyError:
            raise
        except psycopg.Error:
            _deny('UNAVAILABLE')
        except (ValueError, KeyError, TypeError, AttributeError):
            _deny('AUTHORITY_DRIFT')
