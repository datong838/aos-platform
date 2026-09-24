#!/usr/bin/env python3
"""Read the official third-successor definition options without a write."""

from __future__ import annotations

import json
import os
from pathlib import Path

import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3o_uninstalled_ds_register as registered
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c4f_successor_bindings as bindings

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c4g-definition-options")


def _write(value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / "options.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def read():
    if STATE.exists():
        raise ValueError("W5C4G_OPTIONS_ALREADY_READ_INSPECT_PRIVATE_RESULT")
    if bindings.audit()["outcome"] != "W5C4F_TWELVE_BINDINGS_GREEN":
        raise ValueError("W5C4G_BINDING_DRIFT")
    from aos_api.tenant_scope import TenantScope
    service = prepared._plane().pipeline_control_factory.build_snapshot_schedule(
        TenantScope("org-org", "dev-project"), source_controls=True)
    result = service.options(actor=prepared.ACTOR,
        installation_id=registered.INSTALLATION, generation=registered.GENERATION)
    expected = {item["scheduleId"]: item for item in bindings._load("wave-result")["members"]}
    observed = {item["scheduleId"]: item for item in result.get("members", [])}
    if (result.get("status") != "ready" or len(expected) != 12 or len(observed) != 12
            or len(result.get("policies", [])) == 0
            or result.get("missing") or result.get("ambiguous")
            or result.get("installationId") != registered.INSTALLATION
            or result.get("generation") != registered.GENERATION):
        _write({"accepted": False, "options": result})
        raise ValueError("W5C4G_OFFICIAL_OPTIONS_NOT_READY")
    for schedule_id, item in observed.items():
        match = expected.get(schedule_id)
        if (match is None or item["pipelineId"] != match["pipelineId"]
                or item["bindingRef"] != match["ref"]
                or item["definitionId"] is not None):
            _write({"accepted": False, "options": result})
            raise ValueError("W5C4G_OFFICIAL_MEMBER_MISMATCH")
    runtime = enabled.observe()
    if runtime["counts"]["business"] != bindings._load("wave-intent")["businessCounts"]:
        _write({"accepted": False, "options": result})
        raise ValueError("W5C4G_BUSINESS_DRIFT")
    _write({"accepted": True, "options": result,
            "businessCounts": runtime["counts"]["business"],
            "hostPid": runtime["host"]["pid"]})
    return {"outcome": "W5C4G_OFFICIAL_OPTIONS_READY", "members": 12,
            "policies": len(result["policies"]), "policyRefs": result["policies"],
            "hostPid": runtime["host"]["pid"], "businessCounts": runtime["counts"]["business"]}


if __name__ == "__main__":
    print(json.dumps(read(), ensure_ascii=False, default=str))
