#!/usr/bin/env python3
"""Create AZ from detached AX after exact retirement of failed leaf AY."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-az"
replacement.AV_DIR = replacement.STATE / "az"
replacement.AU_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
replacement.AU_GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
replacement.LOCK = "sha256:ae0c890abf2629daa136a615d9eadc4796e544f2e728ab4f567f0e7ebf65adc5"
replacement.AU_DISABLE_OPERATION = "8589a12c-aec2-4035-8937-f358dd1a8488"
replacement.AU_DETACH_RECEIPT = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"
replacement.AU_DETACH_HASH = "sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870"
replacement.PREFIX = "a0v-qyh-clean-az-20260919"
replacement.PREDECESSOR_ROUTE_REVISION = 125
replacement.PREDECESSOR_GROUP_REVISION = 152
replacement.DEFINITION_REVISION = 79
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "az"

AY_ID = "81df994f-23ce-4448-ac46-366aaee63924"
AY_RETIREMENT_RECEIPT = "48fc0e55-578d-46ae-b45a-bf8ab8085823"
AY_RETIREMENT_HASH = "sha256:21494a12aed250565b7f65cf4b8da0a36a5d9d9c8c9cbb433bd2346734df4409"
_detached_ax = replacement.detached_au


def detached_ax_after_retired_ay(profile):
    predecessor = _detached_ax(profile)
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        head = conn.execute("""SELECT i.etag_version,i.current_revision,r.state
          FROM bundle_installation i JOIN bundle_installation_revision r ON
          (r.org_id,r.project_id,r.installation_pk,r.revision)=
          (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
          (AY_ID,)).fetchone()
        receipt = conn.execute("""SELECT receipt_id::text,retirement_kind,authority_data,content_hash
          FROM extension_runtime_uninstall_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND installation_id=%s""", (AY_ID,)).fetchone()
    authority = None if receipt is None else receipt["authority_data"]
    if (head is None or dict(head) != {"etag_version": 6, "current_revision": 6, "state": "uninstalled"}
            or receipt is None or receipt["receipt_id"] != AY_RETIREMENT_RECEIPT
            or receipt["retirement_kind"] != "configured_unactivated"
            or receipt["content_hash"] != AY_RETIREMENT_HASH
            or authority.get("retirementKind") != "configured_unactivated"
            or authority.get("installationId") != AY_ID
            or authority.get("successfulEnableCount") != 0
            or authority.get("dispatchCount") != 0
            or authority.get("businessExecutionCount") != 0):
        raise ValueError("exact retired AY leaf required before AZ")
    return predecessor


replacement.detached_au = detached_ax_after_retired_ay


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "AZ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=replacement.ACTIONS)
    args = parser.parse_args()
    output = replacement.STATE / f"{args.action}-result.json"
    if output.exists():
        raise ValueError(f"immutable {args.action} output exists")
    result = run(args.action)
    replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
