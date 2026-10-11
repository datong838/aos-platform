"""Actual cached OCI/schema candidate qualification, never Registry publication."""
import json
from datetime import UTC, datetime
import release_transition as T
from prepare_public_bundle_root import OUTPUT, fingerprints
from aos_api.asset_registry import control_wiring
from aos_api.asset_registry.composition_contracts import CompositionRequest, RegistrySnapshot
from aos_api.asset_registry.resolver import resolve
from aos_api.extension_runtime.admission import admit_runtime_artifact
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.schema_conditions import admit_schema_requirements
from aos_api.extension_runtime.schema_registry import require_installed
import os

if __name__ == '__main__':
    assert not (T.R / 'mixed-candidate-qualification-intent.json').exists(), 'Existing attempt: reconcile only'
    identity = T.H.preflight(T.R / 'private/restored-identity.json')
    assert json.loads((T.R / 'selected-public-root-terminal.json').read_text())['outcome'] == \
        'FOUR_SELECTED_PUBLIC_RELEASES_EXACT_ROOT_GREEN'
    before = fingerprints(OUTPUT)
    os.environ['AOS_BUNDLE_ROOT'] = str(OUTPUT)
    trust = T.FileTrustRootProvider(T.TRUST).snapshot()
    loader = T.ManifestLoader(control_wiring._allowlist_roots(repository_root=T.ROOT), trust_roots=trust)
    policy = T.ReleasePolicy(trust_roots=trust)
    builder = T.OLD._load_builder()
    candidates, bundles = [], {}
    for alias, bundle_id, version, retained in T.CASES:
        bundle = loader.load(f'bundle://{alias}/{bundle_id}/{version}')
        bundles[bundle_id] = bundle
    # Loader evidence is observed during loading. Freeze evaluation time after
    # all reads, never before the evidence that the policy checks.
    now = datetime.now(UTC)
    for bundle in bundles.values():
        record = builder._release_record(bundle)
        # This is the original diagnostic candidate projection, not a write or
        # assertion that the two validated Registry records are published.
        approved = policy.evaluate(record, checked_at=now)
        candidates.append(builder._snapshot_candidate(bundle, approved))
    snapshot = RegistrySnapshot.build(candidates=candidates, checked_at=now)
    request = CompositionRequest.model_validate({'requested': [
        {'publisher': 'aos', 'id': bid, 'version': bundles[bid].manifest.metadata.version}
        for bid in ('platform.ecommerce.niushop', 'solution.ecommerce.operations-base', 'solution.ecommerce.growth')],
        'platformApiVersion': '1.7.0', 'platformRelease': 'aos-platform/1.7.0',
        'environment': 'dev', 'registrySnapshotHash': snapshot.snapshot_hash, 'currentInstallationRef': None})
    composition = resolve(request, snapshot, None)
    selected = {r.id: r for r in composition.resolved}
    driver = OciDriver(context=T.H.CONTEXT)
    admissions, requirements = {}, {}
    for bid, bundle in bundles.items():
        if bundle.manifest.spec.runtime is None:
            continue
        root = OUTPUT / bid / bundle.manifest.metadata.version
        record = builder._release_record(bundle)
        artifact = admit_runtime_artifact(record=record, selected=selected[bid], policy=policy,
            checked_at=now, read_artifact=lambda path, limit, root=root: (root / path).read_bytes(),
            platform='linux/arm64', driver=driver)
        required = admit_schema_requirements(record=record, selected=selected[bid], policy=policy,
            checked_at=now, read_artifact=lambda path, limit, root=root: (root / path).read_bytes())
        assert len(required) == 1
        with T.factory() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            require_installed(conn, required)
        admissions[bid] = {'imageId': artifact.image_id, 'packageHash': artifact.package_hash}
        requirements[bid] = [{'packageId': r.package_id, 'schemaVersion': r.schema_version,
                              'migrationHash': r.migration_hash} for r in required]
    assert len(admissions) == 3
    driver.require_isolation()
    T.record('mixed-candidate-qualification-intent.json', {'task': 'qyh-full-system-restoration-20261011',
        'candidateDiagnosticOnly': True, 'admissions': admissions, 'schemaRequirements': requirements,
        'databaseWrites': 0, 'businessCalls': 0, 'providerCalls': 0,
        'registryStatusNotOverridden': True, 'network': 'none'})
    sessions = {}
    for bid, item in admissions.items():
        sessions[bid] = builder._qualify_session(driver=driver, image_id=item['imageId'],
            contributions=bundles[bid].manifest.spec.contributions,
            journal_root=T.R / 'mixed-qualification-session-journal')
    assert fingerprints(OUTPUT) == before
    T.record('mixed-candidate-qualification-terminal.json', {
        'outcome': 'SELECTED_MIXED_OCI_AND_SCHEMA_DIAGNOSTIC_GREEN',
        'candidateDiagnosticOnly': True, 'resolved': [{'id': r.id, 'version': r.version} for r in composition.resolved],
        'admissions': admissions, 'schemaRequirements': requirements, 'sessions': sessions,
        'selectedFilesUnchanged': True, 'databaseWrites': 0, 'registryPublishes': 0,
        'businessCalls': 0, 'providerCalls': 0, 'apiStarted': False, 'eightPagesAccepted': False,
        'runtimeAuthority': False})
    print('SELECTED_MIXED_OCI_AND_SCHEMA_DIAGNOSTIC_GREEN')
