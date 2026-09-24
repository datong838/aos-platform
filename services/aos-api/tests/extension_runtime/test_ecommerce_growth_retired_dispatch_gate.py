from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
import aos_api.ecommerce_growth_lifecycle as lifecycle_module
from aos_api.ecommerce_growth_lifecycle import (
    EcommerceGrowthDisableDependent, EcommerceGrowthLifecycleBlocked,
    EcommerceGrowthLifecycleConflict,
)
from aos_api.tenant_scope import TenantScope


class _Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class _Connection:
    def __init__(self, *, rows, gate=None, attached=None, history=None, status="resumed"):
        self.rows = rows
        self.gate = gate
        self.attached = attached
        self.history = history or {"total": 1, "detached": 1}
        self.status = status

    def execute(self, query, _params):
        if "extension_dispatch_retired_read_lock_a0v_092" in query:
            return _Result(None)
        if "FROM public.extension_dispatch_cutover_operation" in query:
            return _Result({"status": self.status})
        if "FROM public.extension_operation_dispatch_binding" in query:
            if "cutover_group_id" in query:
                return _Result(self.rows)
            return _Result(self.attached)
        if "FROM public.extension_dispatch_claim_gate" in query:
            return _Result(self.gate)
        if "FROM public.extension_dispatch_lifecycle_operation" in query:
            return _Result(self.history)
        raise AssertionError(query)


def _rows():
    return [{"operation_id": operation, "handler_kind": "legacy",
             "installation_id": None, "generation": None,
             "execution_epoch": None, "operation_fence": True}
            for operation in ECOMMERCE_GROWTH_OPERATIONS]


def _activation():
    return {"cutover_operation_id": uuid4(), "cutover_group_id": uuid4(),
            "target_installation_id": uuid4(), "target_generation": uuid4()}


def test_only_complete_detached_legacy_group_is_recognized(monkeypatch):
    owner = EcommerceGrowthDisableDependent()
    checked = []
    monkeypatch.setattr(owner, "_assert_recovery_drained", lambda *_: checked.append(True))
    assert owner._retired_dispatch_group(_Connection(rows=_rows()),
                                         TenantScope("org-org", "dev-project"), uuid4(),
                                         _activation())
    assert checked == [True]


@pytest.mark.parametrize("change", ["missing", "mixed", "unfenced", "gate", "attached", "history", "status"])
def test_incomplete_retirement_never_skips_current_gate(monkeypatch, change):
    rows = _rows()
    options = {"rows": rows}
    if change == "missing":
        options["rows"] = rows[:-1]
    elif change == "mixed":
        rows[0]["handler_kind"] = "extension"
    elif change == "unfenced":
        rows[0]["operation_fence"] = False
    elif change == "gate":
        options["gate"] = {"revision": 2}
    elif change == "attached":
        options["attached"] = {"operation_id": rows[0]["operation_id"]}
    elif change == "history":
        options["history"] = {"total": 1, "detached": 0}
    elif change == "status":
        options["status"] = "committed"
    owner = EcommerceGrowthDisableDependent()
    monkeypatch.setattr(owner, "_assert_recovery_drained", lambda *_: pytest.fail("not retired"))
    assert not owner._retired_dispatch_group(_Connection(**options),
                                             TenantScope("org-org", "dev-project"), uuid4(),
                                             _activation())


def test_unresolved_attempt_blocks_retired_noop(monkeypatch):
    owner = EcommerceGrowthDisableDependent()
    def blocked(*_):
        raise EcommerceGrowthLifecycleBlocked("unresolved attempt")
    monkeypatch.setattr(owner, "_assert_recovery_drained", blocked)
    with pytest.raises(EcommerceGrowthLifecycleBlocked, match="unresolved attempt"):
        owner._retired_dispatch_group(_Connection(rows=_rows()),
                                      TenantScope("org-org", "dev-project"), uuid4(),
                                      _activation())


def test_multiple_matched_activations_never_take_retired_shortcut(monkeypatch):
    class Connection:
        def execute(self, query, _params):
            if "FROM public.extension_dispatch_lifecycle_operation" in query:
                return _Result(None)
            if "FROM public.extension_dispatch_cutover_operation" in query:
                return _Result([
                    {**_activation(), "current_binding_revision": 12,
                     "current_binding_epoch": 6},
                    {**_activation(), "current_binding_revision": 12,
                     "current_binding_epoch": 6},
                ])
            raise AssertionError(query)

    owner = EcommerceGrowthDisableDependent()
    monkeypatch.setattr(lifecycle_module, "_require_transaction", lambda _: None)
    monkeypatch.setattr(owner, "_scope", lambda *_: TenantScope("org-org", "dev-project"))
    monkeypatch.setattr(owner, "_runtime_operation", lambda *_: {
        "status": "accepted", "expected_binding_revision": 11,
        "installation_id": uuid4(),
    })
    monkeypatch.setattr(owner, "_load_receipt", lambda *_: None)
    monkeypatch.setattr(owner, "_current_dispatch_authority", lambda *_: (4, 3, None))
    monkeypatch.setattr(owner, "_retired_dispatch_group", lambda *_: pytest.fail("shortcut"))
    with pytest.raises(EcommerceGrowthLifecycleConflict) as error:
        owner.after_runtime_fenced(Connection(), org_id="org-org", project_id="dev-project",
                                   runtime_operation_id=uuid4())
    assert "multiple resumed activations" in str(error.value)
