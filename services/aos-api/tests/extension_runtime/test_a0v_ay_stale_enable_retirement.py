import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "a0v_ay_stale_enable_retirement", ROOT / "scripts/a0v_ay_stale_enable_retirement.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_fixed_ay_stale_enable_authority():
    assert MODULE.INSTALLATION == "81df994f-23ce-4448-ac46-366aaee63924"
    assert MODULE.GENERATION == "a1069f60-46f5-41a8-bd18-61ed677eb3bd"
    assert MODULE.STALE_ENABLE == "24a85b28-f00d-43cf-ba5d-28f064c74f6a"
    assert MODULE.ACTIONS == ("preflight", "request-disable", "process-disable", "retire", "audit")


def test_run_rejects_unknown_action():
    with pytest.raises(KeyError):
        MODULE.run("resume-enable")


def test_intents_are_immutable(tmp_path):
    path = tmp_path / "intent.json"
    MODULE.freeze_or_match(path, {"operationId": "one"})
    MODULE.freeze_or_match(path, {"operationId": "one"})
    with pytest.raises(ValueError, match="immutable AY"):
        MODULE.freeze_or_match(path, {"operationId": "two"})
