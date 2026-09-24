from copy import deepcopy

import pytest

import a0v_w5c3o_uninstalled_ds_register as wave


def facts():
    operations = sorted([
        "ecommerce_growth_analysis_advance", "ecommerce_growth_case_put",
        "ecommerce_growth_content_generate", "ecommerce_growth_content_review",
        "ecommerce_growth_data_fulfill", "ecommerce_growth_investigation_describe",
        "ecommerce_growth_review_advance", "ecommerce_growth_schedule_put",
        "ecommerce_growth_schedule_trigger"])
    rows = [dict(operation_id=op, handler_kind="legacy", installation_id=None,
        generation=None, execution_epoch=None, operation_fence=True, revision=338,
        cutover_group_id=wave.GROUP, cutover_group_revision=365) for op in operations]
    snapshot = [dict(operationId=row["operation_id"], handlerKind="legacy",
        installationId=None, generation=None, executionEpoch=None, operationFence=True,
        revision=338, cutoverGroupId=wave.GROUP, cutoverGroupRevision=365) for row in rows]
    return dict(prior=dict(installationId=wave.INSTALLATION, bindingRevision=4,
        executionEpoch=3), uninstalledSuccessorGuardLoaded=True,
        newInstallationSuccessorReceipts=[], newInstallationSelections=[],
        newInstallationControls=dict(revisions=0,pipelines=0),
        oldSchedules=dict(total=12,enabled=0), routes=rows,
        currentDetachAuthority=dict(receipt_id=wave.DETACH, content_hash=wave.DETACH_HASH,
          status="detached", lifecycle_status="detached", fenced_group_revision=364,
          disable_status="succeeded", disable_phase="succeeded", enabled=False,
          operation_fence=True, desired_state="uninstalled", observed_state="stopped",
          old_active_revision=None, unsafe_resources=0, dispatch_snapshot=snapshot))


CONFIG = {"configurationId": "f8d1f58f-9a49-48e2-b1a4-262e22f929f0", "revision": 1,
          "hash": "sha256:f21169b03b4aba5dec2e6bbaa8ee8921e5ed833eee558f051b6e564aa068e359"}
HEAD = {"installation_id": wave.legacy.DS_ID, "state": "uninstalled"}


def test_exact_uninstalled_registration_preview():
    request = wave.request_from(facts(), config_ref=CONFIG, old_head=HEAD)
    assert request.expectedGroupRevision == 365
    assert request.registration.installationRef.installation_id == wave.INSTALLATION
    assert request.predecessorDetachReceiptRef.resourceId == wave.DETACH


@pytest.mark.parametrize("path,value", [
    (("uninstalledSuccessorGuardLoaded",), False),
    (("currentDetachAuthority","old_active_revision"), 5),
    (("currentDetachAuthority","desired_state"), "disabled"),
    (("currentDetachAuthority","unsafe_resources"), 1),
    (("routes",0,"operation_fence"), False),
    (("routes",0,"cutover_group_revision"), 366),
    (("newInstallationSuccessorReceipts",), [dict(receipt_id="already")]),
])
def test_drift_rejected(path, value):
    data = deepcopy(facts())
    target = data
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        wave.request_from(data, config_ref=CONFIG, old_head=HEAD)


def test_snapshot_mismatch_rejected():
    data = facts()
    data["currentDetachAuthority"]["dispatch_snapshot"][0]["revision"] = 337
    with pytest.raises(ValueError, match="DETACH_SNAPSHOT_DRIFT"):
        wave.request_from(data, config_ref=CONFIG, old_head=HEAD)
