"""Integrity is not Rule approval; connection doubles never grant production authority."""
from datetime import datetime,timezone
from contextlib import contextmanager
import pytest
from aos_api.aip_production_contract_store import AipProductionContractStore,ProductionContractDependencyBlocked
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')

def case():
    spec={'testOnly':True,'kind':'fixture-check'}
    digest=canonical_hash({'ruleId':'fixture-rule','revision':1,'spec':spec})
    row={'rule_id':'fixture-rule','revision':1,'spec':spec,'content_hash':digest,'created_by':'fixture-creator','created_at':datetime.now(timezone.utc)}
    ref=ExactRevisionRef(resourceType='EvalRuleRevision',resourceId='fixture-rule',revision=1,contentHash=digest)
    return row,ref

class Conn:
    def __init__(self,row):self.row=row;self.reads=[]
    def execute(self,query,parameters):
        assert query.strip().startswith('SELECT');self.reads.append(parameters);return self
    def fetchone(self):return self.row
    def commit(self):pytest.fail('read must not commit caller transaction')

def store():
    @contextmanager
    def forbidden(scope):
        pytest.fail('must use caller transaction');yield
    return AipProductionContractStore(forbidden)


def test_exact_integrity_uses_original_getter_one_caller_transaction():
    row,ref=case();conn=Conn(row)
    value=store().get_review_rule_revision_with_content_integrity(SCOPE,ref,conn=conn)
    assert value.spec['testOnly'] is True  # digest does not approve this fixture
    assert conn.reads==[('org-org','dev-project','fixture-rule',1)]

@pytest.mark.parametrize('change',['spec','storedHash','referenceHash','id','revision','type'])
def test_tamper_rejected_without_write_or_fallback(change):
    row,ref=case()
    if change=='spec':row['spec']={'testOnly':False,'kind':'changed'}
    if change=='storedHash':row['content_hash']='2'*64
    if change=='referenceHash':ref=ref.model_copy(update={'content_hash':'2'*64})
    if change=='id':row['rule_id']='other'
    if change=='revision':row['revision']=2
    if change=='type':ref=ref.model_copy(update={'resource_type':'ApprovalRevision'})
    conn=Conn(row)
    with pytest.raises(ProductionContractDependencyBlocked):store().get_review_rule_revision_with_content_integrity(SCOPE,ref,conn=conn)
    if change=='type':assert not conn.reads


def test_historical_getter_still_reads_without_reclassifying_old_data():
    row,_=case();row['content_hash']='1'*64
    value=store().get_review_rule_revision(SCOPE,'fixture-rule',1,conn=Conn(row))
    assert value.content_hash=='1'*64
