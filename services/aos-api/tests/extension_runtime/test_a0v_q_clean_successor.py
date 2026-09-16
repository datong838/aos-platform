import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]


def load_module():
    path = ROOT / "scripts/a0v_q_clean_successor.py"
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("a0v_q_clean_successor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def database(module):
    authority = {"phase": "detach", "receiptId": module.P_DETACH}
    from aos_api.asset_registry.canonical_json import canonical_sha256
    content_hash = canonical_sha256(authority)
    module.P_DETACH_HASH = content_hash
    return {
        "detach": {"receipt_id": module.P_DETACH, "phase": "detach",
                   "content_hash": content_hash, "authority_data": authority},
        "routes": [{"operation_id": value, "handler_kind": "legacy",
                    "installation_id": None, "generation": None, "execution_epoch": None,
                    "operation_fence": True, "revision": 29, "cutover_group_revision": 53}
                   for value in {"a", "b"}],
        "schedule": {"enabled": False, "last_run": "scr-current"},
        "safety": {"running": 0, "unresolved": 0, "canary": 0},
    }


def test_accepts_exact_terminal_route_snapshot():
    module = load_module()
    value = database(module)
    assert module._validate_database_snapshot(value, {"a", "b"}) is value


@pytest.mark.parametrize("mutation", ["group", "cursor", "canary", "detach"])
def test_rejects_any_authority_drift(mutation):
    module = load_module()
    value = database(module)
    if mutation == "group":
        value["routes"][0]["cutover_group_revision"] = 52
    elif mutation == "cursor":
        value["schedule"]["last_run"] = None
    elif mutation == "canary":
        value["safety"]["canary"] = 1
    else:
        value["detach"]["receipt_id"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError):
        module._validate_database_snapshot(value, {"a", "b"})
