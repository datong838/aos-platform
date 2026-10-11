"""Metadata-only candidate recovery inputs; no admission or execution replay."""
import release_transition as T
import audit_restored_configuration as A
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope

SCOPE = ('org-org', 'dev-project')
DEPENDENCIES = {
    'networkPolicyRef': ('aip_network_policy', None),
    'egressPolicyRef': ('aip_runtime_guard_policy', 'egress'),
    'dataClassificationPolicyRef': ('aip_runtime_guard_policy', 'data_classification'),
    'quotaPolicyRef': ('aip_model_governance_policy', 'quota'),
    'budgetPolicyRef': ('aip_model_governance_policy', 'budget'),
}

if __name__ == '__main__':
    name = 'restored-configuration-dependency-audit.json'
    assert not (T.R / name).exists(), 'Existing result: reconcile only'
    identity = T.H.preflight(T.R / 'private/restored-identity.json')
    with T.factory() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        apply_asset_transaction_scope(conn, org_id=SCOPE[0], project_id=SCOPE[1])
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        before = A.digest(A.configuration_rows(conn))
        results = []
        for installation_id in A.IDS:
            row = conn.execute('''SELECT h.current_revision,r.content_hash,
                r.payload->'networkPolicyRef' AS "networkPolicyRef",
                r.payload->'egressPolicyRef' AS "egressPolicyRef",
                r.payload->'dataClassificationPolicyRef' AS "dataClassificationPolicyRef",
                r.payload->'quotaPolicyRef' AS "quotaPolicyRef",
                r.payload->'budgetPolicyRef' AS "budgetPolicyRef"
                FROM extension_runtime_configuration c
                JOIN aip_runtime_policy_head h ON h.org_id=c.org_id AND h.project_id=c.project_id
                    AND h.runtime_policy_id=c.payload->'policyRef'->>'id'
                JOIN aip_runtime_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                    AND r.runtime_policy_id=h.runtime_policy_id AND r.revision=h.current_revision
                WHERE c.org_id=%s AND c.project_id=%s AND c.installation_id=%s''',
                (*SCOPE, installation_id)).fetchall()
            assert len(row) == 1, 'Expected one retained configuration and current policy'
            current = row[0]
            checks = []
            for key, (base, kind) in DEPENDENCIES.items():
                ref = current[key]
                assert isinstance(ref, dict), 'Missing actual current policy dependency'
                kind_sql = 'AND h.policy_kind=%s' if kind else ''
                kind_join = 'AND r.policy_kind=h.policy_kind' if kind else ''
                parameters = (now, now, *SCOPE, ref['assetId']) + ((kind,) if kind else ())
                head = conn.execute(f'''SELECT h.current_revision,r.content_hash,r.lifecycle,
                    r.effective_from,r.effective_until,
                    (r.effective_from<=%s AND r.effective_until>%s) AS effective_now
                    FROM {base}_head h JOIN {base}_revision r
                    ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.policy_id=h.policy_id
                    AND r.revision=h.current_revision {kind_join}
                    WHERE h.org_id=%s AND h.project_id=%s AND h.policy_id=%s {kind_sql}''',
                    parameters).fetchone()
                checks.append({'dependency': key, 'reference': ref, 'head': head,
                    'currentRefExact': bool(head and head['current_revision'] == ref['revision']
                        and head['content_hash'] == ref['contentHash'])})
            operations = conn.execute('''SELECT kind,status,phase,count(*) AS count
                FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s
                AND installation_id=%s GROUP BY kind,status,phase ORDER BY kind,status,phase''',
                (*SCOPE, installation_id)).fetchall()
            schedules = conn.execute('''WITH latest AS (
                SELECT DISTINCT ON(schedule_id) schedule_id,installation_id
                FROM pipeline_schedule_control_binding WHERE org_id=%s AND project_id=%s
                ORDER BY schedule_id,revision DESC)
                SELECT m.id,m.enabled,
                (SELECT count(*) FROM meta_schedule_run r WHERE r.org_id=m.org_id
                    AND r.project_id=m.project_id AND r.schedule_id=m.id) AS retained_run_count,
                (SELECT count(*) FROM meta_schedule_run r WHERE r.org_id=m.org_id
                    AND r.project_id=m.project_id AND r.schedule_id=m.id
                    AND r.executor_stopped IS NOT TRUE) AS executor_stop_unproven_count
                FROM latest l JOIN meta_schedule m ON m.id=l.schedule_id
                WHERE l.installation_id=%s AND m.org_id=%s AND m.project_id=%s ORDER BY m.id''',
                (*SCOPE, installation_id, *SCOPE)).fetchall()
            results.append({'installationId': installation_id,
                'currentRuntimePolicyRevision': current['current_revision'],
                'dependencyMetadataChecks': checks, 'operationStateCounts': operations,
                'currentScheduleAssociations': schedules,
                'formalAdmissionChecked': False, 'replayAuthorized': False})
        assert A.digest(A.configuration_rows(conn)) == before
    T.record(name, {'outcome': 'RESTORED_CONFIGURATION_DEPENDENCY_METADATA_AUDIT',
        'observedAt': now, 'identity': identity['identity'], 'installations': results,
        'databaseWrites': 0, 'businessPayloadReads': 0, 'oldExecutorsInvoked': 0,
        'configurationAndBindingRowsUnchanged': True, 'formalOwnerVerified': False,
        'productionLockingReadersNotInvoked': True, 'runtimeAuthorization': False})
    print('RESTORED_CONFIGURATION_DEPENDENCY_METADATA_AUDIT')
