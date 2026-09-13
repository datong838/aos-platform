from contextlib import nullcontext
from datetime import UTC, datetime
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.ui_resource_reader import PublishedUiResourceReader
from .test_manifest_loader import _make_bundle, _manifest, _loader, _sign_bundle, _write_release_evidence


@pytest.fixture
def case(tmp_path):
    html = b'<!doctype html><html><body>signed entry</body></html>'
    ui = dict(schemaVersion='aos.dev/frontend-runtime/v1alpha1', title='经营参谋',
              entrypoint='frontend/index.html', initialRoute='/workshop/analyst',
              routeClaims=['/workshop/analyst'], readOperationClaims=['analyst_workspace_view_v1'],
              commandOperationClaims=[])
    ui_bytes = json.dumps(ui).encode()
    manifest = _manifest()
    manifest['spec']['runtime'] = dict(apiVersion='aos.dev/bundle-runtime/v1alpha1',
        frontend=dict(manifest='frontend/manifest.json', artifactHash='sha256:' + sha256(ui_bytes).hexdigest()))
    bundle = _make_bundle(tmp_path, manifest=manifest)
    (bundle / 'frontend').mkdir()
    (bundle / 'frontend/manifest.json').write_bytes(ui_bytes)
    (bundle / 'frontend/index.html').write_bytes(html)
    (bundle / 'frontend/hidden.html').write_text('not declared')
    _write_release_evidence(bundle, sbom={'format': 'CycloneDX', 'components': []},
                            evals={'status': 'passed', 'failed': 0, 'passed': 1})
    source = 'bundle://fixtures/example'
    roots = _sign_bundle(bundle, _loader(tmp_path).load(source))
    roots.snapshot = lambda: roots
    loader = _loader(tmp_path, roots)
    loaded = loader.load(source)
    row = dict(publisher='aos', bundle_id='solution.example', version='1.0.0',
        manifest_json=loaded.manifest.model_dump(mode='json', by_alias=True),
        content_hash=loaded.content_hash, signature=loaded.signature.model_dump(mode='json', by_alias=True),
        status='published', artifacts=[a.model_dump(mode='json', by_alias=True) for a in loaded.artifacts],
        evidence=[e.model_dump(mode='json', by_alias=True) for e in loaded.evidence])
    state = SimpleNamespace(queries=0, rows=[row], before_query=None)

    class Connection:
        def execute(self, sql, params=None):
            if 'clock_timestamp' in sql:
                return SimpleNamespace(fetchone=lambda: {'checked_at': datetime.now(UTC)})
            assert 'publisher=%s AND bundle_id=%s AND version=%s LIMIT 2' in sql
            assert params == ('aos', 'solution.example', '1.0.0')
            state.queries += 1
            if state.before_query:
                state.before_query(state.queries)
            return SimpleNamespace(fetchall=lambda: state.rows)

    reader = PublishedUiResourceReader(connect_factory=lambda: nullcontext(Connection()),
        release_policy=ReleasePolicy(trust_roots=roots), loader=loader)
    args = dict(publisher='aos', bundle_id='solution.example', version='1.0.0',
        entrypoint='frontend/index.html', package_hash=loaded.content_hash,
        content_hash='sha256:' + sha256(html).hexdigest())
    return SimpleNamespace(reader=reader, args=args, html=html, bundle=bundle,
                           state=state, roots=roots, loader=loader, row=row)


def test_exact_signed_html_and_two_release_checks(case):
    assert case.reader.read(**case.args) == case.html
    assert case.state.queries == 2


@pytest.mark.parametrize('changes', [
    {'entrypoint': 'backend/main.py'}, {'entrypoint': 'frontend/../index.html'},
    {'publisher': 'aos/evil'}, {'version': '../1.0.0'}, {'content_hash': 'bad'},
])
def test_invalid_request_rejected_before_registry(case, changes):
    with pytest.raises(ValueError):
        case.reader.read(**(case.args | changes))
    assert case.state.queries == 0


@pytest.mark.parametrize('changes', [
    {'entrypoint': 'frontend/hidden.html'},
    {'content_hash': 'sha256:' + 'a' * 64}, {'package_hash': 'sha256:' + 'b' * 64},
])
def test_unclaimed_or_wrong_digest_not_served(case, changes):
    with pytest.raises(LookupError):
        case.reader.read(**(case.args | changes))


def test_tampered_file_rejected(case):
    (case.bundle / 'frontend/index.html').write_text('tampered')
    with pytest.raises((ValueError, AssetRegistryError)):
        case.reader.read(**case.args)


def test_symlink_rejected(case, tmp_path):
    target = tmp_path / 'outside.html'
    target.write_text('outside')
    entry = case.bundle / 'frontend/index.html'
    entry.unlink()
    entry.symlink_to(target)
    with pytest.raises(AssetRegistryError):
        case.reader.read(**case.args)


def test_signature_envelope_replacement_rejected(case):
    (case.bundle / 'bundle.signature.json').unlink()
    with pytest.raises(ValueError):
        case.reader.read(**case.args)


def test_revocation_during_file_read_suppresses_response(case):
    def revoke(count):
        if count == 2:
            case.state.rows = []
    case.state.before_query = revoke
    with pytest.raises(LookupError):
        case.reader.read(**case.args)
    assert case.state.queries == 2


def test_current_trust_root_required(case):
    case.roots.get_trust_root = lambda **kwargs: None
    with pytest.raises(AssetRegistryError):
        case.reader.read(**case.args)
    assert case.state.queries == 1


def test_duplicate_registry_identity_rejected(case):
    case.state.rows *= 2
    with pytest.raises(LookupError):
        case.reader.read(**case.args)
