import importlib
import json

import pytest

from test_analyst_package_proposals import BACKEND
from test_analyst_structure_case import query


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module("ecommerce_growth")


@pytest.mark.parametrize("stage", ["portrait", "diagnosis", "solution-design"])
def test_analysis_operation_derives_case_without_returning_original_text(
    runtime, monkeypatch, stage
):
    original = query(monkeypatch, stage)
    result = runtime.handle(
        "ecommerce_growth_analysis_advance",
        {"kind": "derive_structure_case", "query": original, "stage": stage},
        object(),
    )

    assert result["schemaVersion"] == "aos.analyst-structure-case/v1"
    assert result["stage"] == stage
    assert original not in json.dumps(result, ensure_ascii=False)
    assert set(result) == {"schemaVersion", "stage", "sourceRefs", "metricSources"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"kind": "other", "query": "{}", "stage": "portrait"},
        {"kind": "derive_structure_case", "query": "{}", "stage": "portrait", "orgId": "org-org"},
        {"kind": "derive_structure_case", "query": "", "stage": "portrait"},
        {"kind": "derive_structure_case", "query": {}, "stage": "portrait"},
        {"kind": "derive_structure_case", "query": "{}", "stage": "unknown"},
    ],
)
def test_unapproved_or_invalid_analysis_messages_never_execute(runtime, payload):
    if payload.get("kind") == "derive_structure_case" and set(payload) == {"kind", "query", "stage"}:
        with pytest.raises(ValueError, match="INVALID_GENERATION_CONTEXT"):
            runtime.handle("ecommerce_growth_analysis_advance", payload, object())
    else:
        with pytest.raises(PermissionError, match="registration-only"):
            runtime.handle("ecommerce_growth_analysis_advance", payload, object())


def test_other_registered_and_unknown_operations_remain_fail_closed(runtime):
    with pytest.raises(PermissionError, match="registration-only"):
        runtime.handle("ecommerce_growth_content_generate", {}, object())
    with pytest.raises(ValueError, match="unregistered"):
        runtime.handle("unknown", {}, object())
