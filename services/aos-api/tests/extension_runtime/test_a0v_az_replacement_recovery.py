import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "a0v_az_replacement_recovery", ROOT / "scripts/a0v_az_replacement_recovery.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_az_requires_detached_ax_and_retired_ay():
    assert MODULE.replacement.AU_ID == "be884663-0dba-4d9b-aa56-84caaf01147d"
    assert MODULE.replacement.AU_DETACH_RECEIPT == "622c8e25-ec0f-40dd-bf1f-ea57d180a800"
    assert MODULE.replacement.PREDECESSOR_ROUTE_REVISION == 125
    assert MODULE.AY_ID == "81df994f-23ce-4448-ac46-366aaee63924"
    assert MODULE.AY_RETIREMENT_RECEIPT == "48fc0e55-578d-46ae-b45a-bf8ab8085823"
    assert MODULE.replacement.INSTALLATION_LABEL == "az"
