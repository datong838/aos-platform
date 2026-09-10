from unittest.mock import Mock
import pytest
from aos_api import ecom_projector as projector
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')


def test_drain_continues_until_real_queue_empty(monkeypatch):
    project=Mock(side_effect=[{'projected':500,'pending':2},{'projected':2,'pending':0}])
    monkeypatch.setattr(projector,'project_pending',project)
    assert projector.project_until_caught_up(SCOPE,deadline=float('inf')) == {'projected':502,'pending':0}
    assert project.call_count==2


def test_drain_does_not_start_after_deadline_or_cancel(monkeypatch):
    project=Mock()
    monkeypatch.setattr(projector,'project_pending',project)
    with pytest.raises(RuntimeError,match='PROJECTION_DEADLINE_EXCEEDED'):
        projector.project_until_caught_up(SCOPE,deadline=0)
    cancel=Mock();cancel.is_set.return_value=True
    with pytest.raises(RuntimeError,match='PROJECTION_CANCELLED'):
        projector.project_until_caught_up(SCOPE,deadline=float('inf'),cancel_event=cancel)
    project.assert_not_called()


def test_drain_pending_locked_rows_waits_and_observes_cancel(monkeypatch):
    project=Mock(return_value={'projected':0,'pending':1})
    monkeypatch.setattr(projector,'project_pending',project)
    cancel=Mock();cancel.is_set.side_effect=[False,False,True]
    with pytest.raises(RuntimeError,match='PROJECTION_CANCELLED'):
        projector.project_until_caught_up(SCOPE,deadline=float('inf'),cancel_event=cancel)
    assert project.call_count==1
    cancel.wait.assert_called_once()


@pytest.mark.parametrize('result',[{}, {'projected':0,'pending':-1},{'projected':True,'pending':0}])
def test_invalid_projection_result_never_success(monkeypatch,result):
    monkeypatch.setattr(projector,'project_pending',Mock(return_value=result))
    with pytest.raises(RuntimeError,match='PROJECTION_RESULT_INVALID'):
        projector.project_until_caught_up(SCOPE,deadline=float('inf'))
