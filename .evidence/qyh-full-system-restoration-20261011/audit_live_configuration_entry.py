"""Reconcile preserved configuration sources through the real read-only API."""
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TASK = Path(__file__).resolve().parent
ROOT = TASK.parents[1]
IDS = ('407059df-6f1f-4927-acd7-8e388692838e',
       '89975129-7e0f-4860-ac56-7a031ebe4a1a',
       'ef5bc0c3-1dbe-4659-b839-2350f70232bf')
SUFFIXES = ('configuration-candidates', 'configuration-sources', 'configurations')


def get(iid, suffix, org='org-org'):
    request = Request(f'http://127.0.0.1:18080/v1/bundle-runtime-installations/{iid}/{suffix}',
        headers={'Authorization': 'Bearer dev', 'X-Org-Id': org, 'X-Project-Id': 'dev-project'})
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def read():
    results = []
    for iid in IDS:
        row = {'installationId': iid}
        for suffix in SUFFIXES:
            status, body = get(iid, suffix)
            assert status == 200, (suffix, status, body.get('code'))
            if suffix == 'configuration-candidates':
                assert body['installationId'] == iid
                row['candidates'] = {k: body[k] for k in
                    ('counts', 'missing', 'allPresent', 'authorityKind', 'installationRevision', 'installationEtag')}
            elif suffix == 'configuration-sources':
                assert body['target']['installationId'] == iid
                row['sources'] = {'target': body['target'], 'installationRevision': body['installationRevision'],
                    'roleRefs': [choice['ref'] for choice in body['roles']],
                    'policyRefs': [choice['ref'] for choice in body['policies']],
                    'submissionConfigured': body['submissionConfigured']}
            else:
                assert body['installationId'] == iid
                row['configurations'] = {'count': len(body['items']), 'hasMore': body['hasMore'],
                    'generation': body['generation'], 'bindingRevision': body['bindingRevision']}
            canary_status, canary = get(iid, suffix, 'dev-org')
            assert canary_status == 404, (suffix, canary_status)
            row.setdefault('canary', {})[suffix] = {'status': canary_status, 'code': canary.get('code')}
        results.append(row)
    return results


if __name__ == '__main__':
    output = TASK / 'live-configuration-entry-audit.json'
    assert not output.exists(), 'Existing result: reconcile only'
    sys.path.insert(0, str(ROOT / 'scripts'))
    entry = importlib.import_module('a0v_qyh_restored_http')
    entry.require_api_source_candidate(TASK / 'management-api-frozen-r4.json')
    identity = entry.preflight(TASK / 'private/restored-identity.json')
    first, second = read(), read()
    assert first == second, 'Current configuration entry changed during independent reads'
    report = {'outcome': 'LIVE_RESTORED_CONFIGURATION_ENTRY_RECONCILED',
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'volume': identity['volume'], 'scope': ['org-org', 'dev-project'], 'rows': first,
        'independentReadsStable': True, 'databaseWrites': 0, 'marketplaceSourceReads': 0,
        'formalOwnerVerified': False, 'formalPublisherVerified': False,
        'eightPagesAccepted': False, 'runtimeAuthorized': False,
        'sourceSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with output.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'outcome': report['outcome'], 'independentReadsStable': True,
        'missing': [row['candidates']['missing'] for row in first],
        'submissionConfigured': [row['sources']['submissionConfigured'] for row in first]}))
