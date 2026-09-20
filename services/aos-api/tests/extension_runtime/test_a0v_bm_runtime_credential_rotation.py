from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]


def load_module():
    path = ROOT / "scripts/a0v_bm_runtime_credential_rotation.py"
    spec = importlib.util.spec_from_file_location("a0v_bm_runtime_credential_rotation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rotation_is_fixed_to_existing_three_plane_roles():
    module = load_module()
    assert module.HOST_ID == "a0v-local-ecommerce-host-20260912"
    assert module.ROLES == {
        "web": "aos_a0v_web_20260912",
        "runtime": "aos_a0v_runtime_20260912",
        "directory": "aos_a0v_directory_20260912",
    }
    assert "run_definition" not in (ROOT / "scripts/a0v_bm_runtime_credential_rotation.py").read_text()


def test_exact_snapshot_rejects_role_or_canary_drift():
    module = load_module()
    exact = {
        "roles": {
            "web": {"rolcanlogin": True, "rolsuper": False, "rolbypassrls": False,
                    "runtime_member": False, "directory_member": False},
            "runtime": {"rolcanlogin": True, "rolsuper": False, "rolbypassrls": False,
                        "runtime_member": True, "directory_member": False},
            "directory": {"rolcanlogin": True, "rolsuper": False, "rolbypassrls": False,
                          "runtime_member": False, "directory_member": True},
        },
        "identity": {"database_role": module.ROLES["directory"], "host_id": module.HOST_ID,
                     "enabled": True, "revision": 1},
        "assignment": {"host_id": module.HOST_ID, "state": "assigned", "revision": 1},
        "canaryAssignments": 0,
    }
    module._assert_exact(exact)
    exact["canaryAssignments"] = 1
    with pytest.raises(module.RotationBlocked) as captured:
        module._assert_exact(exact)
    assert captured.value.code == "CANARY_ASSIGNMENT_PRESENT"


def test_private_result_is_exclusive_and_mode_0600(tmp_path):
    module = load_module()
    path = tmp_path / "result.json"
    module._freeze(path, {"outcome": "GREEN"})
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module._freeze(path, {"outcome": "DIFFERENT"})
