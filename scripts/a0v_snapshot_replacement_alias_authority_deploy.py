#!/usr/bin/env python3
"""Back up and deploy only a0v088 to the isolated A0-V recovery database."""
from __future__ import annotations

import json

import a0v_snapshot_prior_recovery_anchor_deploy as deploy


deploy.STATE = deploy.ROOT.parent / ".aos-recovery-20260920/state/snapshot-replacement-alias-authority-deploy-v2"
deploy.SOURCE = "a0v_089"
deploy.TARGET = "a0v_090"
deploy.MIGRATION = deploy.ROOT / "services/aos-api/alembic/versions/a0v_090_snapshot_replacement_alias_authority.py"


def verify(conn):
    version = deploy.storage.version(conn)
    definition = conn.execute(
        "SELECT pg_get_functiondef('public.validate_snapshot_recovery_a0v_065()'::regprocedure) AS body"
    ).fetchone()["body"]
    markers = ("original.body->'policyRef'->>'resourceType'",
               "'mappingRef','schemaRef','maskingPolicyRef'",
               "(m.old_draft->'mappingRef')- 'revision'")
    if version != [deploy.TARGET] or any(marker not in definition for marker in markers):
        raise ValueError("a0v090 trigger readback differs")
    return {"version": version, "replacementAliasAuthorityBound": True}


deploy.verify = verify


if __name__ == "__main__":
    print(json.dumps(deploy.apply(), ensure_ascii=False, indent=2, default=str))
