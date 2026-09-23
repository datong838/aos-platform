#!/usr/bin/env python3
"""W5: register the DS successor directly from the exact detached DR authority.

Template chain: a0v_av_successor_business -> dq -> dr -> ds (this module).
Predecessor facts baked after the W5 DR retirement wave (2026-09-23):
  DR installation 89975129-... etag5 / binding rev9 epoch5 fenced-disabled
  (desired=disabled, observed=unknown) / 3 leases released /
  disable op 4528ffba-a300-4675-81b0-e0182a268cef succeeded with
  fence receipt 5b216beb + detach receipt 9b19f3f4 (hash sha256:68f32fd0...)
  / routes reset to legacy rev335 on cutover group 6a402d31 rev362.

DS successor (created by a0v_w5_ds_replacement_recovery):
  installation c6812824-a0c3-4adc-9ebc-d56178ae135c / generation b59582cc-...
  binding rev4 / epoch3 / enabled+ready (observed at 2026-09-23).
"""
from __future__ import annotations
import argparse
import json
import os

import a0v_dq_successor_business as dq_successor
import a0v_w5_ds_replacement_recovery as ds_recovery

successor = dq_successor.successor

successor.STATE = ds_recovery.replacement.STATE / "registration-ds"
successor.AV_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"
successor.AV_GENERATION = "b59582cc-2abf-472d-8f59-bfc8be1138c8"
successor.LOCK = "sha256:1b8468b86496b277a0ecd3a802379b3640e5ed1ec76e9ec420b9d15089013938"
successor.CONFIG = {"configurationId": "5423ebf3-4928-4950-b55c-ea2662f84bc8", "revision": 1,
                    "hash": "sha256:93d5b6bc55e565ff9f48e319a4402a775f7bdeec147e044e82fe89e0721649c5"}
successor.AU_ID = "89975129-7e0f-4860-ac56-7a031ebe4a1a"
successor.AU_GENERATION = "c78b2e2e-57ef-47ad-be07-9acf689e578c"
successor.DETACH = "9b19f3f4-fec0-4886-872e-023002c870fa"
successor.DETACH_HASH = "sha256:68f32fd03adaffb7cc14416bbb1e21d9d473b46d3e26993144045e84b5427957"
successor.KEY = "a0v-qyh-clean-generation-ds-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 335
successor.PREDECESSOR_GROUP_REVISION = 362
successor.replacement_module = lambda: ds_recovery.replacement

DS_ID = successor.AV_ID
DS_GENERATION = successor.AV_GENERATION
GROUP = successor.GROUP
ACTOR = successor.ACTOR
STATE = successor.STATE


def facts():
    """Extract DS successor binding facts for verification."""
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        binding = conn.execute("""SELECT generation::text, revision, execution_epoch,
            desired_state, observed_state, enabled, operation_fence
          FROM extension_runtime_binding
          WHERE org_id='org-org' AND project_id='dev-project'
          AND installation_id='c6812824-a0c3-4adc-9ebc-d56178ae135c'""").fetchall()
        lock = conn.execute("""SELECT r.lock_hash, i.etag_version
          FROM bundle_installation i JOIN bundle_installation_revision r
            ON r.installation_pk=i.installation_pk AND r.revision=i.current_revision
          WHERE i.org_id='org-org' AND i.project_id='dev-project'
          AND i.installation_id='c6812824-a0c3-4adc-9ebc-d56178ae135c'""").fetchall()
        gen = conn.execute("""SELECT generation::text FROM extension_runtime_binding
          WHERE org_id='org-org' AND project_id='dev-project'
          AND installation_id='c6812824-a0c3-4adc-9ebc-d56178ae135c'
          ORDER BY revision DESC LIMIT 1""").fetchall()
        return {"binding": [dict(r) for r in binding],
                "lock": [dict(r) for r in lock],
                "generation": [dict(r) for r in gen]}


def setup():
    return dq_successor.setup()


def run(mode: str) -> dict:
    plane = setup()
    if mode == "preview":
        request = successor.current_request()
        return {"outcome": "CURRENT_DS_SUCCESSOR_REQUEST_PREVIEW",
                "request": request.model_dump(mode="json", by_alias=True),
                "requestHash": request.request_hash()}
    result = successor.register(plane, successor.current_request())
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DS_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["facts", "preview", "register"])
    args = parser.parse_args()
    if args.mode == "facts":
        os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
        print(json.dumps(facts(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(run(args.mode), ensure_ascii=False, default=str, indent=2))
