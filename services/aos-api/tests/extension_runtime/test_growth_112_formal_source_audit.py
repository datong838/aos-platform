"""A clone success must never become a current formal Host authorization."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_growth_112_formal_source_audit.py"


@pytest.fixture
def audit():
    spec = spec_from_file_location("a0v_growth_112_formal_source_audit", SCRIPT)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_clone_release_does_not_authorize_current(audit):
    current = {"growth112Published": 0, "distinctPositiveTenantMembers": 1,
               "hostIdentity": 0, "hostAssignment": 0,
               "configurationCandidates": {name: 0 for name in audit.CANDIDATE_FIELDS}}
    clone = {**current, "growth112Published": 1}
    result = audit.assess_sources(current=current, clone=clone,
                                  current_trusts_growth112=False,
                                  credential_reference_present=False)
    assert result["formalReady"] is False
    assert set(result["reasons"]) == {
        "CURRENT_RELEASE_MISSING", "CURRENT_TRUST_ROOT_MISSING",
        "INDEPENDENT_CHECKER_MISSING", "THREE_PLANE_CREDENTIAL_REFERENCE_MISSING",
        "HOST_IDENTITY_MISSING", "HOST_ASSIGNMENT_MISSING",
        "CONFIGURATION_CANDIDATES_MISSING", "FORMAL_AUTHORIZATION_NOT_PROVEN",
    }


def test_missing_one_candidate_still_blocks(audit):
    full = {name: 1 for name in audit.CANDIDATE_FIELDS}
    full["budgets"] = 0
    state = {"growth112Published": 1, "distinctPositiveTenantMembers": 2,
             "hostIdentity": 1, "hostAssignment": 1,
             "configurationCandidates": full}
    result = audit.assess_sources(current=state, clone=state,
                                  current_trusts_growth112=True,
                                  credential_reference_present=True)
    assert result == {"formalReady": False,
                      "reasons": ["CONFIGURATION_CANDIDATES_MISSING",
                                  "FORMAL_AUTHORIZATION_NOT_PROVEN"]}


def test_clone_candidate_disappearance_is_reported(audit):
    complete = {"growth112Published": 1, "distinctPositiveTenantMembers": 2,
                "hostIdentity": 1, "hostAssignment": 1,
                "configurationCandidates": {name: 1 for name in audit.CANDIDATE_FIELDS}}
    clone = dict(complete, growth112Published=0)
    result = audit.assess_sources(current=complete, clone=clone,
                                  current_trusts_growth112=True,
                                  credential_reference_present=True)
    assert result["reasons"] == ["CLONE_SUCCESSOR_MISSING",
                                  "FORMAL_AUTHORIZATION_NOT_PROVEN"]
