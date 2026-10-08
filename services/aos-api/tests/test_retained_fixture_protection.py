"""Retained lab records must survive legacy test-client ontology cleanup."""
import pytest
from tests import conftest as fixtures


@pytest.fixture(scope="session", autouse=True)
def _isolated_postgres_database():
    """Pure cleanup boundary tests: no database creation or connection."""
    yield


class RecordingConnection:
    def __init__(self, fail=False):
        self.statements = []
        self.commits = 0
        self.fail = fail

    def execute(self, statement):
        self.statements.append(statement)
        if self.fail:
            raise RuntimeError('cleanup SQL failed')

    def commit(self):
        self.commits += 1


def test_retained_database_has_no_cleanup_effect(monkeypatch):
    monkeypatch.setenv('AOS_TEST_RETAIN_DATABASE', '1')
    conn = RecordingConnection(fail=True)
    fixtures._cleanup_ontology_test_data(conn)
    assert conn.statements == []
    assert conn.commits == 0


@pytest.mark.parametrize('value', [None, '0', 'other'])
def test_disposable_database_keeps_existing_cleanup(monkeypatch, value):
    if value is None:
        monkeypatch.delenv('AOS_TEST_RETAIN_DATABASE', raising=False)
    else:
        monkeypatch.setenv('AOS_TEST_RETAIN_DATABASE', value)
    conn = RecordingConnection()
    fixtures._cleanup_ontology_test_data(conn)
    assert len(conn.statements) == 2
    assert conn.statements[0] == "DELETE FROM obj_instance WHERE props->>'source' IS NOT NULL"
    assert 'DELETE FROM meta_object_type WHERE id NOT IN' in conn.statements[1]
    assert conn.commits == 1


def test_disposable_cleanup_failure_is_not_committed(monkeypatch):
    monkeypatch.delenv('AOS_TEST_RETAIN_DATABASE', raising=False)
    conn = RecordingConnection(fail=True)
    with pytest.raises(RuntimeError, match='cleanup SQL failed'):
        fixtures._cleanup_ontology_test_data(conn)
    assert conn.commits == 0


def test_original_client_routes_cleanup_through_protection():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(fixtures.__file__).read_text())
    client = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'client')
    calls = [node for node in ast.walk(client) if isinstance(node, ast.Call)]
    protected = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == '_cleanup_ontology_test_data']
    assert len(protected) == 1
    assert isinstance(protected[0].args[0], ast.Name)
    assert protected[0].args[0].id == '_c'
    assert not any(isinstance(node, ast.Constant) and isinstance(node.value, str)
                   and ('DELETE FROM meta_object_type' in node.value or 'DELETE FROM obj_instance' in node.value)
                   for node in ast.walk(client))
