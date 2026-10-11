"""Current limited-login metadata audit; no old collector or permission replay."""
import hashlib
import json
from uuid import UUID
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.extension_runtime.configuration_store import _decode

IDS = ['ef5bc0c3-1dbe-4659-b839-2350f70232bf',
       '89975129-7e0f-4860-ac56-7a031ebe4a1a',
       '407059df-6f1f-4927-acd7-8e388692838e']
SOURCES = {
    'aip.responsibility_plan_revision': ('aip_responsibility_plan', 'plan_id'),
    'aip.runtime_policy_revision': ('aip_runtime_policy', 'runtime_policy_id'),
    'aip.budget_revision': ('aip_budget', 'budget_id'),
}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def configuration_rows(conn):
    return conn.execute('''SELECT c.installation_id,c.generation,c.configuration_id,
        c.revision,c.payload,c.content_hash,c.previous_hash,c.actor,
        b.revision AS binding_revision,b.enabled,b.operation_fence,b.config_ref
        FROM extension_runtime_configuration c JOIN extension_runtime_binding b
        ON b.org_id=c.org_id AND b.project_id=c.project_id
        AND b.installation_id=c.installation_id AND b.generation=c.generation
        WHERE c.org_id=%s AND c.project_id=%s AND c.installation_id=ANY(%s::uuid[])
        ORDER BY c.installation_id,c.generation,c.revision''',
        ('org-org', 'dev-project', IDS)).fetchall()

if __name__ == '__main__':
    output = T.R / 'restored-current-configuration-audit.json'
    assert not output.exists(), 'Existing result: do not overwrite'
    identity = T.H.preflight(T.R / 'private/restored-identity.json')
    with T.factory() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        apply_asset_transaction_scope(conn, org_id='org-org', project_id='dev-project')
        observed = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        rows = configuration_rows(conn)
        assert len(rows) == 3 and {str(r['installation_id']) for r in rows} == set(IDS)
        before = digest(rows)
        results = []
        for row in rows:
            target = ('org-org', 'dev-project', row['installation_id'], row['generation'])
            ref, document = _decode(target, row)
            assert row['enabled'] is False and row['operation_fence'] is True
            checks = []
            for purpose, refs in [('role', document.roleRefs), ('data', document.dataRefs),
                                  ('budget', (document.budgetRef,)), ('policy', (document.policyRef,))]:
                for source in refs:
                    head = None
                    if source.authority in SOURCES:
                        base, key = SOURCES[source.authority]
                        # Only immutable static table identifiers interpolate;
                        # every opaque source identity is a SQL parameter.
                        head = conn.execute(f'''SELECT h.current_revision,r.revision,r.content_hash,r.lifecycle
                            FROM {base}_head h JOIN {base}_revision r
                            ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.{key}=h.{key}
                            AND r.revision=h.current_revision
                            WHERE h.org_id=%s AND h.project_id=%s AND h.{key}=%s''',
                            ('org-org', 'dev-project', source.id)).fetchone()
                    elif source.authority == 'aip.data_classification_policy_revision':
                        head = conn.execute('''SELECT h.current_revision,r.revision,r.content_hash,r.lifecycle,
                            r.effective_from,r.effective_until,
                            (r.effective_from<=%s AND r.effective_until>%s) AS effective_now
                            FROM aip_runtime_guard_policy_head h JOIN aip_runtime_guard_policy_revision r
                            ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.policy_kind=h.policy_kind
                            AND r.policy_id=h.policy_id AND r.revision=h.current_revision
                            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='data_classification'
                            AND h.policy_id=%s''', (observed, observed, 'org-org', 'dev-project', source.id)).fetchone()
                    checks.append({'purpose': purpose, 'authority': source.authority,
                        'sourceId': source.id, 'referencedRevision': source.revision,
                        'referencedHash': source.hash,
                        'head': head, 'headRefExact': bool(head and head['revision'] == source.revision
                            and 'sha256:' + head['content_hash'] == source.hash)})
            policy = conn.execute('''SELECT payload->'budgetPolicyRef' AS ref
                FROM aip_runtime_policy_revision WHERE org_id=%s AND project_id=%s
                AND runtime_policy_id=%s AND revision=%s''',
                ('org-org', 'dev-project', document.policyRef.id, document.policyRef.revision)).fetchone()
            assert policy is not None and isinstance(policy['ref'], dict)
            budget_ref = policy['ref']
            budget = conn.execute('''SELECT h.current_revision,r.revision,r.content_hash,r.lifecycle,
                r.effective_from,r.effective_until,
                (r.effective_from<=%s AND r.effective_until>%s) AS effective_now
                FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r
                ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.policy_kind=h.policy_kind
                AND r.policy_id=h.policy_id AND (r.revision=%s OR r.revision=h.current_revision)
                WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget' AND h.policy_id=%s
                ORDER BY r.revision''', (observed, observed, budget_ref['revision'],
                    'org-org', 'dev-project', budget_ref['assetId'])).fetchall()
            results.append({'installationId': str(row['installation_id']),
                'generation': str(row['generation']), 'configurationRef': ref.model_dump(mode='json'),
                'hashVerifiedByOriginalDecoder': True, 'bindingDisabledFenced': True,
                'roleRefCount': len(document.roleRefs), 'dataRefCount': len(document.dataRefs),
                'sourceChecks': checks, 'policyBudgetRef': budget_ref, 'budgetWindows': budget,
                'currentOwnerVerified': False, 'currentConfigurationPermissionVerified': False})
        assert digest(configuration_rows(conn)) == before
    T.record(output.name, {'outcome': 'RESTORED_CURRENT_CONFIGURATION_METADATA_READONLY_AUDIT',
        'identity': identity['identity'], 'observedAt': observed, 'configurations': results,
        'configurationAndBindingRowsUnchanged': True, 'originalDecoderUsed': True,
        'databaseWrites': 0, 'marketplaceSourceReads': 0, 'credentialReads': 0,
        'currentRuntimeAuthorization': False, 'eightPagesAccepted': False})
    print('RESTORED_CURRENT_CONFIGURATION_METADATA_READONLY_AUDIT')
