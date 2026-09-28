from datetime import datetime, timezone
from unittest.mock import MagicMock,patch
from uuid import uuid4

import pytest

from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict,OperationResult


def setup_service():
    store=MagicMock();reader=MagicMock();validator=MagicMock();conn=MagicMock()
    store.lock_for_transition_in_transaction.return_value.record.state="approved"
    store.execute_idempotent.side_effect=lambda **kw:kw["handler"](conn)
    conn.execute.return_value.fetchone.return_value=None
    validator.revalidate_in_transaction.return_value.checked_at=datetime.now(timezone.utc)
    validator.revalidate_in_transaction.return_value.runtime_members=("runtime-test",)
    service=RuntimeLifecycleService(installation_store=store,installation_reader=reader,revalidator=validator)
    args=dict(installation_id=str(uuid4()),kind="runtime-apply",org_id="org-org",project_id="dev-project",
        actor="installer",roles=["asset-installer"],markings=[],idempotency_key="test",if_match='"3"',
        preparation_admission=lambda: True)
    return service,args,store,reader,validator,conn


@pytest.mark.parametrize("case",["accepted","wrong-state","pure-content","active-operation","revoked"])
def test_preparation_requests_do_not_activate(case):
    service,args,store,reader,validator,conn=setup_service()
    if case=="wrong-state":store.lock_for_transition_in_transaction.return_value.record.state="draft"
    if case=="pure-content":validator.revalidate_in_transaction.return_value.runtime_members=()
    if case=="active-operation":conn.execute.return_value.fetchone.return_value={"operation_id":uuid4()}
    if case=="revoked":reader.get.side_effect=PermissionError("revoked")
    with patch("aos_api.extension_runtime.lifecycle_service._load_current_lock"),patch(
        "aos_api.extension_runtime.lifecycle_service._require_lock_markings"),patch(
        "aos_api.extension_runtime.lifecycle_service.RuntimeOperationStore") as operations:
        operations.return_value.accept.return_value=OperationResult(uuid4(),"accepted","accepted",1)
        if case=="accepted":
            response=service.request_preparation(**args)
            assert response.status_code==202 and response.response_json["status"]=="accepted"
            assert store.lock_for_transition_in_transaction.call_args.kwargs["expected_etag_version"]==3
        else:
            with pytest.raises((RuntimeConflict,PermissionError)):
                service.request_preparation(**args)
            operations.return_value.accept.assert_not_called()
    store.append_apply_in_transaction.assert_not_called()
    store.append_verify_in_transaction.assert_not_called()


def test_unauthorized_request_does_not_read_or_write():
    service,args,store,reader,_,_=setup_service()
    from aos_api.asset_registry.errors import DutySeparationRequiredError
    with pytest.raises(DutySeparationRequiredError):
        service.request_preparation(**{**args,"roles":["developer"]})
    reader.get.assert_not_called();store.execute_idempotent.assert_not_called()


def test_new_preparation_refuses_missing_host_without_operation_or_receipt():
    service,args,store,_,_,_=setup_service()
    with patch("aos_api.extension_runtime.lifecycle_service._load_current_lock"),patch(
        "aos_api.extension_runtime.lifecycle_service._require_lock_markings"),patch(
        "aos_api.extension_runtime.lifecycle_service.RuntimeOperationStore") as operations:
        with pytest.raises(RuntimeConflict, match="host"):
            service.request_preparation(**{**args, "preparation_admission": lambda: False})
    operations.return_value.accept.assert_not_called()


def test_existing_preparation_receipt_replay_does_not_require_new_host_admission():
    service,args,store,_,_,_=setup_service()
    original = object()
    store.execute_idempotent.side_effect = None
    store.execute_idempotent.return_value = original
    assert service.request_preparation(**{**args, "preparation_admission": lambda: False}) is original


@pytest.mark.parametrize("action",["submit","apply"])
def test_planning_validator_does_not_replace_execution_gate(action):
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.composition_contracts import EmptyInstallationActionRequest
    store=MagicMock();legacy=MagicMock();planning=MagicMock()
    legacy.revalidate_in_transaction.side_effect=RuntimeConflict("legacy runtime execution forbidden")
    service=InstallationService(store=store,composition_store=MagicMock(),revalidator=legacy,planning_revalidator=planning)
    store.execute_idempotent.side_effect=lambda **kw:kw["handler"](MagicMock())
    args=dict(installation_id=str(uuid4()),request=EmptyInstallationActionRequest(),org_id="org-org",
        project_id="dev-project",actor="installer",roles=["asset-installer"],markings=[],
        idempotency_key="plan",if_match='"1"')
    with patch("aos_api.asset_registry.installation_service._load_current_lock"),patch(
        "aos_api.asset_registry.installation_service._require_lock_markings"),patch(
        "aos_api.asset_registry.installation_service._command_result"),patch.object(service,"_authorize_receipt"):
        if action=="submit":
            service.submit(**args)
            planning.revalidate_in_transaction.assert_called_once()
            legacy.revalidate_in_transaction.assert_not_called()
        else:
            with pytest.raises(RuntimeConflict,match="forbidden"):
                service.apply(**args)
            planning.revalidate_in_transaction.assert_not_called()
            store.append_apply_in_transaction.assert_not_called()


@pytest.mark.parametrize("guard_fails", [False, True])
def test_installation_uninstall_calls_runtime_guard_before_append(guard_fails):
    from aos_api.asset_registry.installation_service import InstallationService

    store=MagicMock();guard=MagicMock();locked=MagicMock();conn=MagicMock()
    locked.org_id="org-org";locked.project_id="dev-project"
    locked.record.installation_id=str(uuid4());locked.record.current.revision=5
    service=InstallationService(store=store,composition_store=MagicMock(),
        revalidator=MagicMock(),runtime_uninstall_guard=guard)
    sequence=MagicMock()
    sequence.attach_mock(store.guard_no_active_replacement_in_transaction,"leaf")
    sequence.attach_mock(guard.before_uninstall,"runtime")
    sequence.attach_mock(store.append_uninstall_in_transaction,"append")
    if guard_fails:
        guard.before_uninstall.side_effect=RuntimeConflict("resources unresolved")
    with patch("aos_api.asset_registry.installation_service._evidence",return_value=MagicMock()):
        if guard_fails:
            with pytest.raises(RuntimeConflict,match="unresolved"):
                service._append_uninstall(conn,locked,MagicMock(reason="retire"),"operator",MagicMock())
            store.read_control_clock_in_transaction.assert_not_called()
            store.append_uninstall_in_transaction.assert_not_called()
        else:
            service._append_uninstall(conn,locked,MagicMock(reason="retire"),"operator",MagicMock())
            guard.before_uninstall.assert_called_once_with(conn,org_id="org-org",
                project_id="dev-project",installation_id=locked.record.installation_id,
                expected_installation_revision=5,actor="operator")
            store.append_uninstall_in_transaction.assert_called_once()
            names=[call[0] for call in sequence.mock_calls]
            assert names.index("leaf") < names.index("runtime") < names.index("append")
