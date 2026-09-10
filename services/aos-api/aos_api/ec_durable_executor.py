"""Scheduled ingress: save original input, then recover only that saved batch."""
from psycopg import sql
from aos_api.db import connect
from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict, _digest
from aos_api.ec_ingress_recovery import _bound_parent, _check_active, recover_saved_authoritative_stages
from aos_api.ec_ingress_dataset import finalize_saved_dataset
from aos_api.ec_source_adapter import fetch_source_rows_versioned
from aos_api.ec_ot_writer import _normalize_rows, _build_sync_scope, _build_batch_command
from aos_api.ecom_projector import project_until_caught_up
from aos_api.ecommerce_growth_host_ports import HostTransaction


def _node_execution(node):
    def field(key):
        return node.get(key) if isinstance(node,dict) else getattr(node,key,None)
    return {key:field(key) for key in ('id','pipeline_id','node_type','config')}


def execute_durable_ingress(*,eng,pipeline,nodes,scope,run_id,run_started_at,deadline,cancel_event):
    from aos_api.ec_live_executor import _transform_live_rows
    journal = IngressJournal()
    rows_read = 0
    _check_active(deadline,cancel_event)
    with connect(scope) as conn:
        journal.lock_run(conn,scope,run_id)
        parent = journal.read(conn,scope,run_id)
        if parent is not None:
            if parent['pipelineId'] != pipeline.id:
                raise IngressJournalConflict('INGRESS_PIPELINE_BINDING_DRIFT')
            _bound_parent(conn,scope,run_id,journal)
        else:
            graph = conn.execute(sql.SQL('SELECT payload FROM {} WHERE org_id=%s AND project_id=%s AND pipeline_id=%s FOR SHARE').format(
                sql.Identifier(journal.schema,'phase5_pipeline_graph')),(*scope.key,pipeline.id)).fetchone()
            if (graph is None or type(graph['payload']) is not dict
                or graph['payload'].get('write_mode') != pipeline.write_mode
                or [_node_execution(node) for node in graph['payload'].get('nodes',[])] != [_node_execution(node) for node in nodes]):
                raise IngressJournalConflict('INGRESS_EXECUTION_GRAPH_DRIFT')
            sources = [node for node in nodes if node.node_type == 'source']
            if len(sources) != 1 or not sources[0].config.get('source_id'):
                raise IngressJournalConflict('INGRESS_SOURCE_BINDING_DRIFT')
            source_id = sources[0].config['source_id']
            source = conn.execute(sql.SQL('SELECT configuration_revision FROM {} WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE').format(
                sql.Identifier(journal.schema,'meta_source')),(*scope.key,source_id)).fetchone()
            if source is None:
                raise IngressJournalConflict('INGRESS_SOURCE_CONFIGURATION_DRIFT')
            args = dict(run_id=run_id,pipeline_id=pipeline.id,source_id=source_id,
                        source_revision=str(source['configuration_revision']),pipeline_hash=_digest(graph['payload']))
            journal.verify_running_schedule(conn,scope,**args)
            _check_active(deadline,cancel_event)
            rows,ref = fetch_source_rows_versioned(pipeline=pipeline,nodes=nodes,node_id=None,scope=scope,transaction=HostTransaction(conn))
            if ref.resource_id != 'source-config-'+args['source_revision']:
                raise IngressJournalConflict('INGRESS_SOURCE_READ_VERSION_DRIFT')
            _check_active(deadline,cancel_event)
            rows_read = len(rows)
            output = _transform_live_rows(eng=eng,pipeline=pipeline,nodes=nodes,node_id=None,scope=scope,
                                         input_rows=rows,run_started_at=run_started_at)
            _check_active(deadline,cancel_event)
            if not output:
                raise IngressJournalConflict('INGRESS_EMPTY_BATCH_UNSUPPORTED')
            sync = _build_sync_scope(scope,pipeline)
            objects,links = _normalize_rows(output,sync)
            command = _build_batch_command(sync_scope=sync,objects=objects,links=links,pipeline_id=pipeline.id,store=eng.ecom_consistency_store)
            parent = journal.save_for_running_schedule(conn,scope,**args,command=command,output_rows=output)
    _check_active(deadline,cancel_event)
    derived = recover_saved_authoritative_stages(connect,scope,run_id,journal=journal,store=eng.ecom_consistency_store,
                                                deadline=deadline,cancel_event=cancel_event)
    projection = project_until_caught_up(scope,deadline=deadline,cancel_event=cancel_event)
    _check_active(deadline,cancel_event)
    result = finalize_saved_dataset(connect,scope,run_id,journal=journal,store=eng.ecom_consistency_store,eng=eng)
    return dict(input_ref='',output_ref='dataset://catalog/'+result['dataset']['rid'],lineage_ref='',quality_ref='',
                rows_read=rows_read,rows_written=result['build']['rows_written'],output_rows=parent.get('outputRows',[]),
                projection=projection,derived={'derived_updated':sum(int(item.updated and not item.replayed) for item in derived),
                                              'derived_replayed':sum(int(item.replayed) for item in derived)})
