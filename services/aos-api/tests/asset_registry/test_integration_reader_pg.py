"""Real PostgreSQL tests for the authorized M4 Integration Case reader."""

from __future__ import annotations

import pytest
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
)
from aos_api.asset_registry.integration_reader import (
    PostgresIntegrationCaseReader,
    PrincipalMarkingResolver,
)
from aos_api.asset_registry.integration_store import PostgresIntegrationStore
from tests.asset_registry.test_integration_store_pg import (
    INSTALLATION_ID,
    ORG,
    PROJECT,
    _Clock,
    _create,
    _schema,
    _seed_active_installation,
)


def test_reader_projects_current_reference_stats_detail_and_timeline() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store = PostgresIntegrationStore(connect_factory, clock=_Clock())
        current = _create(store)
        reference = store.create_reference_case(
            org_id=ORG, project_id=PROJECT, display_name="脱敏参考"
        )
        reader = PostgresIntegrationCaseReader(connect_factory)

        listed = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="current",
            allowed_markings=("internal",),
            limit=20,
            offset=0,
        )
        assert listed.total == 1
        assert listed.items[0].case_id == current.case_id
        assert listed.stats is not None
        assert listed.stats.case_count.value == 1
        assert listed.stats.connector_count.value is None

        detail = reader.get_case_detail(
            org_id=ORG,
            project_id=PROJECT,
            case_id=current.case_id,
            allowed_markings=("internal",),
        )
        assert detail.scope == "current"
        assert detail.installation_id == str(INSTALLATION_ID)
        assert detail.metrics.connector_count.value is None

        timeline = reader.list_case_timeline(
            org_id=ORG,
            project_id=PROJECT,
            case_id=current.case_id,
            allowed_markings=("internal",),
            limit=20,
            offset=0,
        )
        assert timeline.total == 1
        assert timeline.items[0].cause == "created"

        references = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="reference",
            allowed_markings=(),
            limit=20,
            offset=0,
        )
        assert references.total == 1
        assert references.items[0].case_id == reference.case_id
        assert references.stats is None


def test_reader_filters_before_total_and_fails_closed_on_corruption() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store = PostgresIntegrationStore(connect_factory, clock=_Clock())
        current = _create(store)
        reader = PostgresIntegrationCaseReader(connect_factory)

        hidden = reader.list_cases(
            org_id=ORG,
            project_id=PROJECT,
            scope="current",
            allowed_markings=(),
            limit=20,
            offset=0,
        )
        assert hidden.total == 0 and hidden.items == []
        with pytest.raises(AssetNotFoundError):
            reader.get_case_detail(
                org_id=ORG,
                project_id=PROJECT,
                case_id=current.case_id,
                allowed_markings=(),
            )

        with connect_factory() as conn:
            conn.execute(
                "ALTER TABLE integration_evidence_snapshot DISABLE TRIGGER USER"
            )
            conn.execute(
                "UPDATE integration_evidence_snapshot SET snapshot_hash=%s",
                ("sha256:" + "0" * 64,),
            )
            conn.execute(
                "ALTER TABLE integration_evidence_snapshot ENABLE TRIGGER USER"
            )
            conn.commit()
        with pytest.raises(EvidenceIntegrityCorruptError):
            reader.list_cases(
                org_id=ORG,
                project_id=PROJECT,
                scope="current",
                allowed_markings=("internal",),
                limit=20,
                offset=0,
            )


def test_principal_marking_resolver_requires_active_tenant_binding() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        resolver = PrincipalMarkingResolver()
        with connect_factory() as conn:
            assert resolver.required_markings_for_create_in_transaction(
                conn,
                org_id=ORG,
                project_id=PROJECT,
                installation_id=str(INSTALLATION_ID),
                principal_markings=("secret", "internal"),
            ) == ["internal", "secret"]
            with pytest.raises(AssetNotFoundError):
                resolver.required_markings_for_create_in_transaction(
                    conn,
                    org_id="other-org",
                    project_id=PROJECT,
                    installation_id=str(INSTALLATION_ID),
                    principal_markings=("internal",),
                )
