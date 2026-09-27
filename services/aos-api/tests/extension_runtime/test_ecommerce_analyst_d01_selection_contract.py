"""A D01 packet proposal is only a bounded candidate, never approval."""
from datetime import timedelta

import pytest

from aos_api.ecommerce_analyst_d01_source_selection import D01SourceSelectionProposal
from test_ecommerce_analyst_d01_issuer import NOW, SCOPE, _packet, _resource


def _candidate(**changes):
    fields = dict(
        tenant={'orgId': SCOPE.org_id, 'projectId': SCOPE.project_id},
        taskRunRef=_resource('TaskRun', 'run-1', '2'),
        planRef=_resource('PlanRevision', 'plan-1'),
        planContentHash='a' * 64,
        sourceSelectionRef={
            'resourceType': 'SourceSelectionRevision',
            'resourceId': 'source-selection-1', 'revision': 1,
            'contentHash': 'sha256:' + 'a' * 64,
        },
        packet=_packet(), proposedBy='analyst-owner', proposedAt=NOW,
    )
    fields.update(changes)
    return D01SourceSelectionProposal.model_validate(fields)


def test_proposal_has_stable_identity_but_no_approval():
    first = _candidate()
    second = _candidate()
    assert first.selection_id == second.selection_id
    assert first.selection_id.startswith('d01-source-')
    assert not hasattr(first, 'approved_by')


@pytest.mark.parametrize('change', [
    {'taskRunRef': _resource('Task', 'run-1', '2')},
    {'planRef': _resource('PlanRevision', 'plan-1', None)},
    {'sourceSelectionRef': {
        'resourceType': 'EvidenceBundleRevision', 'resourceId': 'source-selection-1',
        'revision': 1, 'contentHash': 'sha256:' + 'a' * 64,
    }},
    {'proposedBy': ' '},
    {'proposedAt': NOW - timedelta(seconds=1)},
])
def test_proposal_rejects_incomplete_identity_or_future_cutoff(change):
    with pytest.raises(ValueError):
        _candidate(**change)
