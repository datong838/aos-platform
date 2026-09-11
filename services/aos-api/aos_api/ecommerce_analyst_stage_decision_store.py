"""Transaction-bound stage decision persistence; human/source checks are upstream."""
from aos_api.ecommerce_analyst_stage_decision import AnalystStageDecisionRevision
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore,canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

_FIELDS=('task_run_id','plan_ref','stage','stage_attempt_ref','subject_ref','artifact_ref','eval_report_ref')
_OPERATION='analyst.stage_decision_publish'


def stage_decision_id(item):
    body=item.model_dump(mode='json',by_alias=False)
    return 'stage-review-'+canonical_hash(dict(tenant=body['tenant'],**{key:body[key] for key in _FIELDS}))


class AnalystStageDecisionStore:
    def __init__(self,transaction,scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('stage decision requires HostTransaction and TenantScope')
        self.tx,self.scope=transaction,scope
        self.owner=EcommerceAnalystAuthorityStore(TransactionBoundConnectFactory(transaction,scope))

    def put(self,item,*,actor,key,expected_version):
        item=AnalystStageDecisionRevision.model_validate(item.model_dump())
        if (type(actor) is not str or actor!=item.created_by or type(key) is not str or not key or key.strip()!=key or len(key)>200
            or type(expected_version) is not int or expected_version<0 or (item.tenant.org_id,item.tenant.project_id)!=self.scope.key
            or item.decision_id!=stage_decision_id(item)
            or canonical_hash(item.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=item.content_hash):
            raise ValueError('stage decision publication identity drifted')
        for lock in sorted({canonical_hash([*self.scope.key,'stage-target',item.decision_id]),canonical_hash([*self.scope.key,'stage-key',key])}):
            self.tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(lock,))
        now=self.tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if item.created_at>now:raise ValueError('stage decision creation is in the future')
        if item.prior_ref is None:
            if item.decision=='revoke':raise ValueError('cannot revoke an absent stage decision')
        else:
            prior=self.read_exact(item.prior_ref)
            if any(getattr(prior,key)!=getattr(item,key) for key in _FIELDS) or prior.created_at>item.created_at:
                raise ValueError('stage decision target or chronology drifted')
        ref=self.owner._publish(self.scope,actor,key,item,expected_version=expected_version,identity=item.decision_id,
            identity_column='decision_id',resource_type='AnalystStageDecisionRevision',head_table='ecommerce_analyst_stage_decision_head',
            revision_table='ecommerce_analyst_stage_decision_revision',operation=_OPERATION)
        if self.read_exact(ref)!=item:raise ValueError('stage decision persistence drifted')
        return ref

    def read_exact(self,ref):
        ref=AnalystExactRef.model_validate(ref.model_dump())
        if ref.resource_type!='AnalystStageDecisionRevision':raise ValueError('exact stage decision required')
        row=self.tx.execute('''SELECT * FROM ecommerce_analyst_stage_decision_revision
            WHERE org_id=%s AND project_id=%s AND decision_id=%s AND revision=%s''',(*self.scope.key,ref.resource_id,ref.revision)).fetchone()
        if row is None:raise ValueError('stage decision unavailable in scope')
        item=AnalystStageDecisionRevision.model_validate(row['payload'])
        body=item.model_dump(mode='json',by_alias=True)
        digest=canonical_hash(item.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))
        expected=AnalystExactRef(resourceType='AnalystStageDecisionRevision',resourceId=item.decision_id,revision=item.revision,contentHash=digest)
        if (expected!=ref or item.content_hash!=digest or row['content_hash']!=digest
            or canonical_hash(row['payload'])!=canonical_hash(body) or item.decision_id!=stage_decision_id(item)
            or (item.tenant.org_id,item.tenant.project_id)!=self.scope.key or row['created_by']!=item.created_by
            or row['created_at']!=item.created_at or row['parent_revision']!=(None if item.revision==1 else item.revision-1)):
            raise ValueError('stage decision body or columns drifted')
        receipt=self.tx.execute('''SELECT request_hash,result_ref,created_by FROM ecommerce_analyst_authority_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s AND operation=%s''',(*self.scope.key,row['receipt_id'],_OPERATION)).fetchone()
        if (receipt is None or receipt['created_by']!=item.created_by
            or canonical_hash(receipt['result_ref'])!=canonical_hash(ref.model_dump(mode='json',by_alias=True))
            or receipt['request_hash']!=canonical_hash({'expectedVersion':item.version-1,'revision':body})):
            raise ValueError('stage decision receipt drifted')
        return item

    def read_current(self,ref):
        row=self.tx.execute('''SELECT current_revision,version FROM ecommerce_analyst_stage_decision_head
            WHERE org_id=%s AND project_id=%s AND decision_id=%s FOR SHARE''',(*self.scope.key,ref.resource_id)).fetchone()
        if row is None or row['current_revision']!=ref.revision or row['version']!=ref.revision:
            raise ValueError('stage decision is no longer current')
        return self.read_exact(ref)
