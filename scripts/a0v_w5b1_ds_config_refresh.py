#!/usr/bin/env python3
"""DS-only successor configuration on the original Configuration Owner path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a0v_w4_dq_config_refresh as profile
import a0v_w5b_ds_settlement as settled
from a0v_formal_text_model_renewal import database_connect

STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5b1-ds-config")
INSTALLATION = settled.DS_ID
GENERATION = settled.GENERATION
SOURCE_CONFIG = {"configurationId": "5423ebf3-4928-4950-b55c-ea2662f84bc8",
                 "revision": 1,
                 "hash": "sha256:93d5b6bc55e565ff9f48e319a4402a775f7bdeec147e044e82fe89e0721649c5"}
KEY = "a0v-w5b1-ds-config-refresh-20260924-v1"


def _profile():
    profile.STATE = STATE
    profile.INSTALLATION = INSTALLATION
    profile.GENERATION = GENERATION
    profile.SOURCE_CONFIG = SOURCE_CONFIG
    profile.KEY = KEY
    return profile


def _command_count(suffix):
    with database_connect("aos_meta_head")() as conn:
        return conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""",
          (KEY + suffix,)).fetchone()["n"]


def _stage_count():
    with database_connect("aos_meta_head")() as conn:
        return conn.execute("""SELECT count(*) AS n FROM extension_runtime_configuration
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
            AND generation=%s AND idempotency_key=%s""",
          (INSTALLATION, GENERATION, KEY + "-stage-v1")).fetchone()["n"]


def preflight():
    p = _profile()
    ds = settled.snapshot()
    binding = ds["installation"]["bindings"]
    if (ds["installation"]["head"]["state"] != "active"
            or ds["installation"]["head"]["etag_version"] != 5
            or len(binding) != 1 or binding[0]["revision"] != 9
            or binding[0]["execution_epoch"] != 5
            or binding[0]["desired_state"] != "disabled"
            or binding[0]["enabled"] is not False
            or binding[0]["operation_fence"] is not True
            or binding[0]["config_ref"] != SOURCE_CONFIG
            or ds["schedules"] != {"total": 12, "enabled": 0}
            or ds["activeAttempts"] != 0 or ds["canaryBindings"] != 0
            or ds["oldDefinition"] is None or ds["oldDefinition"]["state"] != "disabled"
            or ds["newDefinition"] is not None):
        raise ValueError("W5B1_DS_BASELINE_DRIFT")
    inspect = p.inspect()
    policy = p._document().policyRef
    if (inspect["configHeadRevision"] != 1 or policy.revision != 13
            or _stage_count() != 0
            or _command_count("-configure-v1") != 0
            or _command_count("-enable-v1") != 0):
        raise ValueError("W5B1_CONFIGURATION_AUTHORITY_DRIFT")
    return {"outcome": "W5B1_PREFLIGHT_GREEN", "installationEtag": 5,
            "bindingRevision": 9, "executionEpoch": 5,
            "configurationRevision": 1, "policyRevision": policy.revision,
            "activeAttempts": 0, "schedulesEnabled": 0}


def stage():
    if STATE.exists():
        raise ValueError("W5B1_EXISTING_STATE_RECONCILE_FIRST")
    preflight()
    result = _profile().stage()
    staged = result["staged"]["configRef"]
    if (staged["configurationId"] != SOURCE_CONFIG["configurationId"]
            or staged["revision"] != 2):
        raise ValueError("W5B1_CONFIG_SUCCESSOR_DRIFT")
    return {"outcome": "W5B1_DS_CONFIG_REV2_STAGED", "configRef": staged}


def configure():
    p = _profile()
    if not (STATE / "stage.json").is_file() or (STATE / "configure.json").exists():
        raise ValueError("W5B1_CONFIGURE_BOUNDARY_INVALID")
    if _command_count("-configure-v1") != 0:
        raise ValueError("W5B1_CONFIGURE_RECEIPT_EXISTS_RECONCILE_FIRST")
    result = p.configure()
    return {"outcome": "W5B1_DS_CONFIGURE_ACCEPTED", "receipt": result["receipt"]}


def enable():
    p = _profile()
    if not (STATE / "configure.json").is_file() or (STATE / "enable.json").exists():
        raise ValueError("W5B1_ENABLE_BOUNDARY_INVALID")
    if _command_count("-enable-v1") != 0:
        raise ValueError("W5B1_ENABLE_RECEIPT_EXISTS_RECONCILE_FIRST")
    ds = settled.snapshot()
    binding = ds["installation"]["bindings"]
    staged = json.loads((STATE / "stage.json").read_text())["configRef"]
    if (len(binding) != 1 or binding[0]["desired_state"] != "disabled"
            or binding[0]["operation_fence"] is not True
            or binding[0]["enabled"] is not False
            or binding[0]["config_ref"] != staged
            or ds["activeAttempts"] != 0
            or ds["schedules"] != {"total": 12, "enabled": 0}
            or ds["oldDefinition"] is None or ds["oldDefinition"]["state"] != "disabled"):
        raise ValueError("W5B1_CONFIGURED_DISABLED_GATE_NOT_GREEN")
    result = p.enable()
    return {"outcome": "W5B1_DS_ENABLE_ACCEPTED", "receipt": result["receipt"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "stage", "configure", "enable"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
