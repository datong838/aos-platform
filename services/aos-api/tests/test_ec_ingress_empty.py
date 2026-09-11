from contextlib import nullcontext
from unittest.mock import Mock
import pytest
from aos_api.ec_ingress_journal import IngressJournal, _validate
from aos_api.ec_ingress_recovery import recover_saved_authoritative_stages, read_saved_projection_completion
from aos_api.tenant_scope import TenantScope


def envelope():
    return dict(runId='run',pipelineId='p01',sourceId='source',
                sourceRevision='00000000-0000-0000-0000-000000000001',pipelineHash='a'*64,
                kind='empty_observation_v1',command=None,outputRows=[])


def test_empty_contract_and_derived_list():
    parent=envelope()
    assert len(_validate(TenantScope('org-org','dev-project'),parent))==64
    assert IngressJournal()._derived_payload(parent,[])['commands']==[]


@pytest.mark.parametrize('change',[{'outputRows':[{}]},{'command':{}},{'kind':'unknown'}])
def test_empty_envelope_cannot_hide_records(change):
    with pytest.raises(ValueError):
        _validate(TenantScope('org-org','dev-project'),dict(envelope(),**change))


def test_empty_recovery_never_calls_authoritative_store():
    journal=Mock();journal.read.return_value=envelope()
    journal.read_derived.side_effect=[None,{'commands':[]},{'commands':[]}]
    conn=Mock();conn.transaction.return_value=nullcontext()
    store=Mock()
    scope=TenantScope('org-org','dev-project')
    assert recover_saved_authoritative_stages(lambda _:nullcontext(conn),scope,'run',journal=journal,store=store)==()
    journal.save_derived.assert_called_once_with(conn,scope,'run',())
    assert read_saved_projection_completion(conn,scope,'run',journal=journal,store=store)=={'expected':0,'projected':0,'pending':0}
    assert store.mock_calls==[]
