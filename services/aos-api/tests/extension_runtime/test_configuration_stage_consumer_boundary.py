"""The Host entry cannot be constructed with test callbacks or lookalike authority."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
from aos_api.extension_runtime.configuration_stage_consumer import ConfigurationStageConsumer


def test_production_entry_requires_closed_original_authority_before_connecting():
    def connect(): raise AssertionError('must not connect during construction')
    fake = build_current_configuration_authorization(permission=lambda *a, **k: True)
    for authority in (lambda *a, **k: True, fake, None):
        with pytest.raises(TypeError): ConfigurationStageConsumer(connect=connect, authorize=authority)
    actual = build_current_configuration_authorization(permission=CurrentConfigurationPermission(
        installation_store=PostgresInstallationStore(connect_factory=connect)))
    assert ConfigurationStageConsumer(connect=connect, authorize=actual).authorize is actual


def test_caller_transaction_cannot_enter_host_consumer():
    from psycopg.pq import TransactionStatus
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    @contextmanager
    def connect():
        yield SimpleNamespace(info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS))
    actual = build_current_configuration_authorization(permission=CurrentConfigurationPermission(
        installation_store=PostgresInstallationStore(connect_factory=connect)))
    consumer = ConfigurationStageConsumer(connect=connect, authorize=actual)
    with pytest.raises(RuntimeConflict, match='independent idle'):
        consumer.run_once(org_id='org-org', project_id='dev-project')
