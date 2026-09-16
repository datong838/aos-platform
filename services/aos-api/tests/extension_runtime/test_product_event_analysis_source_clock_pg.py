"""Real claim guards with named group metadata; native locator is tested separately."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

pytest_plugins = ('test_product_event_analysis_service_pg',)

from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_locator import SnapshotGroupRoute


@pytest.mark.parametrize('fault', [None, 'actor', 'control', 'run'])
def test_group_clock_and_original_source_membership(analysis_case, monkeypatch, fault):
    conn, analysis, claimed = analysis_case
    ref = PipelineExactRef(resourceType='PipelineRuntimeControlRevision',
        resourceId='pipeline-control-12345678-1234-1234-1234-123456789abc',
        revision=1, contentHash='sha256:'+'a'*64)
    analysis.source.reader._journal._ref = ref
    cutoff = (datetime.now(UTC)-timedelta(seconds=10)).replace(microsecond=123456)
    group = SnapshotGroupRoute('12345678-1234-1234-1234-123456789abc', analysis.source.actor,
        ((ref, analysis.source.reader._journal._run_id),), 'sha256:'+'b'*64,
        cutoff-timedelta(seconds=1), cutoff)
    if fault == 'actor':
        group = replace(group, actor='different-source-actor')
    elif fault == 'control':
        group = replace(group, bindings=((ref.model_copy(update={'revision':2}), group.bindings[0][1]),))
    elif fault == 'run':
        group = replace(group, bindings=((ref, 'different-original-run'),))
    monkeypatch.setattr(analysis, '_source_group', lambda db: group)
    if fault:
        with pytest.raises(ValueError, match='group differs from original source'):
            analysis._phase(conn, claimed, lambda *args: pytest.fail('foreign source admitted'))
    else:
        snapshot, request = analysis._phase(conn, claimed, lambda snapshot, request, dispatch: (snapshot, request))
        assert datetime.fromisoformat(request['cutoffAt']) == cutoff
        assert snapshot['sourceGroup'] == dict(groupId=group.group_id, manifestHash=group.manifest_hash,
            readStartedAt=group.read_started_at.isoformat(), readCompletedAt=cutoff.isoformat())
        event = conn.execute('SELECT created_at FROM automation_occurrence WHERE occurrence_id=%s',
            (claimed.occurrence_id,)).fetchone()
        assert cutoff != event['created_at']
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_investigation_run').fetchone()['n'] == 0


def test_single_source_without_snapshot_group_is_rejected(analysis_case, monkeypatch):
    conn, analysis, claimed = analysis_case
    monkeypatch.setattr(analysis, '_source_group', lambda db: None)
    with pytest.raises(ValueError, match='snapshot group differs'):
        analysis._phase(conn, claimed, lambda *args: pytest.fail('ungrouped source admitted'))
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_investigation_run').fetchone()['n'] == 0
