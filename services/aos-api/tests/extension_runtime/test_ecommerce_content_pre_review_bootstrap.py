"""Read-only installation preflight never grants authority from partial rows."""

from contextlib import contextmanager

import pytest

from aos_api import ecommerce_content_pre_review_bootstrap as bootstrap
from aos_api.ecommerce_content_pre_review_bootstrap import preflight_content_pre_review_install
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _factory(schema="a0v_105", graph=0, suites=0, contracts=0):
    queries = []

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchall(self):
            return self.row

    class Conn:
        def execute(self, query, params=None):
            queries.append((query, params))
            if "alembic_version" in query:
                return Cursor([{"version_num": schema}])
            if "aip_logic_graph" in query:
                assert params == (*SCOPE.key, "ecommerce.content.pre-review.v1")
                return Cursor([{"graph_id": "ecommerce.content.pre-review.v1"}] * graph)
            if "aip_eval_suite_revision" in query:
                assert params[:2] == SCOPE.key
                rows = [{"suite_id": "ecommerce.content.pre-review.governance.v1", "revision": 1},
                        {"suite_id": "ecommerce.content.pre-review.subject.v1", "revision": 1}]
                return Cursor((rows + [rows[0]])[:suites])
            if "aip_eval_contract_revision" in query:
                assert params == (*SCOPE.key, "ecommerce_content")
                rows = [{"contract_id": "contract", "revision": 1},
                        {"contract_id": "contract", "revision": 2},
                        {"contract_id": "other", "revision": 1}]
                return Cursor(rows[:contracts])
            raise AssertionError(query)

    @contextmanager
    def connect():
        yield Conn()

    return connect, queries


def test_preflight_blocks_old_schema_before_inventory():
    connect, queries = _factory(schema="a0v_092")
    result = preflight_content_pre_review_install(SCOPE, connect)
    assert result.state == "SCHEMA_BLOCKED"
    assert result.schema_revision == "a0v_092"
    assert len(queries) == 1


def test_preflight_all_empty_is_installable_but_not_installed():
    connect, queries = _factory()
    result = preflight_content_pre_review_install(SCOPE, connect)
    assert result.state == "INSTALLABLE"
    assert (result.graph_count, result.suite_count, result.contract_count) == (0, 0, 0)
    assert len(queries) == 4


@pytest.mark.parametrize("graph,suites,contracts", [(1, 0, 0), (0, 2, 0), (1, 2, 0), (0, 0, 1), (1, 2, 3)])
def test_preflight_partial_or_ambiguous_rows_require_reconciliation(graph, suites, contracts):
    connect, _ = _factory(graph=graph, suites=suites, contracts=contracts)
    result = preflight_content_pre_review_install(SCOPE, connect)
    assert result.state == "RECONCILE_REQUIRED"


def test_preflight_fails_closed_on_unknown_schema_rows():
    connect, _ = _factory(schema="future")
    result = preflight_content_pre_review_install(SCOPE, connect)
    assert result.state == "SCHEMA_BLOCKED"


def test_preflight_calls_exact_authority_reader_before_reporting_installed(monkeypatch):
    connect, _ = _factory(graph=1, suites=2, contracts=2)
    checked = []
    monkeypatch.setattr(bootstrap, "require_current_content_pre_review_gate",
                        lambda _conn, scope: checked.append(scope))
    result = preflight_content_pre_review_install(SCOPE, connect)
    assert result.state == "INSTALLED"
    assert checked == [SCOPE]


def test_preflight_rejects_full_inventory_with_invalid_authority(monkeypatch):
    connect, _ = _factory(graph=1, suites=2, contracts=2)

    def invalid(_conn, _scope):
        raise ValueError("publication revoked")

    monkeypatch.setattr(bootstrap, "require_current_content_pre_review_gate", invalid)
    assert preflight_content_pre_review_install(SCOPE, connect).state == "RECONCILE_REQUIRED"
