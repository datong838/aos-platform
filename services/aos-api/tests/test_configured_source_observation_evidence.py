from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from aos_api.tenant_scope import TenantScope
from tests.test_source_configuration_revision import SCOPE, upsert
from tests.test_source_read_observation import observation

ROWS = [{"goods_id": 1}]


def bound(conn, source_id):
    upsert(conn, source_id, {"fixture": True})
    revision = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE).read_current(source_id)
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    item = observation().model_copy(update={"source_id": source_id,
        "read_started_at": now, "read_finished_at": now})
    return ConfiguredSourceObservation(observation=item.model_dump(), sourceConfigurationRef=revision.ref.model_dump())


def test_combination_exact_read_configuration_change_and_outer_rollback():
    source = "combined-" + uuid4().hex
    with connect(SCOPE) as conn:
        item = bound(conn, source)
        store = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE)
        ref = store.put(item, ROWS, actor="user:fixture")
        assert store.put(item, ROWS, actor="user:fixture") == ref
        restored = store.read_exact(ref)
        assert restored.observation == item
        assert restored.recorded_at >= item.observation.read_finished_at
        upsert(conn, source, {"fixture": "changed"})
        assert store.read_exact(ref) == restored
        payload = conn.execute("SELECT payload FROM public.aip_evidence WHERE evidence_id=%s", (ref.resource_id,)).fetchone()["payload"]
        assert payload["factIds"] == [] and "goods_id" not in str(payload)
        assert "fixture" not in str(payload).replace("user:fixture", "")
        conn.rollback()
    with connect(SCOPE) as conn:
        assert ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE).read_exact(ref) is None


def test_wrong_source_rejected_before_evidence_write():
    with connect(SCOPE) as conn:
        item = bound(conn, "combined-" + uuid4().hex)
        wrong = item.model_dump()
        wrong["observation"]["source_id"] = "different-source"
        with pytest.raises(ValueError, match="configuration"):
            ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE).put(
                ConfiguredSourceObservation.model_validate(wrong), ROWS, actor="user:fixture")
        conn.rollback()


def test_concurrent_dedup_canary_and_child_observation_revocation():
    with connect(SCOPE) as conn:
        item = bound(conn, "combined-" + uuid4().hex)
        conn.commit()

    def save(_):
        with connect(SCOPE) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            ref = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE).put(item, ROWS, actor="user:fixture")
            conn.commit()
            return ref
    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(save, range(2)))
    assert refs[0] == refs[1]
    ref = refs[0]
    canary = TenantScope("dev-org", "dev-project")
    with connect(canary) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert ConfiguredObservationEvidenceStore(HostTransaction(conn), canary).read_exact(ref) is None
    with connect(SCOPE) as conn:
        store = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE)
        child = store.read_exact(ref).observation_evidence_ref
        conn.execute("""INSERT INTO public.aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'fixture revoke','user:fixture')""",
            (*SCOPE.key, "revoke-" + uuid4().hex, child.resource_id, child.content_hash[7:]))
        with pytest.raises(ValueError, match="revoked"):
            store.read_exact(ref)
        with pytest.raises(ValueError, match="revoked"):
            store.put(item, ROWS, actor="user:fixture")
        conn.rollback()


def test_later_configuration_cannot_explain_earlier_observation():
    with connect(SCOPE) as conn:
        item = bound(conn, "combined-" + uuid4().hex)
        upsert(conn, item.observation.source_id, {"fixture": "later"})
        later = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE).read_current(item.observation.source_id)
        raw = item.model_dump()
        raw["source_configuration_ref"] = later.ref.model_dump()
        with pytest.raises(ValueError, match="configuration lineage"):
            ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE).put(
                ConfiguredSourceObservation.model_validate(raw), ROWS, actor="user:fixture")
        conn.rollback()


def test_temporary_tables_do_not_shadow_evidence_and_parent_revocation():
    with connect(SCOPE) as conn:
        item = bound(conn, "combined-" + uuid4().hex)
        conn.execute("CREATE TEMP TABLE aip_evidence (LIKE public.aip_evidence INCLUDING DEFAULTS)")
        conn.execute("CREATE TEMP TABLE aip_evidence_revoke_event (LIKE public.aip_evidence_revoke_event INCLUDING DEFAULTS)")
        store = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE)
        ref = store.put(item, ROWS, actor="user:fixture")
        assert store.read_exact(ref).observation == item
        assert conn.execute("SELECT count(*) AS n FROM pg_temp.aip_evidence").fetchone()["n"] == 0
        conn.execute("""INSERT INTO public.aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'fixture revoke','user:fixture')""",
            (*SCOPE.key, "revoke-" + uuid4().hex, ref.resource_id, ref.content_hash[7:]))
        with pytest.raises(ValueError, match="revoked"):
            store.read_exact(ref)
        with pytest.raises(ValueError, match="revoked"):
            store.put(item, ROWS, actor="user:fixture")
        conn.rollback()


@pytest.mark.parametrize("field,value", [("source_ref", "other"), ("subject_ref", {}),
    ("content_hash", "0" * 64), ("created_by", "user:other"), ("created_at", None), ("created_at", datetime(2020, 1, 1, tzinfo=UTC)),
    ("org_id", "dev-org"), ("payload", {}), ("boolean_alias", 0)])
def test_parent_split_column_drift_is_rejected(field, value):
    from tests.test_source_read_observation_evidence import Connection
    with connect(SCOPE) as conn:
        item = bound(conn, "combined-" + uuid4().hex)
        ref = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE).put(item, ROWS, actor="user:fixture")
        row = conn.execute("SELECT *,false AS revoked FROM public.aip_evidence WHERE evidence_id=%s", (ref.resource_id,)).fetchone()
        if field == "boolean_alias":
            row["payload"]["secretMaterialVersionKnown"] = value
        else:
            row[field] = value
        class Intercept:
            def execute(self, sql, params=()):
                if "FROM public.aip_evidence e" in sql and params[-1] == ref.resource_id:
                    return Connection(row)
                return conn.execute(sql, params)
        with pytest.raises(ValueError):
            ConfiguredObservationEvidenceStore(HostTransaction(Intercept()), SCOPE).read_exact(ref)
        conn.rollback()
