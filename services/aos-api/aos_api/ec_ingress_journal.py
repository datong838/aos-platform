"""Original canonical command storage; never grants execution authority."""
import hashlib
import json
import re
from uuid import UUID
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


def _validate(scope, envelope):
    if type(scope) is not TenantScope or set(envelope) != {'runId','pipelineId','sourceId','sourceRevision','pipelineHash','command'}:
        raise ValueError('INGRESS_ENVELOPE_INVALID')
    for key in ('runId', 'pipelineId', 'sourceId'):
        value = envelope[key]
        if type(value) is not str or not 1 <= len(value) <= 200 or value.strip() != value or '\x00' in value:
            raise ValueError('INGRESS_ID_INVALID')
    if str(UUID(envelope['sourceRevision'])) != envelope['sourceRevision']:
        raise ValueError('INGRESS_SOURCE_REVISION_INVALID')
    if type(envelope['pipelineHash']) is not str or re.fullmatch('[0-9a-f]{64}', envelope['pipelineHash']) is None:
        raise ValueError('INGRESS_PIPELINE_HASH_INVALID')
    command = BatchCommand.model_validate(envelope['command'])
    if (command.scope.org_id, command.scope.workspace_id) != scope.key or command.scope.stream != envelope['pipelineId']:
        raise ValueError('INGRESS_SCOPE_MISMATCH')
    if command.model_dump(mode='json') != envelope['command']:
        raise ValueError('INGRESS_COMMAND_NOT_CANONICAL')
    return _digest(envelope)


class IngressJournal:
    def __init__(self, *, storage_schema='public'):
        self.schema = storage_schema
        self.table = sql.Identifier(storage_schema, 'ecommerce_ingress_command')

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

    def save(self, conn, scope, *, run_id, pipeline_id, source_id, source_revision, pipeline_hash, command):
        payload = BatchCommand.model_validate(command.model_dump(mode='python')).model_dump(mode='json')
        envelope = dict(runId=run_id,pipelineId=pipeline_id,sourceId=source_id,sourceRevision=source_revision,pipelineHash=pipeline_hash,command=payload)
        digest = _validate(scope, envelope)
        conn.execute(sql.SQL('''INSERT INTO {} (org_id,project_id,run_id,pipeline_id,source_id,source_revision,envelope_hash,envelope)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(org_id,project_id,run_id) DO NOTHING''').format(self.table),
            (*scope.key,run_id,pipeline_id,source_id,source_revision,digest,json.dumps(envelope,ensure_ascii=False,allow_nan=False)))
        saved = self.read(conn, scope, run_id)
        if saved is None or _digest(saved) != digest:
            raise IngressJournalConflict('INGRESS_COMMAND_CONFLICT')
        return saved


    def save_for_running_schedule(self, conn, scope, **args):
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
        graph = read('phase5_pipeline_graph', 'pipeline_id', args['pipeline_id'], 'payload')
        if graph is None or type(graph['payload']) is not dict or _digest(graph['payload']) != args['pipeline_hash']:
            raise IngressJournalConflict('INGRESS_GRAPH_DRIFT')
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
        return self.save(conn, scope, **args)
