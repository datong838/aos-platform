"""Host callback boundary tests; named fakes do not prove live authorization."""
import pytest

from test_ecommerce_product_event_policy import case
import aos_api.ecommerce_product_event_reader as module
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_snapshot_materialization import SnapshotMapping


def test_current_owner_denial_prevents_candidate_query(monkeypatch):
    body, _ = case()
    owner = object.__new__(PipelineSourceSelectionOwner)
    def denied(*args, **kwargs): raise PermissionError('test current denial')
    owner.run_current_snapshot = denied
    monkeypatch.setattr(module, '_read_candidates', lambda *args: pytest.fail('must not query'))
    with pytest.raises(PermissionError): module.ProductEventCandidateReader(owner).read(None,policy=body,actor='test')


@pytest.mark.parametrize('wrong_shop', [False, True])
def test_pinned_mapping_scope_and_source_limit(monkeypatch, wrong_shop):
    body, selection = case()
    owner = object.__new__(PipelineSourceSelectionOwner)
    mapping = SnapshotMapping(selection.read_spec, (), (), (), 'niushop', 'site_id',
        '2' if wrong_shop else '1', '+08:00', ())
    def named_fake_current(conn, *, scope, ref, actor, execute):
        assert scope.key == (body['orgId'],body['projectId'])
        assert ref == selection.ref
        return execute(selection.draft,mapping)
    owner.run_current_snapshot = named_fake_current
    calls=[]
    monkeypatch.setattr(module,'_read_candidates',lambda conn,policy,limit: calls.append(limit) or ())
    if wrong_shop:
        with pytest.raises(PermissionError):module.ProductEventCandidateReader(owner).read(None,policy=body,actor='test')
        assert calls==[]
    else:
        assert module.ProductEventCandidateReader(owner).read(None,policy=body,actor='test')==()
        assert calls==[min(selection.draft.row_limit,100)]
