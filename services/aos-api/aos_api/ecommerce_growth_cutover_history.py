"""Validated historical phase view, with no execution or continuation authority."""
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverConflict


def _dump(receipt):
    return receipt.model_dump(mode='json', by_alias=True)


def _ref(receipt, kind):
    return dict(resourceType=kind, resourceId=str(receipt.receipt_id), revision=1, contentHash=receipt.content_hash)


def _require(condition):
    if not condition:
        raise EcommerceGrowthCutoverConflict('cutover history linkage or completeness drifted')


def _complete(store, conn, scope, operation_id, receipts, ordered):
    rows=conn.execute(f'''SELECT phase,count(*) AS n FROM {store._schema}.extension_dispatch_cutover_receipt
        WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s GROUP BY phase''',
        (*scope.key,operation_id)).fetchall()
    _require({r['phase']:r['n'] for r in rows} == {p:1 for p in receipts})
    _require(list(receipts)==list(ordered[:len(receipts)]))


def activation_history(store, conn, scope, row, prepare):
    operation_id=prepare.cutover_operation_id
    event=conn.execute(f'''SELECT payload,payload_hash,occurred_at
        FROM {store._schema}.extension_dispatch_cutover_event
        WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s
          AND sequence=1 AND event_type='CUTOVER_PREPARED' ''',(*scope.key,operation_id)).fetchone()
    expected=dict(cutoverOperationId=str(operation_id),cutoverGroupId=str(prepare.cutover_group_id),
        expectedGroupRevision=row['expected_group_revision'],targetGroupRevision=row['target_group_revision'],
        receiptId=str(prepare.receipt_id),contentHash=prepare.content_hash)
    _require(event is not None and event['payload']==expected
        and event['payload_hash']==canonical_sha256(expected) and event['occurred_at']==prepare.created_at)
    receipts={'prepare':_dump(prepare)}
    commit=None
    for phase in ('pause','commit'):
        value=store._load_phase_receipt(conn,scope,operation_id,phase)
        if value is not None:
            receipt=store._phase_receipt(scope,value,replayed=True)
            _require(_dump(receipt.prepare_receipt_ref)==_ref(prepare,'CutoverPrepareReceipt'))
            receipts[phase]=_dump(receipt)
            if phase=='commit':commit=receipt
    for phase in ('validate','resume'):
        value=store._load_finalize_receipt(conn,scope,operation_id,phase)
        if value is not None:
            receipt=store._finalize_receipt(scope,value,replayed=True)
            _require(commit is not None and _dump(receipt.commit_receipt_ref)==_ref(commit,'CutoverCommitReceipt'))
            receipts[phase]=_dump(receipt)
    _complete(store,conn,scope,operation_id,receipts,('prepare','pause','commit','validate','resume'))
    children=conn.execute(f'''SELECT cutover_operation_id,target_installation_id,cutover_group_id,status
        FROM {store._schema}.extension_dispatch_cutover_operation
        WHERE org_id=%s AND project_id=%s AND parent_cutover_operation_id=%s AND kind='rollback'
        ORDER BY created_at,cutover_operation_id''',(*scope.key,operation_id)).fetchall()
    _require(len(children)<=1)
    rollbacks=[]
    for child in children:
        _require(commit is not None and child['target_installation_id']==row['target_installation_id']
            and child['cutover_group_id']==row['cutover_group_id'])
        phases={}
        for phase in ('fence','drain','rollback'):
            value=store._load_rollback_receipt(conn,scope,child['cutover_operation_id'],phase)
            if value is not None:
                receipt=store._rollback_receipt(scope,value,replayed=True)
                _require(_dump(receipt.commit_receipt_ref)==_ref(commit,'CutoverCommitReceipt'))
                phases[phase]=_dump(receipt)
        _require(bool(phases))
        _complete(store,conn,scope,child['cutover_operation_id'],phases,('fence','drain','rollback'))
        rollbacks.append(dict(operationId=str(child['cutover_operation_id']),observedStatus=child['status'],receipts=phases))
    return dict(schemaVersion='aos.ecommerce.cutover-history/v1',historical=True,executable=False,
        observedStatus=row['status'],activationReceipts=receipts,rollbacks=rollbacks)
