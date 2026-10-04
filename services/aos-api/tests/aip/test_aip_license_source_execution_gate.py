import pytest
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionTransitionBlocked

@pytest.mark.parametrize('action_id,snapshot_id',[
    ('aip_issue_source_license','aip_issue_source_license'),
    ('aip_issue_source_license','ordinary'),
    ('ordinary','aip_issue_source_license'),
])
@pytest.mark.parametrize('policy',[{}, {'executionAllowed':True}])
def test_generic_execution_rejects_source_issuance_identity_even_if_policy_permits(action_id,snapshot_id,policy):
    row={'action_type_id':action_id,'action_type_snapshot':{'id':snapshot_id},
         'payload':{},'approval_policy':policy}
    with pytest.raises(AipActionTransitionBlocked,match='SOURCE_LICENSE_DEDICATED_ISSUER_REQUIRED'):
        AipActionExecutionService._reject_bootstrap_action(row)


def test_ordinary_internal_executor_precheck_is_unchanged():
    AipActionExecutionService._reject_bootstrap_action({
        'action_type_id':'ordinary-work-order','action_type_snapshot':{'id':'ordinary-work-order'},'payload':{}})
