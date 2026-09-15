import importlib
from types import SimpleNamespace
import pytest
from test_growth19_successor_business import profile


def test_revision_key_preserves_legacy_and_separates_successors(profile):
    import a0v_firstchain_skill_publication
    m=importlib.import_module('skill_eval_revision_key')
    key='suite-run-r1'
    graph=SimpleNamespace(revision=1,graph_hash='a'*64)
    assert m.skill_eval_revision_key(key,graph)==key
    graph.revision=2
    first=m.skill_eval_revision_key(key,graph)
    assert first!=key and 'a'*64 in first
    graph.graph_hash='b'*64
    assert m.skill_eval_revision_key(key,graph)!=first


@pytest.mark.parametrize('revision,hash_value',[(0,'a'*64),(2,'bad'),(2,'A'*64)])
def test_revision_key_rejects_unbound_identity(profile,revision,hash_value):
    import a0v_firstchain_skill_publication
    m=importlib.import_module('skill_eval_revision_key')
    with pytest.raises(ValueError):
        m.skill_eval_revision_key('suite-run-r1',SimpleNamespace(revision=revision,graph_hash=hash_value))
