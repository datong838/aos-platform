"""Read-factory compatibility boundaries; no original DB fixture is loaded."""
from contextlib import contextmanager

import pytest

from aos_api import aip_budget_cost_proposal_store as store
from aos_api.auth import Principal
from test_budget_policy_window_review import SnapshotConnection, HUMAN


def principal(subject=HUMAN):
    return Principal(subject=subject,org_id='org-org',project_id='dev-project',token_kind='oidc')


@pytest.mark.parametrize('operation',['get','review','inquire'])
def test_injected_read_factory_retains_existing_cost_semantics(operation):
    conn=SnapshotConnection();opened=[]
    @contextmanager
    def borrow(scope):
        opened.append(scope.key);yield conn
    source=store.BudgetCostProposalStore(read_connect_factory=borrow)
    if operation=='inquire':
        value=source.inquire(principal('unit-machine'),conn.proposal,'unit-key')
        assert value['status']=='observed'
    else:
        value=getattr(source,operation)(principal(),'unit-proposal')
        assert (value['proposal'] if operation=='review' else value)['activationEligible'] is False
    assert opened==[('org-org','dev-project')]


@pytest.mark.parametrize('operation',['get','review','inquire'])
def test_default_read_factory_remains_dynamic_and_existing_behavior_is_unchanged(monkeypatch,operation):
    conn=SnapshotConnection();opened=[]
    source=store.BudgetCostProposalStore()
    @contextmanager
    def factory(scope):opened.append(scope.key);yield conn
    monkeypatch.setattr(store,'connect_read_only',factory)
    if operation=='inquire': source.inquire(principal('unit-machine'),conn.proposal,'unit-key')
    else:getattr(source,operation)(principal(),'unit-proposal')
    assert opened==[('org-org','dev-project')]


def test_read_factory_cannot_replace_create_write_connection(monkeypatch):
    class OriginalWriteChosen(Exception):pass
    conn=SnapshotConnection();write_calls=[]
    def no_read(*args):raise AssertionError('read factory selected for create')
    @contextmanager
    def original_write(scope):
        write_calls.append(scope.key)
        raise OriginalWriteChosen()
        yield
    monkeypatch.setattr(store,'connect_serializable',original_write)
    with pytest.raises(OriginalWriteChosen):
        store.BudgetCostProposalStore(read_connect_factory=no_read).create(
            principal('unit-machine'),conn.proposal,'unit-key')
    assert write_calls==[('org-org','dev-project')]
