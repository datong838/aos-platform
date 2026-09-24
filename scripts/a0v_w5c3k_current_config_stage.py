#!/usr/bin/env python3
"""Stage one current four-source configuration for the live fenced successor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w4_dq_config_refresh as configuration
import a0v_w5c3j_third_natural_verify as verified

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3k-current-config-stage")
KEY = "a0v-w5c3k-current-four-source-stage-20260924-v1"
INSTALLATION = "407059df-6f1f-4927-acd7-8e388692838e"
GENERATION = "7571af17-e2bb-4437-9f04-75812bae56c0"


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _load(name):
    path = STATE / (name + ".json")
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C3K_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _counts():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        config = conn.execute("""SELECT count(*) AS n FROM extension_runtime_configuration
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND generation=%s""", (INSTALLATION, GENERATION)).fetchone()["n"]
        command = conn.execute("""SELECT count(*) AS n FROM extension_runtime_configuration
          WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""",
          (KEY,)).fetchone()["n"]
        attempts = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""",
          (INSTALLATION,)).fetchone()["n"]
        counts = conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_controlled_source_claim) AS claims,
          (SELECT count(*) FROM meta_schedule_run) AS runs""").fetchone()
    return {"configurations": config, "stageCommands": command,
            "attempts": attempts, "businessCounts": dict(counts)}


def preflight():
    live = verified.audit()
    if (live["installationId"] != INSTALLATION or live["generation"] != GENERATION
            or live["bindingRevision"] != 1 or live["executionEpoch"] != 1):
        raise ValueError("W5C3K_LIVE_BINDING_DRIFT")
    configuration._configure()
    document = configuration._document()
    if document.policyRef.revision != 13 or len(document.roleRefs) != 1 or len(document.dataRefs) != 1:
        raise ValueError("W5C3K_FOUR_SOURCE_DRIFT")
    counts = _counts()
    if counts["configurations"] or counts["stageCommands"] or counts["attempts"]:
        raise ValueError("W5C3K_STAGE_ALREADY_USED_OR_ATTEMPT")
    return {"outcome": "W5C3K_STAGE_PREFLIGHT_GREEN", "installationId": INSTALLATION,
            "generation": GENERATION, "hostPid": live["hostPid"],
            "bindingRevision": 1, "installationEtag": 5,
            "document": document.model_dump(mode="json"),
            "businessCounts": counts["businessCounts"]}


def stage():
    if STATE.exists():
        raise ValueError("W5C3K_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "idempotencyKey": KEY, "resend": False})
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument
    connect, activation, authorize, _service = configuration._service()
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn, org_id="org-org", project_id="dev-project")
            staged = append_configuration(conn, org_id="org-org", project_id="dev-project",
                installation_id=INSTALLATION, generation=GENERATION,
                expected_installation_etag=5, expected_binding_revision=1,
                actor=activation.ACTOR, idempotency_key=KEY,
                configuration=ConfigurationDocument.model_validate(before["document"]),
                authorize=authorize, previous_ref=None)
    result = {"outcome": "W5C3K_CONFIG_STAGED", "configRef": staged.model_dump(mode="json")}
    _write("result", result)
    return result


def audit():
    intent, result = _load("intent"), _load("result")
    live = verified.audit()
    counts = _counts()
    ref = result["configRef"]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT revision,content_hash,previous_hash,payload
          FROM extension_runtime_configuration WHERE org_id='org-org' AND project_id='dev-project'
          AND installation_id=%s AND generation=%s AND idempotency_key=%s""",
          (INSTALLATION, GENERATION, KEY)).fetchone()
    if (live["hostPid"] != intent["hostPid"]
            or counts != {"configurations": 1, "stageCommands": 1, "attempts": 0,
                          "businessCounts": intent["businessCounts"]}
            or row is None or row["revision"] != 1
            or row["content_hash"] != ref["hash"]
            or row["previous_hash"] is not None
            or row["payload"] != intent["document"]):
        raise ValueError("W5C3K_CONFIG_STAGE_AUDIT_NOT_GREEN")
    return {"outcome": "W5C3K_CURRENT_CONFIG_REV1_STAGED_GREEN",
            "installationId": INSTALLATION, "generation": GENERATION,
            "configRef": ref, "hostPid": live["hostPid"],
            "schedulesEnabled": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "stage", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
