"""BG-00 exact publication options are read-only and tenant scoped."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_skill_publication_options import SkillPublicationOptionsReader
from aos_api.routers import phase3_aip_skills
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope('org-org', 'dev-project')
NOW = datetime(2026, 9, 28, tzinfo=UTC)
HASH = 'a' * 64


def _target():
    return {'assetType': 'skill_template', 'assetId': 'ecommerce.skill.D01',
            'revision': '1', 'contentHash': HASH}


def _reader(*, source=True, event_rows=None, logic_rows=None, routes=None):
    seen = []
    class Connection:
        def execute(self, query, params=None):
            seen.append((query, params))
            if 'FROM aip_skill_template_revision' in query:
                return SimpleNamespace(fetchone=lambda: None if not source else {
                    'skill_id': 'ecommerce.skill.D01', 'revision': 1,
                    'lifecycle': 'evaluated', 'content_hash': HASH,
                    'canonical_logic_id': 'ecommerce.logic.D01'})
            if 'clock_timestamp()' in query:
                return SimpleNamespace(fetchone=lambda: {'now': NOW})
            if 'FROM aip_release_gate_decision' in query:
                return SimpleNamespace(fetchall=lambda: event_rows or [])
            if 'FROM aip_logic_publication' in query:
                return SimpleNamespace(fetchall=lambda: logic_rows or [])
            raise AssertionError('unexpected publication read')
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    route_ref = VersionedAssetRef(assetType='ModelRouteRevision',
        assetId='route-1', revision=1, contentHash=HASH)
    policy_ref = VersionedAssetRef(assetType='RuntimePolicyRevision',
        assetId='policy-1', revision=1, contentHash=HASH)
    class Runtime:
        def list_current_assets(self, scope, kind):
            assert scope == SCOPE and kind == 'model_route'
            return routes or []
        def get_route(self, scope, identity, revision):
            assert (scope, identity, revision) == (SCOPE, 'route-1', 1)
            return SimpleNamespace(content_hash=HASH, runtime_policy_ref=policy_ref)
    authority = SimpleNamespace(require_ready=lambda *args, **kwargs: True)
    return SkillPublicationOptionsReader(connect, runtime_store=Runtime(),
                                         route_authority=authority), seen, route_ref


def test_publication_options_endpoint_uses_authenticated_scope_and_no_write():
    calls = []
    def read(scope, skill_id, revision):
        calls.append((scope.key, skill_id, revision))
        return {'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
                'skillId': skill_id, 'revision': revision,
                'releaseCandidates': [], 'logicCandidates': [],
                'routeCandidates': [], 'blockers': ['RELEASE_GATE_MISSING']}
    principal = type('Principal', (), {'org_id': 'org-org', 'project_id': 'dev-project'})()
    result = phase3_aip_skills.publication_options(
        'ecommerce.skill.D01', 1, principal=principal, service=type('Service', (), {'read': staticmethod(read)})())
    assert result.blockers == ['RELEASE_GATE_MISSING']
    assert calls == [(('org-org', 'dev-project'), 'ecommerce.skill.D01', 1)]
    from aos_api.main import app
    assert '/v1/aip/skills/{skill_id}/revisions/{revision}/publication-options' in app.openapi()['paths']


def test_empty_options_are_explicit_and_never_synthesized():
    reader, seen, _ = _reader()
    options = reader.read(SCOPE, 'ecommerce.skill.D01', 1)
    assert options.release_candidates == [] and options.logic_candidates == []
    assert options.route_candidates == []
    assert options.blockers == ['RELEASE_PUBLICATION_UNAVAILABLE',
                                'LOGIC_PUBLICATION_UNAVAILABLE',
                                'MODEL_ROUTE_UNAVAILABLE']
    assert all(query.lstrip().startswith('SELECT') for query, _ in seen)
    assert all(params is None or params[:2] != ('dev-org', 'dev-project')
               for _, params in seen)
    with pytest.raises(LookupError, match='Skill revision unavailable'):
        _reader(source=False)[0].read(SCOPE, 'ecommerce.skill.D01', 1)


def test_only_exact_unrevoked_release_and_active_route_are_choices():
    base = {'decision_id': 'gate-1', 'gate_target': _target(),
            'status': 'passed', 'invalidated_by': None,
            'decided_at': NOW - timedelta(minutes=1),
            'expires_at': NOW + timedelta(minutes=1),
            'publication_id': 'pub-1', 'event_target': _target(),
            'release_gate_decision_id': 'gate-1'}
    route_ref = VersionedAssetRef(assetType='ModelRouteRevision',
        assetId='route-1', revision=1, contentHash=HASH)
    routes = [SimpleNamespace(lifecycle=SimpleNamespace(value='active'),
                              ref=route_ref)]
    logic = [{'graph_id': 'ecommerce.logic.D01',
              'graph_revision': 2, 'graph_hash': HASH}]
    reader, _, _ = _reader(event_rows=[{**base, 'event_type': 'published'}],
                           logic_rows=logic, routes=routes)
    options = reader.read(SCOPE, 'ecommerce.skill.D01', 1)
    assert options.blockers == []
    assert options.release_candidates[0].publication_id == 'pub-1'
    assert options.logic_candidates[0].asset_id == 'ecommerce.logic.D01'
    assert options.route_candidates[0].route_ref == route_ref

    revoked, _, _ = _reader(event_rows=[{**base, 'event_type': 'published'},
                                     {**base, 'event_type': 'revoked'}],
                            logic_rows=logic, routes=routes)
    assert revoked.read(SCOPE, 'ecommerce.skill.D01', 1).release_candidates == []
