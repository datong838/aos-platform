import pytest
from pydantic import ValidationError
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest
from test_ui_invocation import target


def payload():return dict(schemaVersion='aos.runtime-ui-read-request/v1',operationId='analyst_workspace_view_v1',moduleId='ecommerce.analyst',target=target())

def test_fixed_read_has_no_command_body_or_client_subject():
    result=UiReadRequest(**payload())
    assert result.caseLimit==20 and result.runLimit==5

@pytest.mark.parametrize('change',[{'operationId':'ecommerce_growth_case_put'},{'subject':'admin'},{'input':{'sql':'select 1'}},{'caseLimit':True},{'runLimit':11}])
def test_ui_read_cannot_request_arbitrary_execution(change):
    with pytest.raises(ValidationError):UiReadRequest(**(payload()|change))
