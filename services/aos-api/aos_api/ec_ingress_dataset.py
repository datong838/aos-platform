"""Commit Dataset metadata and its immutable run result before cache publication."""
import hashlib
import json
from types import SimpleNamespace
from psycopg import sql
from aos_api import data_os_store
from aos_api.ec_dataset_sink import _resolve_stable_rid, _resolve_dataset_name, _resolve_ot_hint
from aos_api.ec_ingress_journal import IngressJournalConflict, _digest
from aos_api.ec_ingress_recovery import _bound_parent, read_saved_projection_completion


def finalize_saved_dataset(connection_factory, scope, run_id, *, journal, store, eng):
    """Internal running-run finalizer; factory commits before publishing memory."""
    table = sql.Identifier(journal.schema,'ecommerce_ingress_dataset_receipt')
    with connection_factory(scope) as conn:
        with conn.transaction():
            journal.lock_run(conn,scope,run_id)
            parent = _bound_parent(conn,scope,run_id,journal)
            derived = journal.read_derived(conn,scope,run_id)
            if derived is None:
                raise IngressJournalConflict('INGRESS_DERIVED_COMMAND_REQUIRED')
            row = conn.execute(sql.SQL('SELECT payload,payload_hash FROM {} WHERE org_id=%s AND project_id=%s AND run_id=%s').format(table),(*scope.key,run_id)).fetchone()
            if row is not None:
                result = row['payload']
                if (_digest(result) != row['payload_hash'] or result.get('parentHash') != _digest(parent)
                    or result.get('derivedHash') != _digest(derived)):
                    raise IngressJournalConflict('INGRESS_DATASET_RECEIPT_DRIFT')
            else:
                # A committed receipt proves historical completion; only a new
                # result must reconcile the current authoritative records.
                completion = read_saved_projection_completion(conn,scope,run_id,journal=journal,store=store)
                if completion['pending'] != 0:
                    raise IngressJournalConflict('INGRESS_PROJECTION_PENDING')
                pipeline = SimpleNamespace(id=parent['pipelineId'])
                dataset_lock = int.from_bytes(hashlib.sha256(json.dumps(['dataset',*scope.key,_resolve_stable_rid(pipeline)]).encode()).digest()[:8],'big',signed=True)
                conn.execute('SELECT pg_advisory_xact_lock(%s)',(dataset_lock,))
                at = float(conn.execute('SELECT extract(epoch from clock_timestamp()) AS at').fetchone()['at'])
                count = len(parent.get('outputRows',[])) if 'outputRows' in parent else len(parent['command']['objects'])+len(parent['command']['links'])
                item = dict(rid=_resolve_stable_rid(pipeline),name=_resolve_dataset_name(pipeline),
                            displayName=_resolve_dataset_name(pipeline),pipelineId=pipeline.id,
                            sourceId=parent['sourceId'],status='READY',objectTypeHint=_resolve_ot_hint(pipeline),
                            createdAt=at,updatedAt=at)
                build_id = 'db-ingress-'+hashlib.sha256(json.dumps([*scope.key,run_id],separators=(',',':')).encode()).hexdigest()[:32]
                build = dict(id=build_id,status='success',rows_written=count,started_at=at,finished_at=at)
                result = dict(parentHash=_digest(parent),derivedHash=_digest(derived),dataset=item,build=build,completion=completion)
                data_os_store._persist_dataset_in_transaction(conn,scope,item,
                    history_entries=[dict(version=1,status='SUCCEEDED',at=at,rowsWritten=count,runId=run_id,buildId=build_id)])
                conn.execute(sql.SQL('INSERT INTO {}(org_id,project_id,run_id,payload_hash,payload) VALUES(%s,%s,%s,%s,%s::jsonb)').format(table),
                    (*scope.key,run_id,_digest(result),json.dumps(result,ensure_ascii=False,allow_nan=False)))
    # Replaying an old run must not replace newer cached Dataset metadata.
    item = result['dataset']
    current = eng.get_dataset(scope,item['rid'])
    if current is None or current.updated_at <= item['updatedAt']:
        eng.create_dataset(scope,id=item['rid'],name=item['name'],created_at=item['createdAt'],
                           updated_at=item['updatedAt'],row_count=result['build']['rows_written'])
    eng.add_build(scope,item['rid'],**result['build'])
    return result
