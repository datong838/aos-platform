"""Only the explicitly enabled, preflighted staging consumer enters the original Host."""
from dataclasses import replace

import pytest

from test_production_runtime import _connector, _dependencies, _patch_identities
from aos_api.extension_runtime.production_runtime import select_production_runtime_host
from aos_api.extension_runtime.configuration_stage_consumer import ConfigurationStageConsumer


@pytest.mark.parametrize('enabled,ready', ((False, False), (True, False), (True, True)))
def test_staging_consumer_needs_explicit_flag_and_preflight(monkeypatch, enabled, ready):
    _patch_identities(monkeypatch)
    calls, checks = [], []
    runtime = _connector('runtime', calls)
    def probe(conn):
        checks.append(conn.name)
        return ready
    monkeypatch.setattr('aos_api.extension_runtime.production_runtime.configuration_stage_ready', probe)
    selected = select_production_runtime_host(enabled=True,
        directory_connect=_connector('directory', calls, ({'org_id':'org-org','project_id':'dev-project','assignment_revision':1},)),
        runtime_connect=runtime, web_connect=_connector('web', calls),
        dependencies=replace(_dependencies(runtime), configuration_stage_enabled=enabled))
    assert checks == (['runtime'] if enabled else [])
    if enabled and not ready:
        assert selected.host is None and selected.error_code == 'CONFIGURATION_STAGE_PREFLIGHT_FAILED'
    else:
        assignment = selected.host._current_assignments()[0]
        assert sum(type(c) is ConfigurationStageConsumer for c in assignment.consumers) == int(enabled)


@pytest.mark.parametrize('value', (1, '1', None))
def test_staging_dependency_flag_does_not_coerce(value):
    with pytest.raises(TypeError):
        replace(_dependencies(_connector('unused', [])), configuration_stage_enabled=value)
