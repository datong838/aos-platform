#!/usr/bin/env python3
"""Export deterministic AIP v1 contract and compatibility artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services" / "aos-api"
OUTPUT_ROOT = ROOT / "packages" / "contracts" / "aip"
CONTRACT_PATH = OUTPUT_ROOT / "v1.contract.json"
COMPATIBILITY_PATH = OUTPUT_ROOT / "v1.compatibility.json"


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def payloads() -> tuple[bytes, bytes]:
    sys.path.insert(0, str(API_ROOT))
    from aos_api.aip_compatibility import (
        LEGACY_STEP_RUN_STATUS,
        LEGACY_TASK_RUN_STATUS,
        ROUTE_COMPATIBILITY,
    )
    from aos_api.aip_contracts import (
        AIP_CONTRACT_MODELS,
        AIP_ERROR_STATUS,
        StepRunStatus,
        TaskRunStatus,
    )
    from aos_api.public_contracts import TaskStatus
    from aos_api.aip_research_job import RESEARCH_JOB_CONTRACT_MODELS

    schemas = {
        model.__name__: model.model_json_schema(by_alias=True)
        for model in (*AIP_CONTRACT_MODELS, *RESEARCH_JOB_CONTRACT_MODELS)
    }
    contract = {
        "authority": "aos_api.aip_contracts",
        "extensions": ["aos_api.aip_research_job"],
        "errors": AIP_ERROR_STATUS,
        "jsonFieldPolicy": "camelCase",
        "schemas": schemas,
        "states": {
            "stepRun": [item.value for item in StepRunStatus],
            "task": [item.value for item in TaskStatus],
            "taskRun": [item.value for item in TaskRunStatus],
        },
        "version": 1,
    }
    compatibility = {
        "legacyStepRunStatus": {
            key: value.value for key, value in LEGACY_STEP_RUN_STATUS.items()
        },
        "legacyTaskRunStatus": {
            key: value.value for key, value in LEGACY_TASK_RUN_STATUS.items()
        },
        "routes": [entry.__dict__ for entry in ROUTE_COMPATIBILITY],
        "version": 1,
    }
    return _json_bytes(contract), _json_bytes(compatibility)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    contract, compatibility = payloads()
    outputs = ((CONTRACT_PATH, contract), (COMPATIBILITY_PATH, compatibility))
    if args.check:
        drift = [str(path.relative_to(ROOT)) for path, data in outputs if not path.exists() or path.read_bytes() != data]
        if drift:
            print("DRIFT " + ", ".join(drift), file=sys.stderr)
            return 1
        print("PASS AIP v1 contract artifacts are current")
        return 0
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for path, data in outputs:
        path.write_bytes(data)
        print(f"WROTE {path.relative_to(ROOT)} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
