"""X cutover has a new operation namespace and group71 predecessor."""

import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_x_successor_cutover.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_x_successor_cutover", PATH)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_x_cutover_is_independent_and_targets_group71():
    assert cutover.OPERATION == "c93c537b-821e-5ae5-a0cf-adc7ae1a3d88"
    assert cutover.PREFIX.endswith("x-cutover-v1")
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 71' in source
    assert 'fallbackAllowed": False' in source


def test_x_cutover_uses_receipt_services_only():
    source = PATH.read_text(encoding="utf-8")
    for method in ("prepare_activation", "begin_activation_commit", "commit_activation",
                   "validate_activation", "resume_activation"):
        assert method in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
