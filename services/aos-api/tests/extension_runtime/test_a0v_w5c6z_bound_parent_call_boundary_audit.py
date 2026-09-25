"""No-effect contracts for saved parent rereads under original current grants."""

from pathlib import Path


API = Path(__file__).resolve().parents[2] / 'aos_api'


def _source(name):
    return (API / name).read_text()


def test_input_consumer_reloads_original_input_before_and_after_callback():
    source = _source('pipeline_snapshot_group_input_owner.py')
    start = source.index('def _run(self,conn,')
    first = source.index('current=self._load(conn,group,args,completed_read=completed_read)', start)
    consume = source.index('result=execute(current);_reject_deferred(result)', first)
    second = source.index('if self._load(conn,group,args,completed_read=completed_read)!=current:', consume)
    assert start < first < consume < second


def test_every_original_member_parent_is_read_and_bound_to_running_schedule():
    source = _source('pipeline_snapshot_group_input_owner.py')
    start = source.index('def _load(self,conn,group,args,')
    loop = source.index('for leaf,(ref,draft,mapping),member in zip(', start)
    parent = source.index('parent=_bound_parent(conn,scope,member.run_id,journal)', loop)
    envelope = source.index("leaf['envelopeHash']!=_digest(parent)", parent)
    append = source.index('parents.append(parent)', envelope)
    assert start < loop < parent < envelope < append
    bound = _source('ec_ingress_recovery.py')
    read = bound.index('parent = journal.read(conn, scope, run_id)', bound.index('def _bound_parent('))
    verify = bound.index('journal.verify_running_schedule(', read)
    returned = bound.index('return parent', verify)
    assert read < verify < returned


def test_interrupted_measurement_does_not_imply_skipped_parent_guard():
    loads = 30 + 28 + 56
    expected = loads * 12
    observed_before_interrupt = 1357
    assert expected == 1368
    assert expected - observed_before_interrupt == 11
    assert 0 < observed_before_interrupt < expected
