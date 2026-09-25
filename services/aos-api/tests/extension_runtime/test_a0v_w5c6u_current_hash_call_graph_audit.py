"""No-effect contracts for current-authority reads around independent commits."""

from pathlib import Path


API = Path(__file__).resolve().parents[2] / 'aos_api'


def _source(name):
    return (API / name).read_text()


def test_object_rechecks_group_current_before_each_independent_single_resume():
    source = _source('pipeline_snapshot_group_object_executor.py')
    loop = source.index('for ref,run in sorted(bindings')
    current = source.index('saved=self._journal.read_current(conn,**args)', loop)
    resume = source.index('result=self._single.resume_saved(', current)
    final = source.index('completions=self._journal.run_current(', resume)
    assert loop < current < resume < final


def test_link_rechecks_after_store_commit_and_before_projection_readback():
    source = _source('pipeline_snapshot_group_link_executor.py')
    prepare = source.index('prepared = self._commands.prepare(conn, **args)')
    store = source.index('result = self._store.apply_strict_link_batch(', prepare)
    post_store = source.index('current(conn)', store)
    project = source.index('projection = (_project_exact_command(', post_store)
    completion = source.index('completion = (self._store.read_batch_projection_completion(', project)
    assert prepare < store < post_store < project < completion


def test_retirement_rechecks_after_store_commit_and_at_projection_completion():
    source = _source('pipeline_snapshot_group_retirement_executor.py')
    prepare = source.index('prepared = self._retirement.prepare(conn, **args)')
    store = source.index('result = self._store.apply_strict_link_retirement_batch(', prepare)
    post_store = source.index('current(conn)', store)
    project = source.index('projection = (_project_exact_command(', post_store)
    completion = source.index('completion = (self._store.read_batch_projection_completion(', project)
    assert prepare < store < post_store < project < completion
