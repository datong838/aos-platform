"""Pure stop gates for the current six-agent one-intent command."""
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_six_agent_install.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("current_six_agent_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
writer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(writer)


def test_install_intent_requires_canonical_uuid():
    good = "55f1cce8-73a3-43b6-a834-b25c675d3afc"
    assert writer._canonical_uuid(good) == good
    for bad in (None, "", "invalid", good.upper(), good.replace("-", "")):
        with pytest.raises(writer.AgentInstallBlocked, match="EXACT_INTENT_UUID_REQUIRED"):
            writer._canonical_uuid(bad)


def test_install_intent_name_is_distinct_from_definition_publication():
    assert writer.INTENT_NAME == "aip-six-agent-install-1.11.0-intent.json"
    assert writer.INTENT_NAME != "aip-definition-publication-1.11.0-intent.json"
