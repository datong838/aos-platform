"""Read-only reconciliation after terminal Registry create/validate operations."""
import json
import release_transition as T

if __name__ == '__main__':
    output = T.R / 'registry-two-validated-readonly-reconciliation.json'
    assert not output.exists(), 'Existing result: never overwrite'
    preflight = T.H.preflight(T.R / 'private/restored-identity.json')
    trust = T.FileTrustRootProvider(T.TRUST).snapshot()
    loader = T.ManifestLoader({'a0v-canonical': T.LEGACY_ROOT,
        'a0v-qyh-current': T.CURRENT / 'signed-bundles'}, trust_roots=trust)
    store = T.PostgresRegistryStore(connect_factory=T.factory)
    rows = []
    for alias, bundle_id, version, retained in T.CASES:
        bundle = loader.load(f'bundle://{alias}/{bundle_id}/{version}')
        existing = store.get_version(bundle_id, version, publisher='aos')
        T.OLD.assert_registry_version_exact(existing, T.OLD._expected_registry_version(bundle))
        assert existing['signature'] == bundle.signature.model_dump(mode='json', by_alias=True)
        assert existing['status'] == ('published' if retained else 'validated')
        if not retained:
            assert not any(e['toStatus'] == 'published' for e in existing['lifecycleEvents'])
        rows.append({'id': bundle_id, 'version': version, 'status': existing['status'],
                     'contentHash': existing['contentHash'], 'retained': retained})
    before = {r['table']: r for r in json.loads(
        (T.R / 'volume-fingerprint-after-name.json').read_text())}
    after = {r['table']: r for r in T.P.M.fingerprint(T.H.TARGET)}
    assert before.keys() == after.keys() and len(after) == 647
    changed = sorted(k for k in before if before[k] != after[k])
    allowed = {'asset_bundle_version', 'asset_bundle_version_event',
               'asset_bundle_dependency', 'asset_bundle_artifact', 'asset_bundle_evidence'}
    assert all(k.split('.')[-1] in allowed for k in changed), changed
    T.record(output.name, {'outcome': 'TWO_CURRENT_VALIDATED_NO_PUBLISH_DATA_RECONCILED',
        'identity': preflight['identity'], 'versions': rows, 'tables': 647,
        'changedTables': changed, 'otherTablesExact': True,
        'databaseWrites': 0, 'unknownWriteResult': False, 'replayPerformed': False,
        'apiStarted': False, 'eightPagesAccepted': False, 'runtimeAuthority': False})
    print('TWO_CURRENT_VALIDATED_NO_PUBLISH_DATA_RECONCILED')
