"""Reconcile three retained installation leaves through the current reader."""
import json
import release_transition as T

IDS = ['ef5bc0c3-1dbe-4659-b839-2350f70232bf',
       '89975129-7e0f-4860-ac56-7a031ebe4a1a',
       '407059df-6f1f-4927-acd7-8e388692838e']

if __name__ == '__main__':
    output = T.R / 'current-installation-entry-live-audit.json'
    assert not output.exists(), 'Existing audit: reconcile, not overwrite'
    results = []
    for installation_id in IDS:
        try:
            report = T.H.select_current_installation(
                identity_file=T.R / 'private/restored-identity.json',
                bundle_root=T.LEGACY_ROOT, trust_roots_file=T.TRUST,
                installation_id=installation_id)
        except T.H.RestorationBlocked as exc:
            results.append({'installationId': installation_id, 'acceptedCurrent': False,
                            'reason': str(exc), 'sourceTree': 'retained signed releases'})
        else:
            assert report['apiStartAuthorized'] is False
            results.append({'installationId': installation_id, 'acceptedCurrent': True,
                            'apiStartAuthorized': False})
    assert len(results) == 3
    identity = T.H.preflight(T.R / 'private/restored-identity.json')
    T.record(output.name, {'outcome': 'THREE_RETAINED_INSTALLATIONS_CURRENT_ENTRY_READONLY_AUDIT',
        'identity': identity['identity'], 'results': results, 'databaseWrites': 0,
        'unknownEffectReplay': False, 'apiStarted': False, 'runtimeHostEnabled': False,
        'currentPublishedInstallationProven': any(r['acceptedCurrent'] for r in results),
        'eightPagesAccepted': False})
    print(json.dumps(results, ensure_ascii=False))
