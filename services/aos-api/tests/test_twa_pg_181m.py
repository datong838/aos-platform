"""181m — TWA store PG write-through + restart hydrate."""
from __future__ import annotations

import os

import pytest

from aos_api.db import init_schema
from aos_api import membership as mem
from aos_api import orgs as org_mod
from aos_api import person_identity as person
from aos_api import twa_pg
from aos_api import workspaces_catalog as ws_cat


@pytest.fixture()
def pg_twa(monkeypatch):
    monkeypatch.setenv("AOS_TWA_STORE", "pg")
    twa_pg.clear_mode_cache()
    try:
        init_schema()
    except Exception as exc:
        pytest.skip(f"PG unavailable: {exc}")
    # clean slate then seed via APIs
    mem.reset_membership_store()
    org_mod.reset_org_store()
    ws_cat.reset_workspace_catalog()
    person.reset_person_store()
    org_mod.seed_dev_orgs()
    ws_cat.seed_dev_workspaces()
    mem.seed_dev_defaults()
    yield
    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    twa_pg.clear_mode_cache()


def test_twa_pg_persists_org_and_hydrates(pg_twa):
    assert twa_pg.mode() == "pg"
    org_mod.create_org(name="持久化组织", org_id="org-persist-1", actor_id="alice")
    assert twa_pg.count_orgs() >= 1
    # simulate restart: wipe memory, hydrate from PG
    org_mod._ORGS.clear()
    ws_cat._WS.clear()
    mem._MEMBERS.clear()
    twa_pg.load_pg_to_memory()
    assert org_mod.get_org("org-persist-1") is not None
    assert org_mod.get_org("org-persist-1")["name"] == "持久化组织"


def test_twa_pg_person_roundtrip(pg_twa):
    person.upsert_person_profile(
        "email:persist@example.com",
        email="persist@example.com",
        display_name="持久人",
    )
    person._PERSONS.clear()
    twa_pg.load_pg_to_memory()
    prof = person.get_profile("email:persist@example.com")
    assert prof["email"] == "persist@example.com"
    assert prof["displayName"] == "持久人"
