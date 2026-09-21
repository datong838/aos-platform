#!/usr/bin/env python3
"""Refresh CQ's expired governance configuration without starting business work."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import a0v_cq_replacement_recovery as cq_replacement
import a0v_ecommerce_runtime_host as runtime_host
from a0v_formal_text_model_renewal import database_connect
from a0v_qyh_current_product_event_first_chain import freeze


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/cq-configuration-refresh"
INSTALLATION = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"
GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"
SOURCE_CONFIG = {
    "configurationId": "85103076-e401-4624-8141-4dc8374db731", "revision": 1,
    "hash": "sha256:f63e3f688081dac051643213f06ab62d0193c60f8e14859f2a510897c891511c",
}
BUNDLE_ROOT = cq_replacement.replacement.BUNDLE_ROOT
TRUST_STATE = cq_replacement.canonical.TRUST_STATE
CREDENTIALS = cq_replacement.canonical.CREDENTIALS
KEY_PREFIX = "a0v-current-ecommerce-cq-refresh-20260921"
COMMAND_PREFIX = "current-ecommerce-cq-refresh-20260921"


def load_profile():
    path = ROOT / "scripts/a0v_ecommerce_1_7_configure.py"
    spec = importlib.util.spec_from_file_location("cq_configuration_successor_base", path)
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.TRUST_STATE = TRUST_STATE
    runtime_host.DEFAULT_CREDENTIALS = CREDENTIALS
    original_load = profile.load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = CREDENTIALS
        return module

    profile.load = load

    def target(recovery=False, *, sleep_recovery=False, niushop_1_4=False):
        if any((recovery, sleep_recovery, niushop_1_4)):
            raise ValueError("only exact current CQ configuration successor allowed")
        return (INSTALLATION, STATE / "configuration-successor.json", KEY_PREFIX, COMMAND_PREFIX)

    profile.configuration_target = target
    return profile


def audit(expected_phase: str) -> dict:
    with database_connect("aos_meta_head")() as conn:
        binding = dict(conn.execute("""SELECT generation,revision,execution_epoch,desired_state,
          observed_state,enabled,operation_fence,config_ref FROM extension_runtime_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""",
          (INSTALLATION,)).fetchone())
        routes = conn.execute("""SELECT count(*) n FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
            AND generation=%s AND execution_epoch=3 AND revision=252
            AND cutover_group_revision=279 AND operation_fence=false""",
          (INSTALLATION, GENERATION)).fetchone()["n"]
        attempts = conn.execute("""SELECT count(*) n FROM extension_runtime_execution_attempt
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""",
          (INSTALLATION,)).fetchone()["n"]
        in_flight = conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') +
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) n""").fetchone()["n"]
        canary = conn.execute("""SELECT count(*) n FROM bundle_installation
          WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
    if (str(binding["generation"]) != GENERATION or routes != 9 or attempts or in_flight or canary):
        raise RuntimeError("exact zero-effect CQ refresh boundary required")
    if expected_phase == "source":
        expected = {"revision": 6, "execution_epoch": 3, "desired_state": "enabled",
            "observed_state": "ready", "enabled": True, "operation_fence": False,
            "config_ref": SOURCE_CONFIG}
    elif expected_phase == "configured":
        expected = {"revision": 8, "execution_epoch": 4, "desired_state": "disabled",
            "observed_state": "unknown", "enabled": False, "operation_fence": True}
    elif expected_phase == "enabled":
        expected = {"revision": 9, "execution_epoch": 5, "desired_state": "enabled",
            "observed_state": "ready", "enabled": True, "operation_fence": False}
    else:
        raise ValueError("unknown audit phase")
    if any(binding[key] != value for key, value in expected.items()):
        raise RuntimeError(f"CQ {expected_phase} binding differs")
    if expected_phase != "source":
        ref = binding["config_ref"]
        if (not ref or ref["configurationId"] != SOURCE_CONFIG["configurationId"]
                or ref["revision"] != 2):
            raise RuntimeError("CQ successor configuration differs")
    return {"binding": binding, "routes": routes, "attempts": attempts,
        "inFlight": in_flight, "canary": canary}


def stage() -> dict:
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.tenant_scope import TenantScope

    baseline = audit("source")
    profile = load_profile()
    preview = profile.run("preflight")
    document = ConfigurationDocument.model_validate_json(json.dumps(preview["configuration"]))
    connect, activation, authorize, _service = profile.setup()
    scope = TenantScope("org-org", "dev-project")
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
            staged = append_configuration(conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=INSTALLATION, generation=GENERATION, expected_installation_etag=5,
                expected_binding_revision=6, actor=activation.ACTOR,
                idempotency_key=f"{KEY_PREFIX}-config-stage-v1",
                configuration=document, authorize=authorize, previous_ref=SOURCE_CONFIG)
    if staged.configurationId != SOURCE_CONFIG["configurationId"] or staged.revision != 2:
        raise RuntimeError("same-family CQ configuration successor required")
    frozen = {"installationEtag": 5, "bindingRevision": 6, "generation": GENERATION,
        "configuration": document.model_dump(mode="json"), "configRef": staged.model_dump(mode="json")}
    freeze(STATE / "configuration-successor.json", frozen)
    return {"outcome": "CQ_CONFIGURATION_SUCCESSOR_STAGED", "baseline": baseline, "staged": frozen}


def run(action: str) -> dict:
    if action == "preflight":
        return {"outcome": "CQ_CONFIGURATION_REFRESH_PREFLIGHT_GREEN", **audit("source")}
    result_path = STATE / f"{action}-result.json"
    if result_path.exists():
        raise RuntimeError("immutable CQ configuration refresh result exists")
    if action == "stage":
        result = stage()
    elif action == "configure":
        audit("source")
        result = {"outcome": "CQ_CONFIGURATION_SUCCESSOR_CONFIGURE_ACCEPTED",
            "request": load_profile().run("configure")}
    elif action == "enable":
        audit("configured")
        result = {"outcome": "CQ_CONFIGURATION_SUCCESSOR_ENABLE_ACCEPTED",
            "request": load_profile().run("enable")}
    elif action == "observe":
        return {"outcome": "CQ_CONFIGURATION_SUCCESSOR_READY", **audit("enabled")}
    else:
        raise ValueError("unknown action")
    freeze(result_path, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "stage", "configure", "enable", "observe"))
    print(json.dumps(run(parser.parse_args().action), ensure_ascii=False, default=str, indent=2))
