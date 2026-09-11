import pytest
from aos_api.aip_evidence_dependencies import POLICY, require_evidence_dependencies
from aos_api.data_requirement_store import canonical_hash
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('fault',['none','revoked','hash','nested','duplicate','boolean','empty','version','missing'])
def test_leaf_dependencies_fail_closed(fault):
    payload={'factIds':[]}
    if fault=='nested': payload['evidencePolicyVersion']=POLICY
    digest=canonical_hash(payload)
    ref=dict(resourceType='Evidence',resourceId='source',revision=1,contentHash=digest)
    body=dict(evidencePolicyVersion=POLICY,upstreamEvidenceRefs=[ref])
    row=dict(payload=payload,content_hash=digest,revoked=fault=='revoked')
    if fault=='hash': row['content_hash']='0'*64
    if fault=='duplicate': body['upstreamEvidenceRefs'].append(dict(ref))
    if fault=='boolean': ref['revision']=True
    if fault=='empty': body['upstreamEvidenceRefs']=[]
    if fault=='version': body['evidencePolicyVersion']='unknown'
    class Connection:
        def execute(self,query,params):
            assert params==('org','project','source')
            return self
        def fetchone(self): return None if fault=='missing' else row
    if fault=='none': require_evidence_dependencies(Connection(),TenantScope('org','project'),body)
    else:
        with pytest.raises(ValueError): require_evidence_dependencies(Connection(),TenantScope('org','project'),body)
