"""Registration is pure assembly, independent of legacy schema/bootstrap."""
from unittest.mock import Mock


def test_runtime_registration_has_no_database_or_source_effect(monkeypatch):
    from aos_api import main, db
    from aos_api import ec_live_executor as live
    from aos_api import phase5_pipeline_engine as engine_module
    engine = Mock()
    monkeypatch.setattr(engine_module, 'get_engine', lambda: engine)
    monkeypatch.setattr(db, 'connect', Mock(side_effect=AssertionError('registration queried database')))
    monkeypatch.setattr(live, 'fetch_source_rows', Mock(side_effect=AssertionError('registration queried source')))
    main._register_pipeline_runtime()
    main._register_pipeline_runtime()
    assert engine.register_executor.call_count == 2
    assert engine.register_executor.call_args.args == ('ec-live-v1', live.ec_live_executor)
    assert engine.register_evidence_resolver.call_args.args[0] == 'dataset'
    db.connect.assert_not_called()
    live.fetch_source_rows.assert_not_called()


def test_explicit_ssh_prebuild_disable_never_reads_source(monkeypatch):
    from aos_api import main, jdbc_connector_runtime
    prebuild = Mock(side_effect=AssertionError('disabled warmup contacted source'))
    monkeypatch.setattr(jdbc_connector_runtime, 'prebuild_all_ssh_tunnels_from_meta_source', prebuild)
    monkeypatch.setenv('AOS_JDBC_SSH_PREBUILD_ENABLED', 'false')
    main._prebuild_jdbc_ssh_tunnels()
    prebuild.assert_not_called()
