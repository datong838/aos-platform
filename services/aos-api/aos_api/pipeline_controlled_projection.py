"""Project only a current controlled run's reconciled original events, in order."""
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _bound_parent, _check_active
from aos_api.ecom_consistency_store import EcomConsistencyStore, ProjectionEventEvidence
from aos_api.ecom_core_models import BatchCommand, DerivedMetricCommand
from aos_api.ecom_projector import projection_order_lock_key, _verify_payload, _project_object, _project_link, PROJECTOR_ACTOR
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.tenant_scope import TenantScope


def project_saved_batch(conn,scope,run_id,*,journal,store,deadline=None,cancel_event=None):
    """Caller commits. Never consume caller-supplied event keys or another run."""
    _require_transaction(conn)
    if type(scope) is not TenantScope or type(journal) is not ControlledIngressJournal or type(store) is not EcomConsistencyStore:
        raise TypeError('exact controlled journal, tenant and consistency Owner required')
    _check_active(deadline,cancel_event)
    journal.lock_run(conn,scope,run_id)
    parent=_bound_parent(conn,scope,run_id,journal)
    saved=journal.read_derived(conn,scope,run_id)
    if saved is None:raise IngressJournalConflict('INGRESS_DERIVED_PREPARATION_REQUIRED')
    if parent.get('kind')=='empty_observation_v1':
        if saved['commands']:raise IngressJournalConflict('INGRESS_EMPTY_DERIVED_DRIFT')
        return {'projected':0,'pending':0}
    command=BatchCommand.model_validate(parent['command'])
    if (command.scope.org_id,command.scope.workspace_id)!=scope.key:
        raise IngressJournalConflict('INGRESS_SCOPE_MISMATCH')
    derived=[DerivedMetricCommand.model_validate(item) for item in saved['commands']]
    result=_project_exact_command(conn,scope,command,derived,store=store,
        deadline=deadline,cancel_event=cancel_event)
    _bound_parent(conn,scope,run_id,journal)
    return result


def _project_exact_command(conn,scope,command,derived,*,store,deadline=None,cancel_event=None,max_events=5000):
    """Internal shared projection primitive; caller must hold original current guards."""
    _require_transaction(conn)
    if type(scope) is not TenantScope or type(store) is not EcomConsistencyStore or type(command) is not BatchCommand:
        raise TypeError('exact original tenant, Store and command required')
    if (command.scope.org_id,command.scope.workspace_id)!=scope.key:
        raise IngressJournalConflict('INGRESS_SCOPE_MISMATCH')
    if type(max_events) is not int or not 1<=max_events<=24000:
        raise ValueError('bounded exact projection required')
    _check_active(deadline,cancel_event)
    # Share the existing projector's tenant lock; never overtake its writes.
    lock_key=projection_order_lock_key(scope)
    if conn.execute('SELECT pg_try_advisory_xact_lock(%s) AS acquired',(lock_key,)).fetchone()['acquired'] is not True:
        raise IngressJournalConflict('PROJECTION_BUSY')
    evidence=store.read_batch_projection_evidence(command,derived)
    if (type(evidence) is not tuple or not 1<=len(evidence)<=max_events
        or any(type(item) is not ProjectionEventEvidence for item in evidence)):
        raise IngressJournalConflict('PROJECTION_EVIDENCE_INVALID')
    expected={item.event_key:item for item in evidence}
    if len(expected)!=len(evidence):raise IngressJournalConflict('PROJECTION_EVIDENCE_AMBIGUOUS')
    keys=list(expected)
    rows=conn.execute('''SELECT * FROM projection_outbox WHERE org_id=%s AND project_id=%s
        AND event_source='authoritative_store' AND event_key=ANY(%s)
        ORDER BY input_revision,outbox_id FOR UPDATE''',(*scope.key,keys)).fetchall()
    if len(rows)!=len(expected):raise IngressJournalConflict('PROJECTION_EVENT_SET_DRIFT')
    checked=[]
    for row in rows:
        item=expected.get(row['event_key'])
        if item is None or (row['payload_hash'],row['input_revision'])!=(item.payload_hash,item.input_revision):
            raise IngressJournalConflict('PROJECTION_EVENT_EVIDENCE_DRIFT')
        checked.append((row,_verify_payload(row)))
    pending=[item for item in checked if item[0]['projected'] is not True]
    if pending:
        last=pending[-1][0]
        earlier=conn.execute('''SELECT outbox_id FROM projection_outbox
            WHERE org_id=%s AND project_id=%s AND event_source='authoritative_store' AND projected=FALSE
            AND NOT(event_key=ANY(%s)) AND (input_revision,outbox_id)<(%s,%s) LIMIT 1''',
            (*scope.key,keys,last['input_revision'],last['outbox_id'])).fetchone()
        if earlier is not None:raise IngressJournalConflict('PROJECTION_ORDER_BLOCKED')
        conn.execute("SELECT set_config('aos.projection_actor',%s,true)",(PROJECTOR_ACTOR,))
    for row,payload in pending:
        _check_active(deadline,cancel_event)
        if payload.get('entityKind')=='object':_project_object(conn,scope,payload)
        elif payload.get('entityKind')=='link':_project_link(conn,scope,payload)
        else:raise IngressJournalConflict('PROJECTION_ENTITY_KIND_UNSUPPORTED')
        result=conn.execute('''UPDATE projection_outbox SET projected=TRUE,projected_at=clock_timestamp(),projection_error=NULL
            WHERE org_id=%s AND project_id=%s AND outbox_id=%s AND event_key=%s AND payload_hash=%s''',
            (*scope.key,row['outbox_id'],row['event_key'],row['payload_hash']))
        if result.rowcount!=1:raise IngressJournalConflict('PROJECTION_EVENT_UPDATE_DRIFT')
    _check_active(deadline,cancel_event)
    return {'projected':len(pending),'pending':0}
