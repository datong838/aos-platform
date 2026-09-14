"""Host callback boundary tests; named fakes do not prove live authorization."""
import pytest

from test_ecommerce_product_event_policy import case
import aos_api.ecommerce_product_event_reader as module
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v3 import SnapshotMappingV3
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.ecom_consistency_store import EcomConsistencyStore

def reader(owner):
    journal=object.__new__(ControlledIngressJournal)
    journal.lock_run=lambda *args: None
    journal.read_derived=lambda *args: {'commands':[]}
    return module.ProductEventCandidateReader(owner,journal=journal,store=object.__new__(EcomConsistencyStore))


def test_current_owner_denial_prevents_candidate_query(monkeypatch):
    body, _ = case()
    owner = object.__new__(PipelineSourceSelectionOwner)
    def denied(*args, **kwargs): raise PermissionError('test current denial')
    owner.run_current_snapshot = denied
    monkeypatch.setattr(module, '_read_candidates', lambda *args: pytest.fail('must not query'))
    with pytest.raises(PermissionError): reader(owner).read(None,policy=body,actor='test',run_id='original')


@pytest.mark.parametrize('wrong_shop,wrong_parent', [(False,False),(True,False),(False,True)])
@pytest.mark.parametrize('version', ['v1','v3'])
def test_pinned_mapping_and_original_ingress_scope(monkeypatch, wrong_shop,wrong_parent,version):
    body, selection = case()
    owner = object.__new__(PipelineSourceSelectionOwner)
    mapping = SnapshotMapping(selection.read_spec, (), (), (), 'niushop', 'site_id',
        '2' if wrong_shop else '1', '+08:00', ())
    if version == 'v3':
        mapping = SnapshotMappingV3(mapping, (), (), 'state', 'state', ((1,'ACTIVE'),))
    def named_fake_current(conn, *, scope, ref, actor, execute):
        assert scope.key == (body['orgId'],body['projectId'])
        assert ref == selection.ref
        return execute(selection.draft,mapping)
    owner.run_current_snapshot = named_fake_current
    monkeypatch.setattr(module,'_bound_parent',lambda *args: dict(kind='empty_observation_v1',pipelineId=selection.draft.pipeline_id,
        sourceId='wrong-source' if wrong_parent else selection.draft.source_id,sourceRevision=selection.draft.source_configuration_ref.resource_id.removeprefix('source-config-'),pipelineHash=selection.draft.graph_hash))
    calls=[]
    monkeypatch.setattr(module,'_read_candidates',lambda conn,policy,limit,evidence: calls.append(limit) or ())
    if wrong_shop or wrong_parent:
        with pytest.raises(PermissionError):reader(owner).read(None,policy=body,actor='test',run_id='original')
        assert calls==[]
    else:
        assert reader(owner).read(None,policy=body,actor='test',run_id='original')==()
        assert calls==[]
