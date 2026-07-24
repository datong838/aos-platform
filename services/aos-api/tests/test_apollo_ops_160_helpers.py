"""160 · Apollo ops deepening (in-memory KV via monkeypatch · no PG)."""

from __future__ import annotations

import pytest

from aos_api import apollo_ops
from aos_api.errors import ApiError

_STORE: dict[str, dict] = {}


@pytest.fixture(autouse=True)
def _mem_kv(monkeypatch):
    _STORE.clear()

    def get_payload(key: str):
        return _STORE.get(key)

    def put_payload(key: str, payload: dict):
        _STORE[key] = dict(payload)
        return payload

    monkeypatch.setattr(apollo_ops, "get_payload", get_payload)
    monkeypatch.setattr(apollo_ops, "put_payload", put_payload)
    yield
    _STORE.clear()


def test_change_approve_audit():
    row = apollo_ops.create_change(
        title="cutover",
        kind="channel",
        channelId="staging",
        subject="alice",
        org_id="dev-org",
        project_id="dev-project",
    )
    assert row["status"] == "pending"
    assert row["scheme"] == "160"
    decided = apollo_ops.decide_change(row["id"], approve=True, subject="bob", note="lgtm")
    assert decided["status"] == "approved"
    assert decided["decidedBy"] == "bob"
    assert any(c["id"] == row["id"] for c in apollo_ops.list_changes())


def test_hotfix_merge_stable():
    row = apollo_ops.create_change(
        title="urgent",
        kind="hotfix",
        subject="alice",
        org_id="dev-org",
        project_id="dev-project",
    )
    assert row["emergency"] is True
    assert row["channelId"] == "hotfix"
    apollo_ops.decide_change(row["id"], approve=True, subject="bob")
    merged = apollo_ops.merge_hotfix_to_stable(row["id"], subject="carol")
    assert merged["status"] == "merged"
    assert merged["mergedToStableAt"]


def test_asset_gate_blocks_target():
    apollo_ops.register_asset(
        contents=["WorkOrder"],
        hotfix=False,
        compatible_channels=["dev"],
        subject="alice",
    )
    with pytest.raises(ApiError) as ei:
        apollo_ops.assert_promote_assets_ok("staging")
    assert ei.value.code == "CHANNEL_PROMOTE_ASSET"
