import pytest

from aos_api.extension_runtime.lifecycle import AdmissionFacts, effective_ready, next_phase


def ready():
    return dict(installation_active=True, installation_revision=3, binding_installation_revision=3,
                binding_ready=True, enabled=True, operation_fence=False, execution_epoch=4,
                request_epoch=4, permissions_valid=True, budget_valid=True, policy_valid=True)


def test_effective_ready_requires_every_fact():
    assert effective_ready(AdmissionFacts(**ready()))
    for field in ("installation_active", "binding_ready", "enabled", "permissions_valid", "budget_valid", "policy_valid"):
        values=ready(); values[field]=False
        assert not effective_ready(AdmissionFacts(**values))
    for field,value in [("operation_fence",True),("request_epoch",3),("binding_installation_revision",2)]:
        values=ready(); values[field]=value
        assert not effective_ready(AdmissionFacts(**values))


def test_strict_facts_reject_coercion_and_unknown():
    for field,value in [("enabled",1),("execution_epoch",True),("request_epoch",0),("installation_revision",0)]:
        values=ready(); values[field]=value
        with pytest.raises(ValueError):
            AdmissionFacts(**values)


def test_uninstall_cannot_skip_resource_confirmation():
    with pytest.raises(ValueError):
        next_phase("uninstall-execute", "draining", "succeeded")
    assert next_phase("uninstall-execute", "resources_released", "committing") == "committing"
    assert next_phase("uninstall-execute", "committing", "succeeded") == "succeeded"


def test_terminal_cannot_restart_or_switch_operation():
    for kind,current,target in [("runtime-apply","succeeded","validating"),
                                ("enable","accepted","resources_released"),
                                ("reinstall","accepted","succeeded")]:
        with pytest.raises(ValueError):
            next_phase(kind,current,target)
