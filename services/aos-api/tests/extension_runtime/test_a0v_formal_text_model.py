from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import json

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import a0v_formal_text_model as publication


def test_changed_plan_is_rejected_before_connecting():
    def forbidden(*args):
        pytest.fail('drifted plan must not open a database')
    with pytest.raises(ValueError, match='FORMAL_MODEL_PLAN_DRIFT'):
        publication.apply_plan(forbidden, {'planHash': '0'*64, 'changed': True})


def test_frozen_renewal_cannot_switch_evidence_or_mode(tmp_path):
    plan = {'renewal': True, 'evidenceDirectory': str(tmp_path / 'evidence')}
    plan['planHash'] = publication.canonical_hash(plan)
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    def forbidden(*args):
        pytest.fail('frozen context drift must not connect')
    with pytest.raises(ValueError, match='CONTEXT_DRIFT'):
        publication.freeze_plan(forbidden, tmp_path)
    with pytest.raises(ValueError, match='CONTEXT_DRIFT'):
        publication.freeze_plan(forbidden, tmp_path, renew=True, evidence_dir=tmp_path / 'other')
    assert publication.freeze_plan(forbidden, tmp_path, renew=True,
        evidence_dir=tmp_path / 'evidence') == plan


def test_renewal_requires_frozen_head_versions_before_any_write():
    plan = {'renewal': True}
    plan['planHash'] = publication.canonical_hash(plan)
    with pytest.raises(ValueError, match='HEAD_VERSIONS_REQUIRED'):
        publication.apply_plan(None, plan)


@pytest.mark.parametrize('fault', ['provider_suspended', 'network_revoked', 'network_expired', 'network_future'])
def test_inactive_current_dependencies_block_before_evidence_read(monkeypatch, fault):
    now = datetime(2026, 9, 11, 4, tzinfo=UTC)
    provider = SimpleNamespace(lifecycle=SimpleNamespace(value='active'), provider_instance_id='p', revision=1, content_hash='a'*64)
    network = SimpleNamespace(lifecycle=SimpleNamespace(value='active'), policy_id='n', revision=1, content_hash='b'*64,
        effective_from=now-timedelta(hours=1), effective_until=now+timedelta(hours=1))
    if fault == 'provider_suspended': provider.lifecycle.value = 'suspended'
    if fault == 'network_revoked': network.lifecycle.value = 'revoked'
    if fault == 'network_expired': network.effective_until = now
    if fault == 'network_future': network.effective_from = now+timedelta(seconds=1)
    monkeypatch.setattr(publication, 'AipModelRuntimeStore', lambda _: SimpleNamespace(get_provider=lambda *a: provider))
    monkeypatch.setattr(publication, 'AipNetworkPolicyStore', lambda _: SimpleNamespace(get=lambda *a: network))
    monkeypatch.setattr(publication, 'read_verified_text_evidence', lambda *a, **k: {'sourceHash': 'verified-old-probe'})
    with pytest.raises(ValueError, match='FORMAL_MODEL_CURRENT_DEPENDENCY_INACTIVE'):
        publication.evidence(None, checked_at=now)
