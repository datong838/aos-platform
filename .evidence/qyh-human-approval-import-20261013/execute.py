"""Import explicit human chat approval through the original installation service.

The actor denotes the real conversation owner; it is not an OIDC login claim.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / '.evidence/qyh-human-approval-import-20261013'
sys.path.insert(0, str(ROOT / '.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.composition_contracts import ApproveInstallationRequest
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator

spec = importlib.util.spec_from_file_location('readonly', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
ro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ro)

def emit(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=str)
        f.write('\n')

assert not (OUT / 'intent.json').exists(), 'Existing attempt: read-only reconcile; do not resend'
tenant = {'org_id': 'org-org', 'project_id': 'dev-project'}
installation = 'ab2fd72f-d81c-400d-bbbc-e1589a159d6b'
actor = 'human:conversation-owner:01a107a2-e9e4-7670-bc44-1144fa9b27e2'
source = json.loads((OUT / 'approval-source.json').read_text())
assert source['approvalKind'] == 'explicit_user_manual_maintenance_approval'
assert source['authenticatedOidcApproval'] is False
assert source['thread'] == actor.split(':', 2)[2]
container = json.loads(subprocess.check_output(['docker', '--context', ro.CONTEXT, 'inspect', ro.SOURCE], text=True, timeout=10))[0]
assert container['Id'] == '84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
assert container['State']['Running'] and container['Mounts'][0]['Name'] == 'aos-qyh-history159-prepared-data-20261011'
assert ro.current_sql('SELECT version_num FROM alembic_version;').strip() == 'a0v_161'
assert ro.current_sql('SELECT system_identifier FROM pg_control_system();').strip() == '7695302940039200809'
assert ro.current_sql('SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;').strip() == '0'
store = PostgresInstallationStore(connect_factory=T.factory)
cs = PostgresCompositionStore(connect_factory=T.factory)
record = store.get_installation(**tenant, installation_id=installation)
assert record.state == 'submitted' and record.etag_version == 2
assert record.current.requested_by == 'user:dev' and record.current.requested_by != actor
old = store.get_installation(**tenant, installation_id='407059df-6f1f-4927-acd7-8e388692838e')
assert old.active_revision == 5
lock = cs.get_lock(**tenant, composition_id=record.current.composition_id, revision=record.current.lock_revision)
assert {(r.id, r.version) for r in lock.payload.resolved} == {(b, v) for _, b, v, _ in T.CASES}
assert len(lock.payload.edges) == 3
assert sum(c.kind == 'ui' and c.slot == 'workshop.primary.ecommerce' for r in lock.payload.resolved for c in r.contributions) == 8
request = ApproveInstallationRequest.model_validate({
    'lockHash': record.current.lock_hash,
    'permissionDiffHash': record.current.permission_diff_hash,
    'migrationPlanHash': record.current.migration_plan_hash,
    'contributionDiffHash': record.current.contribution_diff_hash})
policy = ReleasePolicy(trust_roots=FileTrustRootProvider(T.TRUST).snapshot())
service = InstallationService(store=store, composition_store=cs,
    revalidator=InstallationRevalidator(release_policy=policy),
    planning_revalidator=RuntimeReleaseRevalidator(release_policy=policy))
before = ro.source_fingerprint()
assert len(before) == 650
private = OUT / 'private'
private.mkdir(mode=0o700)
dump = private / 'before.dump'
with os.fdopen(os.open(dump, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as f:
    backup = subprocess.run(['docker', '--context', ro.CONTEXT, 'exec', ro.SOURCE,
        'pg_dump', '-U', 'aos_app', '-d', 'aos_meta_head', '-Fc'], stdout=f,
        stderr=subprocess.PIPE, timeout=180)
assert backup.returncode == 0, 'Backup failed; no approval mutation'
copy = private / 'before.second.dump'
with os.fdopen(os.open(copy, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as f:
    f.write(dump.read_bytes())
digest = hashlib.sha256(dump.read_bytes()).hexdigest()
assert digest == hashlib.sha256(copy.read_bytes()).hexdigest()
assert ro.source_fingerprint() == before
emit('backup.json', {'sha256': digest, 'bytes': dump.stat().st_size, 'secondCopyExact': True})
emit('intent.json', {'operation': 'InstallationService.approve', 'installationId': installation,
    'tenant': tenant, 'expectedEtag': 2, 'actor': actor,
    'actorSource': 'explicit human conversation authorization; not OIDC',
    'approvalSourceSha256': hashlib.sha256((OUT / 'approval-source.json').read_bytes()).hexdigest(),
    'request': request.model_dump(mode='json', by_alias=True)})
receipt = service.approve(installation_id=installation, request=request, **tenant,
    actor=actor, roles=['asset-install-approver'], markings=['public', 'restricted'],
    idempotency_key='qyh-explicit-human-approval-20261013', if_match='"2"')
emit('command-terminal.json', {'statusCode': receipt.status_code, 'responseEtag': receipt.response_etag,
    'response': receipt.response_json, 'authenticatedOidcApproval': False})
current = store.get_installation(**tenant, installation_id=installation)
assert current.state == 'approved' and current.etag_version == 3 and current.current.decision_id
after = ro.source_fingerprint()
changed = sorted(k for k in before if before[k] != after[k])
allowed = {'public.bundle_installation', 'public.bundle_installation_revision',
    'public.bundle_installation_event', 'public.bundle_installation_decision',
    'public.bundle_installation_command'}
assert set(changed) <= allowed and set(before) == set(after)
assert ro.current_sql('SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;').strip() == '0'
assert store.get_installation(**tenant, installation_id=old.installation_id).active_revision == 5
emit('terminal.json', {'installationId': installation, 'state': current.state,
    'etagVersion': current.etag_version, 'decisionId': current.current.decision_id,
    'humanApprovalRecorded': True, 'actor': actor, 'authenticatedOidcApproval': False,
    'changedTables': changed, 'unchangedTables': 650 - len(changed),
    'predecessorPreserved': True, 'runtimeActivated': False, 'eightPagesAccepted': False})
print('Original approval committed; approved revision3; runtime remains fenced.')
