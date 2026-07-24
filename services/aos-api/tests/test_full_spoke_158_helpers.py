"""158 · Full Spoke helpers (no PG)."""

from __future__ import annotations

from aos_api.apollo_catalog import (
    full_spoke_mode,
    full_spoke_mock_ready,
    full_spoke_plan_artifact,
)


def test_full_spoke_mode_default_mock(monkeypatch):
    monkeypatch.delenv("AOS_FULL_SPOKE_MODE", raising=False)
    assert full_spoke_mode() == "mock"
    assert full_spoke_mock_ready() is True


def test_full_spoke_mode_off(monkeypatch):
    monkeypatch.setenv("AOS_FULL_SPOKE_MODE", "off")
    assert full_spoke_mode() == "off"
    assert full_spoke_mock_ready() is False


def test_full_spoke_plan_artifact_shape(monkeypatch):
    monkeypatch.setenv("AOS_FULL_SPOKE_MODE", "mock")
    art = full_spoke_plan_artifact()
    assert art["chart"] == "aos-spoke-full"
    assert art["k8sDeferred"] is True
    assert art["mockReady"] is True
    assert art["path"].endswith("deploy/spoke-full/chart")
