"""Read original media authority in the restored tenant, never manufacture refs."""
import hashlib
import json
import sys
from pathlib import Path

import psycopg

sys.path[:0] = ['services/aos-api', '.evidence/qyh-source-boundary-rehearsal-20261011',
               '.evidence/qyh-full-system-restoration-20261011']
import real_contract as C
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_production_contracts import RegisterMediaGateProfileRequest
from aos_api.aip_production_contract_store import canonical_hash

root = Path('.evidence/qyh-media-restored-authority-20261012')
output = root / 'result.json'
assert not output.exists(), 'read-only audit output exists; reconcile instead of overwrite'
before = C.S.P.M.fingerprint('qyh-restored-pg-20261011')
metadata = C.S.D.metadata('qyh-restored-pg-20261011')
reads = []
for scope in [('org-org', 'dev-project'), ('dev-org', 'dev-project')]:
    with T.factory() as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        apply_asset_transaction_scope(conn, org_id=scope[0], project_id=scope[1])
        identity = conn.execute("SELECT current_user AS role,current_database() AS db,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation FROM pg_control_system()").fetchone()
        assert identity == dict(role='aos_runtime', db='aos_meta_head',
                               cluster='7695302940039200809', readonly='on', isolation='repeatable read')
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_159'
        totals = {}
        for table in ['aip_review_rule_revision', 'aip_media_gate_profile_revision',
                      'aip_media_gate_set_decision', 'aip_eval_contract_revision']:
            totals[table] = conn.execute(f'SELECT count(*) AS count FROM public.{table} WHERE org_id=%s AND project_id=%s', scope).fetchone()['count']
        profiles = []
        rows = conn.execute('SELECT profile_id,revision,source_bundle_ref,signature_ref,policy_ref,gates,content_hash FROM public.aip_media_gate_profile_revision WHERE org_id=%s AND project_id=%s ORDER BY profile_id,revision LIMIT 16', scope).fetchall()
        assert totals['aip_media_gate_profile_revision'] <= 16, 'bounded audit cannot claim complete profile inventory'
        for row in rows:
            body = RegisterMediaGateProfileRequest.model_validate(dict(
                profileId=row['profile_id'], revision=row['revision'],
                sourceBundleRef=row['source_bundle_ref'], signatureRef=row['signature_ref'],
                policyRef=row['policy_ref'], gates=row['gates']))
            payload = body.model_dump(mode='json', by_alias=True)
            payload['gates'] = sorted(payload['gates'], key=lambda gate: gate['gateId'])
            assert canonical_hash(payload) == row['content_hash']
            profiles.append(dict(profileHash=row['content_hash'], source=payload['sourceBundleRef'],
                                 signature=payload['signatureRef'], policy=payload['policyRef'],
                                 gates=payload['gates']))
        reads.append(dict(scope=scope, identity=identity, totals=totals, profiles=profiles))
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == before
assert C.S.D.metadata('qyh-restored-pg-20261011') == metadata
body = dict(authority='AOS-001904', reads=reads, databaseWrites=0,
            current647DataAndMetadataUnchanged=True, formalRestorationAccepted=False,
            sourceProducerAuthorityGranted=False, providerCalls=0,
            scriptHash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with output.open('x') as file:
    json.dump(body, file, indent=2)
    file.write('\n')
print(json.dumps(body))
