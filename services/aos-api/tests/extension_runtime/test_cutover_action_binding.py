from copy import deepcopy
from uuid import uuid4
import pytest
from aos_api.aip_action_store import canonical_hash
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS


def binding():
    from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
    return internal_cutover_binding_hash


def inputs(kind='ecommerce_growth_cutover'):
    snapshot=dict(id=kind,name='internal cutover',objectType='BundleInstallation',parameters=[],requiredMarkings=[],submissionCriteria=[])
    snapshot['revisionHash']=canonical_hash(snapshot)
    ref=lambda resource:dict(resourceType=resource,resourceId=str(uuid4()),revision=1,contentHash='sha256:'+'a'*64)
    payload=dict(cutoverGroupId=str(uuid4()),expectedGroupRevision=1,targetInstallationId=str(uuid4()),
        targetGeneration=str(uuid4()),targetExecutionEpoch=3,operationIds=sorted(ECOMMERCE_GROWTH_OPERATIONS))
    if kind=='ecommerce_growth_cutover':payload.update(targetRuntimeRevision=4,policyRef=ref('Policy'),registrationReceiptRef=ref('FirstDispatchRegistrationReceipt'))
    else:payload.update(activationOperationId=str(uuid4()),commitReceiptRef=ref('CutoverCommitReceipt'))
    return snapshot,payload


@pytest.mark.parametrize('kind',['ecommerce_growth_cutover','ecommerce_growth_cutover_rollback'])
def test_binding_is_deterministic_and_scope_bound(kind):
    snapshot,payload=inputs(kind);scope=TenantScope('org-org','dev-project')
    value=binding()(scope=scope,action_snapshot=snapshot,payload=payload)
    assert len(value)==64
    assert value==binding()(scope=scope,action_snapshot=deepcopy(snapshot),payload=deepcopy(payload))
    assert value!=binding()(scope=TenantScope('dev-org','dev-project'),action_snapshot=snapshot,payload=payload)
    changed=deepcopy(payload);changed['targetExecutionEpoch']+=1
    assert value!=binding()(scope=scope,action_snapshot=snapshot,payload=changed)


@pytest.mark.parametrize('defect',['snapshot-hash','unknown-action','unknown-field','bool-version','operation-set','uuid','missing-origin'])
def test_untrusted_binding_material_is_rejected(defect):
    snapshot,payload=inputs()
    if defect=='snapshot-hash':snapshot['name']='drift'
    elif defect=='unknown-action':snapshot['id']='arbitrary';snapshot['revisionHash']=canonical_hash({k:v for k,v in snapshot.items() if k!='revisionHash'})
    elif defect=='unknown-field':payload['approved']=True
    elif defect=='bool-version':payload['expectedGroupRevision']=True
    elif defect=='operation-set':payload['operationIds']=payload['operationIds'][:-1]
    elif defect=='uuid':payload['targetInstallationId']='not-an-installation'
    else:payload.pop('registrationReceiptRef')
    with pytest.raises((ValueError,TypeError)):
        binding()(scope=TenantScope('org-org','dev-project'),action_snapshot=snapshot,payload=payload)
