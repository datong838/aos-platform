import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def successor(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "scripts"))
    module = importlib.import_module("a0v_ecommerce_current_signed_successor")
    return module.load_successor()


def _qualified_document():
    profile = importlib.import_module("build_ecommerce_ui_candidates")
    fixture = json.loads(profile.FIXTURE.read_bytes())
    sessions = {
        key: {
            "registration": "exact",
            "heartbeat": "alive",
            "cleanup": "released",
            "contributionCount": count,
            "heartbeatChecks": 2048,
        }
        for key, count in (
            ("domain.ecommerce.core", 1),
            ("platform.ecommerce.niushop", 2),
            ("solution.ecommerce.growth", 25),
        )
    }
    sessions["solution.ecommerce.growth"]["readProbe"] = {
        "method": profile.METHOD,
        "fixtureHash": "sha256:" + profile.FIXTURE_HASH,
        "payloadHash": profile._hash(fixture["payload"]),
        "resultHash": profile._hash(fixture["expected"]),
        "caseCount": 1,
        "runCount": 1,
        "executionAllowed": False,
        "evidence": "qualification-fixture-only",
    }
    return {"runtimeSessions": sessions}


def test_successor_uses_exact_parent_and_current_coordinates(successor):
    assert successor.EXPECTED_OLD_COUNT == 16
    assert successor.EXPECTED_NEW_COUNT == 17
    assert "niushop-1.23-current" in str(successor.OLD_ROOT)
    assert "growth-1.9-current" in str(successor.NEW_ROOT)
    assert successor.NEW_ROOT != successor.OLD_ROOT
    assert successor.VERSIONS == {
        "domain.ecommerce.core": "1.3.0",
        "platform.ecommerce.niushop": "1.23.0",
        "solution.ecommerce.growth": "1.9.0",
        "solution.ecommerce.operations-base": "1.2.0",
    }
    assert successor.legacy()._builder().preflight()["operationCount"] == 14


@pytest.mark.parametrize("drift", ["cleanup", "heartbeat", "count", "probe"])
def test_successor_rejects_incomplete_runtime_qualification(successor, drift):
    document = _qualified_document()
    session = document["runtimeSessions"]["solution.ecommerce.growth"]
    if drift == "cleanup":
        session["cleanup"] = "unknown"
    elif drift == "heartbeat":
        session["heartbeatChecks"] = 2047
    elif drift == "count":
        document["runtimeSessions"]["platform.ecommerce.niushop"]["contributionCount"] = 3
    else:
        session["readProbe"]["resultHash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        successor.require_sessions(document)


def test_successor_accepts_exact_three_member_qualification(successor):
    successor.require_sessions(_qualified_document())
