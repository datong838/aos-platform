from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from a0v_firstchain_eval_contracts import require_lineage
from aos_api.aip_eval_contracts import AssetRevisionRef


@pytest.mark.parametrize('fault', ['expired', 'future', 'target', 'hash', 'revoked', 'event', 'gate', 'draft', 'tenant', None])
def test_exact_current_publication_lineage(fault):
    now = datetime(2026, 9, 12, tzinfo=UTC)
    skill = NS(lifecycle=NS(value='published'), parent_ref=NS(asset_id='s',revision=1,content_hash='a'*64),
        publication_tenant=NS(org_id='org-org', project_id='dev-project'),
        release_gate_ref=NS(content_hash='b'), publication_ref=NS(resource_id='e',revision='p'))
    gate = NS(status=NS(value='passed'),decided_at=now-timedelta(hours=1),expires_at=now+timedelta(hours=1),
        decision_hash='b',target=AssetRevisionRef(asset_type='skill_template',asset_id='s',revision='1',content_hash='a'*64),decision_id='g')
    event = {'event_id':'e','publication_id':'p','release_gate_decision_id':'g','event_type':'published',
        'target_ref':gate.target.model_dump(mode='json')}
    if fault == 'expired': gate.expires_at=now
    if fault == 'future': gate.decided_at=now+timedelta(seconds=1)
    if fault == 'target': gate.target.asset_id='another'
    if fault == 'hash': gate.decision_hash='changed'
    if fault == 'revoked': event['event_type']='revoked'
    if fault == 'event': event['event_id']='new-event'
    if fault == 'gate': event['release_gate_decision_id']='other-gate'
    if fault == 'draft': skill.lifecycle.value='evaluated'
    if fault == 'tenant': skill.publication_tenant.org_id='dev-org'
    if fault:
        with pytest.raises(ValueError, match='LINEAGE_INVALID'):
            require_lineage(skill,gate,event,now)
    else:
        require_lineage(skill,gate,event,now)
