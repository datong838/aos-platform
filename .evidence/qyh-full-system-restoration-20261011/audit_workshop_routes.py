"""Reconcile original tenant catalog sources without enabling installations."""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone

import release_transition as T
from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource


@contextmanager
def readonly_factory():
    with T.factory() as conn:
        conn.read_only = True
        yield conn


def read_scope(org_id):
    source = PostgresWorkshopCatalogSource(connect_factory=readonly_factory)
    result = {}
    for name, reader in [('legacy', source.read_active_bundles),
                         ('runtimeCandidates', source.read_runtime_candidate_bundles)]:
        try:
            rows = reader(org_id=org_id, project_id='dev-project', markings=[])
            result[name] = [{'installationId': row.installation_id,
                'activeRevision': row.active_revision,
                'bundleId': row.bundle.bundle_id, 'version': row.bundle.version,
                'status': row.bundle.status, 'contentHash': row.bundle.content_hash,
                'runtimeDeclared': row.bundle.manifest.spec.runtime is not None}
                for row in rows]
        except Exception as exc:
            # Error class only: never expose raw database payload or credentials.
            result[name] = {'errorType': type(exc).__name__, 'accepted': False}
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


if __name__ == '__main__':
    output = T.R / 'workshop-route-source-audit.json'
    assert not output.exists(), 'Reconcile existing result; do not overwrite'
    identity = T.H.preflight(T.R / 'private/restored-identity.json')
    positive = read_scope('org-org')
    positive_repeat = read_scope('org-org')
    canary = read_scope('dev-org')
    canary_repeat = read_scope('dev-org')
    report = {'outcome': 'RESTORED_WORKSHOP_ORIGINAL_SOURCES_READONLY_AUDIT',
        'observedAt': datetime.now(timezone.utc).isoformat(),
        'identity': identity['identity'], 'positive': positive, 'canary': canary,
        'independentReadsStable': digest(positive) == digest(positive_repeat)
            and digest(canary) == digest(canary_repeat),
        'databaseWrites': 0, 'bindingsEnabled': False, 'apiStarted': False,
        'eightPagesAccepted': False, 'candidateIsExecutionAuthority': False}
    T.record(output.name, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
