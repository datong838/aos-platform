from __future__ import annotations

from aos_api.tenant_backfill_executor import authz_content_hash
from aos_api.tenant_dual_write import stable_key_hash


def test_authz_content_hash_matches_e3_snapshot_contract() -> None:
    row = {
        "user_key": "user:restore-drill",
        "relation": "viewer",
        "object_key": "object:restore-drill",
    }

    assert authz_content_hash(row) == stable_key_hash(
        "authz_tuple",
        "user:restore-drill",
        "viewer",
        "object:restore-drill",
        "",
        "",
    )
    assert authz_content_hash(row, "dev-org", "dev-project") == stable_key_hash(
        "authz_tuple",
        "user:restore-drill",
        "viewer",
        "object:restore-drill",
        "dev-org",
        "dev-project",
    )
