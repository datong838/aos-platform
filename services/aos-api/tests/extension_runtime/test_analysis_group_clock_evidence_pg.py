"""Original Evidence Owner chronology with an explicit named group route."""
from datetime import datetime, timedelta

import pytest

pytest_plugins = ('test_analysis_startup_evidence_pg',)

from test_analysis_startup_evidence_pg import record
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_locator import SnapshotGroupRoute


@pytest.mark.parametrize('after_event', [False, True])
def test_snapshot_read_precedes_original_event(startup_case, monkeypatch, after_event):
    conn, analysis, claimed, _ = startup_case
    snapshot = analysis._phase(conn, claimed, lambda snapshot, *args: snapshot)
    event_at = datetime.fromisoformat(snapshot['source']['events'][0]['created_at'])
    cutoff = event_at + timedelta(seconds=1 if after_event else -1)
    ref = PipelineExactRef(resourceType='PipelineRuntimeControlRevision',
        resourceId='pipeline-control-12345678-1234-1234-1234-123456789abc',
        revision=1, contentHash='sha256:'+'a'*64)
    journal = analysis.source.reader._journal
    journal._ref = ref
    group = SnapshotGroupRoute('12345678-1234-1234-1234-123456789abc', analysis.source.actor,
        ((ref, journal._run_id),), 'sha256:'+'b'*64, cutoff-timedelta(seconds=1), cutoff)
    monkeypatch.setattr(analysis, '_source_group', lambda db: group)
    if after_event:
        with pytest.raises(ValueError, match='chronology differs'):
            record(startup_case)
        assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-startup-lineage'").fetchone()['n'] == 0
    else:
        first = record(startup_case)
        assert record(startup_case) == first
        assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-startup-lineage'").fetchone()['n'] == 1
