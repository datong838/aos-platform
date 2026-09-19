import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ap_continuation_router.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ap_continuation_router", PATH)
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


@pytest.mark.parametrize(("outcome", "action"), (
    ("RUNNING_HEALTHY_NO_ACTION", "OBSERVE_AP_RECOVERY"),
    ("RUNNING_HEARTBEAT_ONLY_DIAGNOSE", "DIAGNOSE_AP_BOUNDED_EXECUTION"),
    ("RUNNING_STALE_DIAGNOSE_ONLY", "DIAGNOSE_AP_HEARTBEAT"),
    ("SUCCEEDED_STRICT_CLOSURE", "RUN_AP_INSPECT_THEN_DISABLE"),
    ("FAILED_FREEZE_BOUNDARY", "FREEZE_AP_FAILURE_BOUNDARY"),
    ("ABANDONED_FREEZE_BOUNDARY", "FREEZE_AP_ABANDONED_BOUNDARY"),
    ("FAILED_CHAIN_PAUSE_REQUIRED", "RUN_AP_FAILED_PAUSE"),
))
def test_route_is_explicit_and_non_executing(outcome, action):
    result = router.classify(
        {"attemptId": "attempt", "state": "running"},
        {"outcome": outcome, "automaticAction": False},
    )
    assert result["nextAction"] == action
    assert result["businessWrites"] == 0


def test_unknown_or_executing_guard_fails_closed():
    with pytest.raises(RuntimeError):
        router.classify({}, {"outcome": "unknown", "automaticAction": False})
    with pytest.raises(RuntimeError):
        router.classify({}, {"outcome": "RUNNING_HEALTHY_NO_ACTION", "automaticAction": True})


def test_router_source_is_read_only_and_main_emits_one_json():
    source = PATH.read_text(encoding="utf-8")
    assert "run_definition" not in source
    assert "INSERT INTO" not in source
    command = [sys.executable, "-c", (
        "import importlib.util;"
        f"s=importlib.util.spec_from_file_location('router',{str(PATH)!r});"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "m.observe=lambda:(print('runtime-log'),{'outcome':'TEST_ROUTED'})[1];"
        "raise SystemExit(m.main())"
    )]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    assert json.loads(result.stdout) == {"outcome": "TEST_ROUTED"}
    assert "runtime-log" in result.stderr
