"""Preparation reuses the live binding checks without inventing ScheduleRuns."""
from unittest.mock import MagicMock

import pytest

from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict, _digest
from aos_api.tenant_scope import TenantScope


def fixture():
    graph = {'pipeline_id':'p01','nodes':[{'node_type':'source','config':{'source_id':'source-one'}}]}
    source = {'type':'jdbc-mysql-ssh','status':'registered','configuration_revision':'11111111-1111-4111-8111-111111111111'}
    args = dict(pipeline_id='p01', source_id='source-one', source_revision=source['configuration_revision'],
        pipeline_hash=_digest(graph), graph_revision=3)
    return graph, source, args


def test_current_graph_and_source_can_be_checked_before_any_schedule():
    graph, source, args = fixture()
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [{'payload':graph,'revision':3}, source]
    IngressJournal().verify_pipeline_source_binding(conn, TenantScope('org-org','dev-project'), **args)
    assert conn.execute.call_count == 2
    for query, params in [call.args for call in conn.execute.call_args_list]:
        assert params[:2] == ('org-org','dev-project')
        assert 'FOR SHARE' in str(query)
        assert 'meta_schedule' not in str(query)


@pytest.mark.parametrize('case', ['missing_graph','hash','revision','node_source','source_type','source_revision','missing_source'])
def test_binding_drift_is_rejected(case):
    graph, source, args = fixture()
    row = {'payload':graph,'revision':3}
    if case == 'missing_graph': row = None
    elif case == 'hash': args['pipeline_hash'] = 'a'*64
    elif case == 'revision': row['revision'] = 4
    elif case == 'node_source':
        graph['nodes'][0]['config']['source_id'] = 'another-source'
        args['pipeline_hash'] = _digest(graph)
    elif case == 'source_type': source['type'] = 'fixture-unapproved'
    elif case == 'source_revision': source['configuration_revision'] = '22222222-2222-4222-8222-222222222222'
    else: source = None
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [row, source]
    with pytest.raises(IngressJournalConflict):
        IngressJournal().verify_pipeline_source_binding(conn, TenantScope('org-org','dev-project'), **args)


@pytest.mark.parametrize('revision', [True, 0, '3', 2**63])
def test_revision_type_is_checked_before_database_access(revision):
    _, _, args = fixture()
    conn = MagicMock()
    with pytest.raises(ValueError):
        IngressJournal().verify_pipeline_source_binding(conn, TenantScope('org-org','dev-project'), **(args|{'graph_revision':revision}))
    conn.execute.assert_not_called()


def test_real_execution_still_requires_a_running_schedule():
    _, _, args = fixture()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    journal = IngressJournal()
    with pytest.raises(IngressJournalConflict, match='INGRESS_RUNNING_SCHEDULE_REQUIRED'):
        journal.verify_running_schedule(conn, TenantScope('org-org','dev-project'), run_id='not-a-run', **args)
    assert conn.execute.call_count == 1
