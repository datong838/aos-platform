"""AIP-owned exact configuration reference adapters, not spending authority.

The extension kernel may receive this reader from its trusted composition root;
it must not import AIP or copy the canonical budget ledger.
"""
from aos_api.aip_budget_contracts import BudgetRevision, BudgetRevisionCreate, BudgetLifecycle
from aos_api.aip_budget_store import canonical_hash
from aos_api.extension_runtime.configuration_contracts import ConfigurationSourceRef
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values, _digest, RuntimeConflict


_BUDGET_FIELDS=tuple(name for name in BudgetRevision.model_fields if name!='tenant')
_COLUMNS=('org_id','project_id',*_BUDGET_FIELDS,'payload')


def read_current_budget_ref(conn, *, org_id, project_id, ref):
    """Current immutable BudgetRevision; no hold, balance check, or permission grant."""
    _require_transaction(conn)
    ref=ConfigurationSourceRef.model_validate(ref)
    if ref.authority!='aip.budget_revision':raise ValueError('exact budget authority required')
    scope=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id, "
                       "current_setting('aos.project_id',true) AS project_id").fetchone()
    if not org_id or not project_id or _values(scope,('role','org_id','project_id'))!=('aos_runtime',org_id,project_id):
        raise PermissionError('runtime budget scope or role differs')
    target=(org_id,project_id,ref.id)
    head=conn.execute('''SELECT current_revision FROM aip_budget_head
        WHERE org_id=%s AND project_id=%s AND budget_id=%s FOR SHARE''',target).fetchone()
    if head is None:raise LookupError('current budget unavailable')
    if _values(head,('current_revision',))[0]!=ref.revision:
        raise RuntimeConflict('budget reference is no longer current')
    row=conn.execute(f'''SELECT {','.join(_COLUMNS)} FROM aip_budget_revision
        WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s''',(*target,ref.revision)).fetchone()
    if row is None:raise LookupError('budget revision unavailable')
    data=dict(zip(_COLUMNS,_values(row,_COLUMNS)))
    record=BudgetRevision.model_validate(data['payload'])
    if _digest(data['payload'])!=_digest(record.model_dump(mode='json',by_alias=True)):
        raise RuntimeConflict('budget payload is not canonical')
    if (record.tenant.org_id,record.tenant.project_id,record.budget_id,record.revision)!=(org_id,project_id,ref.id,ref.revision):
        raise RuntimeConflict('budget identity differs')
    if any(data[name]!=getattr(record,name) for name in _BUDGET_FIELDS):
        raise RuntimeConflict('budget columns differ from canonical payload')
    content=BudgetRevisionCreate.model_validate({name:getattr(record,name) for name in BudgetRevisionCreate.model_fields})
    if record.content_hash!=canonical_hash(content.model_dump(mode='json',by_alias=True)) or ref.hash!='sha256:'+record.content_hash:
        raise RuntimeConflict('budget content hash differs')
    now=_values(conn.execute('SELECT clock_timestamp() AS now').fetchone(),('now',))[0]
    if (record.lifecycle!=BudgetLifecycle.ACTIVE or record.environment!='development' or record.currency!='CNY'
            or record.hard_stop is not True or record.unknown_usage_behavior!='block'
            or not record.effective_from<=now<record.effective_until):
        raise RuntimeConflict('budget is not currently effective')
    return record
