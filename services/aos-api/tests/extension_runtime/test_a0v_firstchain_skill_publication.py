from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import a0v_firstchain_skill_publication as preparation


@pytest.mark.parametrize('database', ['aos_meta_head', 'postgres', 'other_clone', None])
def test_non_owned_clone_is_rejected_before_constructing_stores(monkeypatch, database):
    calls = []
    def execute(query):
        calls.append(query)
        return SimpleNamespace(fetchone=lambda: None if database is None else {'database': database})
    @contextmanager
    def connect(scope):
        assert scope == preparation.SCOPE
        yield SimpleNamespace(execute=execute)
    monkeypatch.setattr(preparation, 'AipModelRuntimeStore', lambda *a: pytest.fail('must reject before stores'))
    with pytest.raises(ValueError, match='FIRSTCHAIN_CONTRACT_CLONE_ONLY'):
        preparation.prepare_contracts(connect)
    assert calls == ['SELECT current_database() AS database']


def test_no_implicit_database_fallback():
    with pytest.raises(ValueError, match='EXPLICIT_CLONE_CONNECTION_REQUIRED'):
        preparation.prepare_contracts(None)


def test_d03_uses_its_own_graph_and_input_contract():
    build, evaluate, registry = preparation.contract_components('D03')
    request = build('exact-test-model')
    assert request.id == 'ecommerce.logic.D03'
    assert request.nodes[-1].config['expression'] == '"GrowthPlan.DRAFT"'
    from aos_api.aip_logic_graph_models import LogicGraphSnapshot
    from datetime import UTC, datetime
    from aos_api.aip_logic_graph_models import compute_logic_graph_hash
    graph = LogicGraphSnapshot(**request.model_dump(exclude={'id'}), id=request.id,
        revision=1, graph_hash=compute_logic_graph_hash(request),
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    result = evaluate(graph, registry('exact-test-model'), datetime.now(UTC))
    assert result.report.gate_passed
    assert {case.id for case in result.suite.cases} == {
        'd03-positive','d03-structure','d03-fact-boundary','d03-external-action','d03-sensitive','d03-adapter-failure'}


def test_unknown_skill_does_not_reuse_a_data_advisor_recipe():
    with pytest.raises(ValueError, match='FIRSTCHAIN_SKILL_UNSUPPORTED'):
        preparation.contract_components('D99')

@pytest.mark.parametrize('logic_id',['S01','P01','C06','A02','G06'])
def test_investigation_role_uses_own_complete_contract(logic_id):
    from datetime import UTC,datetime
    from aos_api.aip_logic_graph_models import LogicGraphSnapshot,compute_logic_graph_hash
    build,evaluate,registry=preparation.contract_components(logic_id)
    request=build('exact-test-model')
    assert request.id=='ecommerce.logic.'+logic_id
    graph=LogicGraphSnapshot(**request.model_dump(exclude={'id'}),id=request.id,revision=1,
        graph_hash=compute_logic_graph_hash(request),created_at=datetime.now(UTC),updated_at=datetime.now(UTC))
    result=evaluate(graph,registry('exact-test-model'),datetime.now(UTC))
    assert result.report.gate_passed
    assert result.report.total>=6
    assert all(case.id.startswith(logic_id.lower()+'-') for case in result.suite.cases)
