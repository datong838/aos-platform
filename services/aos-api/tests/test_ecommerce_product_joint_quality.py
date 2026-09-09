from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.db import connect, connect_serializable
from aos_api.ecommerce_business_investigation_case_selection import PostgresCanonicalShopSelectionSource
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_joint_quality import ProductJointQualityReader
from aos_api.source_read_observation import observed_rows_hash
from aos_api.tenant_scope import TenantScope
from tests.test_configured_source_observation_evidence import bound, SCOPE
from tests.test_ecommerce_product_observation_comparison import setup


STAMP = int(datetime(2026, 9, 1, tzinfo=UTC).timestamp())


def row(identity=1, **changes):
    value = dict(goods_id=identity, site_id=1, goods_name="商品", category_id="1",
        goods_state=1, is_delete=0, price="12.00", goods_stock=3,
        create_time=STAMP, modify_time=STAMP)
    value.update(changes)
    return value


def inputs(conn, rows, *, spec="niushop.product-quality-observation/v1"):
    raw = bound(conn, "joint-" + uuid4().hex).model_dump()
    raw["observation"].update(spec_id=spec, cleaning_version=("niushop.product-quality-fields/v1"
        if spec == "niushop.product-quality-observation/v1" else "niushop.product-public-fields/v1"),
        rows_hash=observed_rows_hash(rows), fetched_count=len(rows), excluded_count=0, retained_count=len(rows))
    tx = HostTransaction(conn)
    evidence = ConfiguredObservationEvidenceStore(tx, SCOPE).put(
        ConfiguredSourceObservation.model_validate(raw), rows, actor="user:fixture")
    selected = PostgresCanonicalShopSelectionSource(TransactionBoundConnectFactory(tx, SCOPE)).read(SCOPE)
    return dict(evidence_ref=evidence, rows=rows, channel_ref=selected.channel_ref,
        entity_ref=selected.business_entity_ref, binding_ref=selected.entity_channel_binding_ref)


def test_same_marginal_counts_cannot_determine_joint_validity():
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        reader = ProductJointQualityReader(HostTransaction(conn), SCOPE)
        separate = reader.read(**inputs(conn, [row(1, goods_name=""), row(2, price=-1)]))
        together = reader.read(**inputs(conn, [row(1, goods_name="", price=-1), row(2)]))
        assert separate.field_valid_counts == together.field_valid_counts
        assert separate.joint_valid_count == 0 and together.joint_valid_count == 1
        assert separate.eligible_count == together.eligible_count == 2
        assert separate.distinct_population_count == 2
        assert separate.rule_version == together.rule_version
        assert not hasattr(separate, "satisfied")
        with pytest.raises(FrozenInstanceError): separate.joint_valid_count = 2
        conn.rollback()


def test_filter_before_duplicate_quarantine_preserves_bad_denominator_and_order():
    rows = [row(1), row(1, is_delete=1), row(2), row(2, price=-1),
            row(None), row(3, goods_state=0), row(4, goods_state=True), row(5)]
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        reader = ProductJointQualityReader(HostTransaction(conn), SCOPE)
        result = reader.read(**inputs(conn, rows))
        reverse = reader.read(**inputs(conn, list(reversed(rows))))
        assert (result.observed_count, result.excluded_count, result.duplicate_count, result.eligible_count) == (8, 2, 2, 4)
        assert result.observed_count == result.excluded_count + result.duplicate_count + result.eligible_count
        assert result.joint_valid_count == 2 and result.distinct_population_count == 3
        for field in ("observed_count", "excluded_count", "duplicate_count", "eligible_count", "joint_valid_count", "field_valid_counts"):
            assert getattr(result, field) == getattr(reverse, field)
        conn.rollback()


@pytest.mark.parametrize("changes,field", [({"goods_id": True}, "identity"),
    ({"goods_name": " "}, "title"), ({"category_id": None}, "category"), ({"category_id": "0"}, "category"),
    ({"is_delete": True}, "availability"), ({"goods_state": None}, "availability"),
    ({"price": True}, "price"), ({"price": -1}, "price"), ({"goods_stock": "2.5"}, "stock"),
    ({"create_time": 0}, "createdAt"), ({"create_time": True}, "createdAt"),
    ({"modify_time": STAMP - 1}, "updatedAt"), ({"modify_time": 99_999_999_999}, "updatedAt")])
def test_invalid_values_remain_eligible_without_defaults(changes, field):
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        result = ProductJointQualityReader(HostTransaction(conn), SCOPE).read(**inputs(conn, [row(**changes)]))
        assert result.eligible_count == 1 and result.joint_valid_count == 0
        assert dict(result.field_valid_counts)[field] == 0
        conn.rollback()


def test_empty_population_is_zero_measurement_not_quality_pass():
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        result = ProductJointQualityReader(HostTransaction(conn), SCOPE).read(**inputs(conn, []))
        assert result.observed_count == result.distinct_population_count == result.joint_valid_count == 0
        assert all(value == 0 for _, value in result.field_valid_counts)
        conn.rollback()


def test_wrong_spec_scope_selection_rows_and_revocation_rejected():
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        reader = ProductJointQualityReader(HostTransaction(conn), SCOPE)
        kwargs = inputs(conn, [row()])
        with pytest.raises(ValueError, match="rows"):
            reader.read(**{**kwargs, "rows": [row(price=99)]})
        altered = deepcopy(kwargs)
        altered["binding_ref"].content_hash = "sha256:" + "f" * 64
        with pytest.raises(ValueError, match="selection"): reader.read(**altered)
        with pytest.raises(ValueError, match="specification"):
            reader.read(**inputs(conn, [row()], spec="niushop.product-observation/v1"))
        with pytest.raises(ValueError, match="site"):
            reader.read(**inputs(conn, [row(site_id=2)]))
        with pytest.raises(ValueError, match="unavailable"):
            ProductJointQualityReader(HostTransaction(conn), TenantScope("dev-org", "dev-project")).read(**kwargs)
        evidence = kwargs["evidence_ref"]
        conn.execute("""INSERT INTO public.aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'fixture revoke','user:fixture')""",
            (*SCOPE.key, "revoke-"+uuid4().hex, evidence.resource_id, evidence.content_hash[7:]))
        with pytest.raises(ValueError, match="revoked"): reader.read(**kwargs)
        conn.rollback()


def test_reader_rejects_unstable_snapshot_and_only_reads(monkeypatch):
    with connect(SCOPE) as conn:
        with pytest.raises(ValueError, match="snapshot"):
            ProductJointQualityReader(HostTransaction(conn), SCOPE).read(
                evidence_ref=None, rows=[],
                channel_ref=InvestigationExactRef(resource_type="ChannelRevision", resource_id="x", revision=1, content_hash="sha256:"+"a"*64),
                entity_ref=InvestigationExactRef(resource_type="BusinessEntityRevision", resource_id="x", revision=1, content_hash="sha256:"+"a"*64),
                binding_ref=InvestigationExactRef(resource_type="BusinessEntityChannelBindingRevision", resource_id="x", revision=1, content_hash="sha256:"+"a"*64))
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        kwargs = inputs(conn, [row()])
        calls = []
        original = HostTransaction.execute
        def execute(self, sql, params=()):
            calls.append(sql)
            return original(self, sql, params)
        monkeypatch.setattr(HostTransaction, "execute", execute)
        result = ProductJointQualityReader(HostTransaction(conn), SCOPE).read(**kwargs)
        assert result.joint_valid_count == 1
        assert all(sql.lstrip().startswith(("SELECT", "SHOW")) for sql in calls)
        conn.rollback()


def test_mutated_boolean_selection_revision_cannot_equal_integer_authority():
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        kwargs = inputs(conn, [row()])
        assert kwargs["binding_ref"].revision == 1
        kwargs["binding_ref"].revision = True
        with pytest.raises(ValueError, match="selection"):
            ProductJointQualityReader(HostTransaction(conn), SCOPE).read(**kwargs)
        conn.rollback()


def test_measurement_clock_cannot_precede_observation(monkeypatch):
    from types import SimpleNamespace
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        kwargs = inputs(conn, [row()])
        original = HostTransaction.execute
        def execute(self, sql, params=()):
            if sql == "SELECT clock_timestamp() AS now":
                return SimpleNamespace(fetchone=lambda: {"now": datetime(2020, 1, 1, tzinfo=UTC)})
            return original(self, sql, params)
        monkeypatch.setattr(HostTransaction, "execute", execute)
        with pytest.raises(ValueError, match="clock moved backwards"):
            ProductJointQualityReader(HostTransaction(conn), SCOPE).read(**kwargs)
        conn.rollback()
