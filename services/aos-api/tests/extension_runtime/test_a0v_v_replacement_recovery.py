"""V replacement keeps U as the exact drained predecessor through enable."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_v_replacement_recovery.py"
SPEC = importlib.util.spec_from_file_location("a0v_v_replacement_recovery", PATH)
replacement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replacement)


def test_v_uses_exact_u_replacement_and_current_package_versions():
    assert replacement.U_ID == "277fe01c-ece7-4c8f-9500-fc1ba0d5f050"
    assert replacement.U_DISABLE_OPERATION == "035fdbcb-dee2-4aeb-afd8-e1f81c95c706"
    assert replacement.VERSIONS["platform.ecommerce.niushop"] == "1.23.0"
    source = PATH.read_text(encoding="utf-8")
    assert "current_installation_ref=predecessor" in source
    assert "uninstall" not in replacement.ACTIONS


def test_v_enable_requires_the_existing_profile_replacement_guard():
    source = PATH.read_text(encoding="utf-8")
    assert 'profile.replacement_ref(detached_u(profile))' in source
    assert 'return profile.configure("v", action)' in source
    assert "UPDATE extension_runtime_binding" not in source
