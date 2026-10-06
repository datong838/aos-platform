from contextlib import contextmanager
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api import membership, orgs, tenant_catalog, workspaces_catalog


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.setattr(tenant_catalog, 'persistence_enabled', lambda: True)
    monkeypatch.setattr(tenant_catalog, '_catalog_tables_present', lambda: True)
    for module, name in [(orgs, '_ORGS'), (workspaces_catalog, '_WS'), (membership, '_MEMBERS')]:
        monkeypatch.setattr(module, name, {})
    def forbidden(*args, **kwargs):
        raise AssertionError('read-only boot/query must not persist or run DDL')
    monkeypatch.setattr(tenant_catalog, 'ensure_tenant_catalog_schema', forbidden)
    monkeypatch.setattr(orgs, '_persist_org', forbidden)
    monkeypatch.setattr(workspaces_catalog, '_persist_ws', forbidden)
    monkeypatch.setattr(membership, '_persist_member', forbidden)
    return monkeypatch


def test_readonly_boot_preserves_existing_viewer_and_queries_never_write(catalog):
    rows = {
        'meta_org': [dict(id='org-org', name='existing', kind='saas', join_policy='invite_only', discoverable=False)],
        'meta_workspace': [dict(org_id='org-org', project_id='dev-project', name='existing workspace', deletable=False, kind='custom')],
        'meta_membership': [dict(org_id='org-org', project_id='dev-project', subject='existing-user', role='viewer')],
    }
    class Connection:
        def execute(self, sql):
            assert sql.strip().startswith('SELECT')
            self.rows = next(values for table, values in rows.items() if 'FROM '+table in sql)
            return self
        def fetchall(self):
            return self.rows
    @contextmanager
    def connect(*, inherit_scope, platform_role):
        assert inherit_scope is False and platform_role is True
        yield Connection()
    for module in (orgs, workspaces_catalog, membership):
        catalog.setattr(module, 'connect_read_only', connect)
    # Execute the actual non-legacy startup branch, then the actual read routers.
    tree = ast.parse((Path(__file__).parents[2] / 'aos_api' / 'main.py').read_text())
    body = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_lifespan_body')
    branch = next(n for n in body.body if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.operand, ast.Name) and n.test.operand.id == 'legacy_bootstrap')
    exec(compile(ast.Module(body=[branch], type_ignores=[]), '<actual startup branch>', 'exec'), {'legacy_bootstrap': False})
    from aos_api.routers.me import me, person
    from aos_api.routers.workspaces import list_workspaces
    catalog.setattr(person, 'get_profile', lambda subject: {})
    principal = SimpleNamespace(org_id='org-org', project_id='dev-project', subject='existing-user', roles=['viewer'], markings=[], token_kind='test')
    assert me(principal)['orgName'] == 'existing'
    assert list_workspaces(principal)['items'][0]['name'] == 'existing workspace'
    membership.ensure_default_membership('org-org', 'dev-project', 'existing-user')
    assert membership.list_members('org-org', 'dev-project')[0]['role'] == 'viewer'
    assert orgs.get_org('org-org')['name'] == 'existing'
    assert workspaces_catalog.get_workspace('org-org', 'dev-project')['name'] == 'existing workspace'


def test_missing_tables_refuses_without_ddl(catalog):
    catalog.setattr(tenant_catalog, '_catalog_tables_present', lambda: False)
    with pytest.raises(RuntimeError, match='TENANT_CATALOG_SCHEMA_UNAVAILABLE'):
        tenant_catalog.boot_tenant_catalogs(read_only=True)


@pytest.mark.parametrize('module,loader', [(orgs, 'load_orgs_from_db'), (workspaces_catalog, 'load_workspaces_from_db'), (membership, 'load_memberships_from_db')])
def test_strict_load_failure_is_not_empty_catalog(catalog, module, loader):
    @contextmanager
    def unavailable(**kwargs):
        raise RuntimeError('catalog connection failed')
        yield
    catalog.setattr(module, 'connect_platform', unavailable)
    catalog.setattr(module, 'connect_read_only', unavailable)
    with pytest.raises(RuntimeError, match='catalog connection failed'):
        getattr(module, loader)(strict=True)
    assert getattr(module, loader)() == 0


def test_nonlegacy_lifespan_executes_strict_catalog_boot():
    path = Path(__file__).parents[2] / 'aos_api' / 'main.py'
    tree = ast.parse(path.read_text())
    body = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_lifespan_body')
    branch = next((n for n in body.body if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.operand, ast.Name) and n.test.operand.id == 'legacy_bootstrap'), None)
    assert branch is not None
    calls = [n for n in ast.walk(branch) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'boot_tenant_catalogs']
    assert any(k.arg == 'read_only' and isinstance(k.value, ast.Constant) and k.value.value is True for c in calls for k in c.keywords)


def test_memory_boot_keeps_existing_cache_and_never_connects(catalog):
    catalog.setattr(tenant_catalog, 'persistence_enabled', lambda: False)
    orgs._ORGS['existing'] = {'id': 'existing', 'name': 'preserved'}
    def forbidden():
        raise AssertionError('memory mode must not access PG')
    catalog.setattr(tenant_catalog, '_catalog_tables_present', forbidden)
    tenant_catalog.boot_tenant_catalogs(read_only=True)
    assert orgs._ORGS['existing']['name'] == 'preserved'


def test_legacy_boot_keeps_original_loader_contract(catalog):
    calls = []
    catalog.setattr(tenant_catalog, 'ensure_tenant_catalog_schema', lambda: calls.append('schema'))
    for module, loader in [(orgs, 'load_orgs_from_db'), (workspaces_catalog, 'load_workspaces_from_db'), (membership, 'load_memberships_from_db')]:
        catalog.setattr(module, loader, lambda: calls.append('load'))
    tenant_catalog.boot_tenant_catalogs()
    assert calls == ['schema', 'load', 'load', 'load']
