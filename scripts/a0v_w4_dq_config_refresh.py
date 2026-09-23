#!/usr/bin/env python3
"""W4 executor: refresh DQ configuration chain to governance rev12, then rebuild
snapshot definition (269) with fresh bindings and enable it.

Phases (idempotent by frozen state files):
  stage     - append configuration revision 2 for DQ installation (policyRef rev12)
  configure - binding configure (desired_state disabled, epoch+1, fence on)
  enable    - binding enable (desired_state enabled, ready, fence off)
  inspect   - read-only binding/config facts
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-config-refresh"
INSTALLATION = "d2d3c478-f9d9-4489-92b7-1de57f546452"
GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
SOURCE_CONFIG = {"configurationId": "5f9ceec4-8532-44be-bb07-13617e195f70", "revision": 1,
                 "hash": "sha256:ffef5daa927083eddc12d3f5848efb7c2a818bb1b631905a61e0ef913b18ceab"}
KEY = "a0v-w4-dq-config-refresh-20260923"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"


def _configure():
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(BASE / "bm-runtime-credentials/runtime-host-identities.json"),
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_BUNDLE_ROOT": str(BASE / "bn-canonical-alias-registry/signed-bundles"),
        "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(BASE / "bn-registration-credentials/registration-main-identity.json"),
    })
    sys.path.insert(0, str(ROOT / "services/aos-api"))


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(name):
    path = STATE / f"{name}.json"
    if not path.is_file():
        raise RuntimeError(f"frozen {name} required (run earlier phases first)")
    return json.loads(path.read_text(encoding="utf-8"))


def _database():
    from a0v_formal_text_model_renewal import database_connect
    return database_connect("aos_meta_head")


def _document():
    """Build the refreshed ConfigurationDocument (policyRef -> current head rev12)."""
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument, ConfigurationSourceRef
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope("org-org", "dev-project")
    metadata = _database()
    models = AipModelRuntimeStore(metadata)
    policy = models.get_policy(scope, "a0v-ecommerce-runtime-policy-v1")
    budget_policy = AipModelGovernancePolicyStore(metadata).get_budget(
        scope, policy.budget_policy_ref.asset_id, policy.budget_policy_ref.revision)
    with metadata(scope) as conn:
        plans = conn.execute(
            "SELECT r.plan_id,r.revision,r.content_hash FROM aip_responsibility_plan_head h "
            "JOIN aip_responsibility_plan_revision r USING(org_id,project_id,plan_id) "
            "WHERE h.org_id=%s AND h.project_id=%s AND r.revision=h.current_revision "
            "AND r.profile='ecommerce.business-investigation.readonly' AND r.lifecycle='frozen'",
            scope.key).fetchall()
    if len(plans) != 1:
        raise RuntimeError("EXACT_FROZEN_INVESTIGATION_PLAN_REQUIRED")
    plan = plans[0]
    def ref(authority, id, revision, hash):
        return ConfigurationSourceRef(authority=authority, id=id, revision=revision,
                                      hash=hash if hash.startswith("sha256:") else "sha256:" + hash)
    document = ConfigurationDocument(
        roleRefs=(ref("aip.responsibility_plan_revision", plan["plan_id"], plan["revision"], plan["content_hash"]),),
        dataRefs=(ref("aip.data_classification_policy_revision", policy.data_classification_policy_ref.asset_id,
                      policy.data_classification_policy_ref.revision, policy.data_classification_policy_ref.content_hash),),
        budgetRef=ref("aip.budget_revision", budget_policy.budget_revision_ref.asset_id,
                      budget_policy.budget_revision_ref.revision, budget_policy.budget_revision_ref.content_hash),
        policyRef=ref("aip.runtime_policy_revision", policy.policy_id, policy.revision, policy.content_hash))
    return document


def inspect():
    _configure()
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn:
        binding = dict(conn.execute(
            "SELECT revision,execution_epoch,desired_state,observed_state,enabled,operation_fence,config_ref "
            "FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s",
            ("org-org", "dev-project", INSTALLATION)).fetchone())
        etag = conn.execute(
            "SELECT etag_version FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s",
            ("org-org", "dev-project", INSTALLATION)).fetchone()["etag_version"]
        config = conn.execute(
            "SELECT revision FROM extension_runtime_configuration WHERE org_id=%s AND project_id=%s "
            "AND configuration_id=%s ORDER BY revision DESC LIMIT 1",
            ("org-org", "dev-project", SOURCE_CONFIG["configurationId"])).fetchone()
    return {"outcome": "W4_DQ_INSPECT", "binding": binding, "installationEtag": etag,
            "configHeadRevision": config["revision"] if config else None}


def stage():
    _configure()
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.tenant_scope import TenantScope
    facts = inspect()
    if facts["binding"]["config_ref"]["revision"] != SOURCE_CONFIG["revision"] or facts["configHeadRevision"] != SOURCE_CONFIG["revision"]:
        raise RuntimeError("exact source configuration rev1 required")
    document = _document()
    if document.policyRef.revision < 12:
        raise RuntimeError("refreshed policy head below rev12")
    scope = TenantScope("org-org", "dev-project")
    connect, activation, authorize, _svc = _service()
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
            staged = append_configuration(conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=INSTALLATION, generation=GENERATION,
                expected_installation_etag=facts["installationEtag"],
                expected_binding_revision=facts["binding"]["revision"],
                actor=ACTOR, idempotency_key=f"{KEY}-stage-v1",
                configuration=document, authorize=authorize, previous_ref=SOURCE_CONFIG)
    if staged.configurationId != SOURCE_CONFIG["configurationId"] or staged.revision != 2:
        raise RuntimeError("same-family config successor rev2 required")
    frozen = {"installationEtag": facts["installationEtag"], "bindingRevision": facts["binding"]["revision"],
              "generation": GENERATION, "configuration": document.model_dump(mode="json"),
              "configRef": staged.model_dump(mode="json")}
    _write("stage", frozen)
    return {"outcome": "W4_DQ_CONFIG_REV2_STAGED", "staged": frozen, "inspect": facts}


def _service():
    """Profile setup with DQ-canonical credentials/bundle paths patched in.

    profile.load() re-imports fresh module instances, so patches must be
    applied inside the load wrapper (same technique as the CQ refresh wave).
    """
    import a0v_ecommerce_1_7_configure as profile
    profile.BUNDLE_ROOT = BASE / "bn-canonical-alias-registry/signed-bundles"
    profile.TRUST_STATE = BASE / "bm-trust-root-rotation"
    original_load = profile.load

    def load(name):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = BASE / "bm-runtime-credentials/runtime-host-identities.json"
        return module

    profile.load = load
    return profile.setup()


def configure():
    _configure()
    frozen = _load("stage")
    from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
    connect, activation, authorize, service = _service()
    receipt = service.request(installation_id=INSTALLATION, kind="configure",
        org_id="org-org", project_id="dev-project", actor=ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=f"{KEY}-configure-v1", if_match='"' + str(frozen["installationEtag"]) + '"',
        target=ConfigureTarget(generation=frozen["generation"], bindingRevision=frozen["bindingRevision"],
                               configRef=frozen["configRef"]))
    _write("configure", {"outcome": "W4_DQ_CONFIG_CONFIGURED", "receipt": receipt.response_json})
    return {"outcome": "W4_DQ_CONFIG_CONFIGURED", "receipt": receipt.response_json}


def enable():
    _configure()
    frozen = _load("stage")
    configure_receipt = _load("configure")
    from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
    connect, activation, authorize, service = _service()
    facts = inspect()
    if facts["binding"]["desired_state"] != "disabled" or facts["binding"]["operation_fence"] is not True:
        raise RuntimeError("configured (fenced disabled) binding required before enable")
    # etag advanced by configure; re-read fresh etag for enable if_match
    etag = facts["installationEtag"]
    receipt = service.request(installation_id=INSTALLATION, kind="enable",
        org_id="org-org", project_id="dev-project", actor=ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=f"{KEY}-enable-v1", if_match='"' + str(etag) + '"',
        target=ConfigureTarget(generation=frozen["generation"], bindingRevision=facts["binding"]["revision"],
                               configRef=frozen["configRef"]))
    _write("enable", {"outcome": "W4_DQ_CONFIG_ENABLED", "receipt": receipt.response_json})
    return {"outcome": "W4_DQ_CONFIG_ENABLED", "receipt": receipt.response_json}


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("inspect", "stage", "configure", "enable"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
