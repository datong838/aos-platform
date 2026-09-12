"""Original canonical command storage; never grants execution authority."""
import hashlib
import json
import re
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from psycopg import sql
from aos_api.ecom_core_models import BatchCommand
from aos_api.tenant_scope import TenantScope


class IngressJournalConflict(RuntimeError):
    pass


def _digest(envelope):
    raw = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('INGRESS_COMMAND_TOO_LARGE')
    return hashlib.sha256(raw).hexdigest()


# Only fields consumed by the canonical writer/derived preparation are retained.
_OUTPUT_FIELDS = frozenset({
    'ot','source_pk','source_updated_at','source_timezone','is_deleted','properties',
    'external_id','status_raw','schema_version','link_type','source_type','target_type',
    'target_source_pk','source_external_id','target_external_id','cursor_external_id',
    'pay_time','_order_create_time','delivery_time',
})


def canonical_output_rows(command, rows):
    """Detach fixed calculation input and prove its base records match the batch."""
    from aos_api.ec_ot_writer import _normalize_rows
    if type(rows) is not list or any(type(row) is not dict for row in rows):
        raise ValueError('INGRESS_OUTPUT_INVALID')
    def encode(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal) and value.is_finite():
            return str(value)
        raise TypeError('INGRESS_OUTPUT_VALUE_INVALID')
    selected = [{key:value for key,value in row.items() if key in _OUTPUT_FIELDS} for row in rows]
    normalized = json.loads(json.dumps(selected,default=encode,allow_nan=False,ensure_ascii=False))
    objects,links = _normalize_rows(normalized,command.scope)
    if ([item.model_dump(mode='json') for item in objects] != [item.model_dump(mode='json') for item in command.objects]
        or [item.model_dump(mode='json') for item in links] != [item.model_dump(mode='json') for item in command.links]):
        raise IngressJournalConflict('INGRESS_OUTPUT_BASE_DRIFT')
    return normalized


def _validate(scope, envelope):
    required = {'runId','pipelineId','sourceId','sourceRevision','pipelineHash','command'}
    empty = envelope.get('kind') == 'empty_observation_v1'
    allowed = (required | {'kind','outputRows'},) if empty else (required, required | {'outputRows'})
    if type(scope) is not TenantScope or set(envelope) not in allowed:
        raise ValueError('INGRESS_ENVELOPE_INVALID')
    for key in ('runId', 'pipelineId', 'sourceId'):
        value = envelope[key]
        if type(value) is not str or not 1 <= len(value) <= 200 or value.strip() != value or '\x00' in value:
            raise ValueError('INGRESS_ID_INVALID')
    if str(UUID(envelope['sourceRevision'])) != envelope['sourceRevision']:
        raise ValueError('INGRESS_SOURCE_REVISION_INVALID')
    if type(envelope['pipelineHash']) is not str or re.fullmatch('[0-9a-f]{64}', envelope['pipelineHash']) is None:
        raise ValueError('INGRESS_PIPELINE_HASH_INVALID')
    if empty:
        if envelope['command'] is not None or envelope['outputRows'] != []:
            raise ValueError('INGRESS_EMPTY_OBSERVATION_INVALID')
        return _digest(envelope)
    command = BatchCommand.model_validate(envelope['command'])
    if (command.scope.org_id, command.scope.workspace_id) != scope.key or command.scope.stream != envelope['pipelineId']:
        raise ValueError('INGRESS_SCOPE_MISMATCH')
    if command.model_dump(mode='json') != envelope['command']:
        raise ValueError('INGRESS_COMMAND_NOT_CANONICAL')
    if 'outputRows' in envelope and canonical_output_rows(command,envelope['outputRows']) != envelope['outputRows']:
        raise IngressJournalConflict('INGRESS_OUTPUT_NOT_CANONICAL')
    return _digest(envelope)


class IngressJournal:
    def __init__(self, *, storage_schema='public'):
        self.schema = storage_schema
        self.table = sql.Identifier(storage_schema, 'ecommerce_ingress_command')

    def lock_run(self, conn, scope, run_id):
        """Serialize preparation/submission of one immutable run in this transaction."""
        material = json.dumps([*scope.key,run_id],ensure_ascii=False,separators=(',',':')).encode()
        key = int.from_bytes(hashlib.sha256(material).digest()[:8],'big',signed=True)
        conn.execute('SELECT pg_advisory_xact_lock(%s)',(key,))

    def read(self, conn, scope, run_id):
        row = conn.execute(sql.SQL('SELECT * FROM {} WHERE org_id=%s AND project_id=%s AND run_id=%s').format(self.table), (*scope.key, run_id)).fetchone()
        if row is None:
            return None
        envelope = row['envelope']
        if (_validate(scope, envelope) != row['envelope_hash'] or envelope['runId'] != row['run_id']
            or envelope['pipelineId'] != row['pipeline_id'] or envelope['sourceId'] != row['source_id']
            or envelope['sourceRevision'] != str(row['source_revision'])):
            raise IngressJournalConflict('INGRESS_COMMAND_DRIFT')
        return envelope

    def save(self, conn, scope, *, run_id, pipeline_id, source_id, source_revision, pipeline_hash, command, output_rows=None):
        payload = BatchCommand.model_validate(command.model_dump(mode='python')).model_dump(mode='json')
        envelope = dict(runId=run_id,pipelineId=pipeline_id,sourceId=source_id,sourceRevision=source_revision,pipelineHash=pipeline_hash,command=payload)
        if output_rows is not None:
            envelope['outputRows'] = canonical_output_rows(BatchCommand.model_validate(payload),output_rows)
        return self._save_envelope(conn,scope,envelope)

    def save_empty_for_running_schedule(self, conn, scope, **args):
        self.verify_running_schedule(conn,scope,**args)
        envelope = dict(runId=args['run_id'],pipelineId=args['pipeline_id'],sourceId=args['source_id'],
                        sourceRevision=args['source_revision'],pipelineHash=args['pipeline_hash'],
                        kind='empty_observation_v1',command=None,outputRows=[])
        return self._save_envelope(conn,scope,envelope)

    def _save_envelope(self, conn, scope, envelope):
        digest = _validate(scope, envelope)
        run_id,pipeline_id,source_id,source_revision = (envelope[k] for k in ('runId','pipelineId','sourceId','sourceRevision'))
        conn.execute(sql.SQL('''INSERT INTO {} (org_id,project_id,run_id,pipeline_id,source_id,source_revision,envelope_hash,envelope)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(org_id,project_id,run_id) DO NOTHING''').format(self.table),
            (*scope.key,run_id,pipeline_id,source_id,source_revision,digest,json.dumps(envelope,ensure_ascii=False,allow_nan=False)))
        saved = self.read(conn, scope, run_id)
        if saved is None or _digest(saved) != digest:
            raise IngressJournalConflict('INGRESS_COMMAND_CONFLICT')
        return saved


    def save_for_running_schedule(self, conn, scope, **args):
        self.verify_running_schedule(conn, scope, **args)
        return self.save(conn, scope, **args)

    def verify_running_schedule(self, conn, scope, **args):
        """Lock and validate current binding; caller retains the transaction."""
        def read(table, identity_column, identity, columns):
            return conn.execute(sql.SQL('SELECT {} FROM {} WHERE org_id=%s AND project_id=%s AND {}=%s FOR SHARE').format(
                sql.SQL(columns), sql.Identifier(self.schema, table), sql.Identifier(identity_column)),
                (*scope.key, identity)).fetchone()
        run = read('meta_schedule_run', 'id', args['run_id'], 'schedule_id,status')
        if run is None or run['status'] != 'running':
            raise IngressJournalConflict('INGRESS_RUNNING_SCHEDULE_REQUIRED')
        schedule = read('meta_schedule', 'id', run['schedule_id'], 'pipeline_id,enabled,ingest')
        if (schedule is None or schedule['enabled'] is not True or schedule['pipeline_id'] != args['pipeline_id']
            or type(schedule['ingest']) is not dict or schedule['ingest'].get('kind') != 'pipeline-live-v1'
            or schedule['ingest'].get('pipelineId') != args['pipeline_id']):
            raise IngressJournalConflict('INGRESS_SCHEDULE_BINDING_DRIFT')
        self.verify_pipeline_source_binding(conn, scope,
            pipeline_id=args['pipeline_id'], source_id=args['source_id'],
            source_revision=args['source_revision'], pipeline_hash=args['pipeline_hash'],
            graph_revision=args.get('graph_revision'))

    def verify_pipeline_source_binding(self, conn, scope, *, pipeline_id, source_id,
                                      source_revision, pipeline_hash, graph_revision=None):
        """Check current graph/source only; this grants no execution permission.

        The caller retains the transaction and must check installation, current
        authorization and budgets separately. No ScheduleRun is manufactured.
        """
        if type(scope) is not TenantScope:
            raise TypeError('exact pipeline tenant scope required')
        if graph_revision is not None and (type(graph_revision) is not int or not 1 <= graph_revision < 2**63):
            raise ValueError('positive graph revision required')
        args = dict(pipeline_id=pipeline_id, source_id=source_id,
                    source_revision=source_revision, pipeline_hash=pipeline_hash)
        def read(table, identity_column, identity, columns):
            return conn.execute(sql.SQL('SELECT {} FROM {} WHERE org_id=%s AND project_id=%s AND {}=%s FOR SHARE').format(
                sql.SQL(columns), sql.Identifier(self.schema, table), sql.Identifier(identity_column)),
                (*scope.key, identity)).fetchone()
        graph = read('phase5_pipeline_graph', 'pipeline_id', args['pipeline_id'],
                     'payload,revision' if graph_revision is not None else 'payload')
        if graph is None or type(graph['payload']) is not dict or _digest(graph['payload']) != args['pipeline_hash']:
            raise IngressJournalConflict('INGRESS_GRAPH_DRIFT')
        if graph_revision is not None and graph.get('revision') != graph_revision:
            raise IngressJournalConflict('INGRESS_GRAPH_REVISION_DRIFT')
        payload = graph['payload']
        nodes = payload.get('nodes')
        if payload.get('pipeline_id') != args['pipeline_id'] or type(nodes) is not list or any(type(n) is not dict for n in nodes):
            raise IngressJournalConflict('INGRESS_GRAPH_INVALID')
        sources = [n for n in nodes if str(n.get('node_type', '')).lower() == 'source']
        if (len(sources) != 1 or type(sources[0].get('config')) is not dict
            or sources[0]['config'].get('source_id') != args['source_id']):
            raise IngressJournalConflict('INGRESS_SOURCE_BINDING_DRIFT')
        source = read('meta_source', 'id', args['source_id'], 'type,status,configuration_revision')
        if (source is None or source['type'] != 'jdbc-mysql-ssh' or source['status'] not in {'registered','active','ready'}
            or str(source['configuration_revision']) != args['source_revision']):
            raise IngressJournalConflict('INGRESS_SOURCE_CONFIGURATION_DRIFT')

    def _derived_payload(self, parent, commands):
        from aos_api.ecom_core_models import DerivedMetricCommand
        if parent.get('kind') == 'empty_observation_v1':
            if commands:
                raise IngressJournalConflict('INGRESS_EMPTY_DERIVED_INVALID')
            return {'parentHash':_digest(parent),'commands':[]}
        base = BatchCommand.model_validate(parent['command'])
        allowed = {(obj.object_type, obj.identity.scoped_key()) for obj in base.objects if not obj.is_deleted}
        seen = set()
        normalized = []
        for raw in commands:
            command = DerivedMetricCommand.model_validate(raw)
            identity = (command.object_type, command.identity.scoped_key())
            if identity not in allowed or identity in seen or command.stream != parent['pipelineId']:
                raise IngressJournalConflict('INGRESS_DERIVED_IDENTITY_DRIFT')
            seen.add(identity)
            normalized.append(command.model_dump(mode='json'))
        return {'parentHash': _digest(parent), 'commands': normalized}

    def read_derived(self, conn, scope, run_id):
        table = sql.Identifier(self.schema, 'ecommerce_ingress_derived_command')
        row = conn.execute(sql.SQL('SELECT payload,payload_hash FROM {} WHERE org_id=%s AND project_id=%s AND run_id=%s').format(table),(*scope.key,run_id)).fetchone()
        if row is None:
            return None
        parent = self.read(conn,scope,run_id)
        payload = row['payload']
        if (parent is None or type(payload) is not dict or set(payload) != {'parentHash','commands'}
            or type(payload['commands']) is not list or self._derived_payload(parent,payload['commands']) != payload
            or _digest(payload) != row['payload_hash']):
            raise IngressJournalConflict('INGRESS_DERIVED_PAYLOAD_DRIFT')
        return payload

    def save_derived(self, conn, scope, run_id, commands):
        parent = self.read(conn,scope,run_id)
        if parent is None:
            raise IngressJournalConflict('INGRESS_PARENT_REQUIRED')
        payload = self._derived_payload(parent,[c.model_dump(mode='json') for c in commands])
        digest = _digest(payload)
        table = sql.Identifier(self.schema, 'ecommerce_ingress_derived_command')
        conn.execute(sql.SQL('''INSERT INTO {} (org_id,project_id,run_id,payload_hash,payload)
            VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(org_id,project_id,run_id) DO NOTHING''').format(table),
            (*scope.key,run_id,digest,json.dumps(payload,ensure_ascii=False,allow_nan=False)))
        saved = self.read_derived(conn,scope,run_id)
        if saved is None or _digest(saved) != digest:
            raise IngressJournalConflict('INGRESS_DERIVED_CONFLICT')
        return saved
