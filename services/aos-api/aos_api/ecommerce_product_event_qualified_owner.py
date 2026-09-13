"""Current signed growth feature qualification around the source Owner callback."""
import json
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.ecommerce_growth_registration_qualification import qualify_registration_release
from aos_api.extension_runtime.ipc import _pairs, _constant
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.tenant_scope import TenantScope

CONTRACT_PATH='content/schemas/product-event-save.contract.v1.json'
EVENT_CONTRACT={
    'schemaVersion':'aos.ecommerce.product-event-save-contract/v1',
    'operationId':'ecommerce_growth_schedule_put',
    'policySchema':'aos.ecommerce.product-event-schedule-policy/v1',
    'wireFields':['idempotencyKey','expectedPolicyRevision','expectedCaseVersion','policy','caseAuthority','approvalRef'],
    'tenantAuthority':'trusted-host-scope',
    'sourceAuthority':'current-source-selection-owner',
    'approvalAuthority':'current-independent-action-approval',
    'saveEnabled':False,
}


class ProductEventQualifiedOwner:
    def __init__(self, *, selections, installation_store, artifacts, release_policy):
        if (type(selections) is not PipelineSourceSelectionOwner
                or type(installation_store) is not PostgresInstallationStore
                or type(artifacts) is not CurrentRuntimeReleaseArtifacts or type(release_policy) is not ReleasePolicy):
            raise TypeError('current production event qualification dependencies required')
        self._selections,self._store,self._artifacts,self._policy=selections,installation_store,artifacts,release_policy

    def _qualify(self, conn, scope, draft):
        current=CurrentInstallationRef.model_validate(draft.installation_ref.model_dump(by_alias=True))
        return self._qualify_contract(conn,scope,current,CONTRACT_PATH,EVENT_CONTRACT)

    def _qualify_contract(self,conn,scope,current,contract_path,expected_contract):
        baseline=self._store.load_active_baseline_in_transaction(conn,org_id=scope.org_id,
            project_id=scope.project_id,requested_ref=current)
        selected=[item for item in baseline.lock.payload.resolved if item.id=='solution.ecommerce.growth']
        if len(selected)!=1:raise ValueError('current growth package must be unique')
        selected=selected[0]
        qualification=qualify_registration_release(conn,lock=baseline.lock,release_policy=self._policy)
        expected=dict(schemaVersion='aos.ecommerce.registration-release-qualification/v1',
            lockHash=baseline.lock.lock_hash,packageId=selected.id,version=selected.version,
            contentHash=selected.content_hash,executable=False)
        if any(qualification.get(key)!=value for key,value in expected.items()):
            raise ValueError('current growth qualification differs')
        record=self._artifacts.load_record(selected)
        if not ManifestLoader._is_exported_path(contract_path,record.manifest.spec.exports.schemas):
            raise PermissionError('current growth package does not export event save contract')
        raw=self._artifacts.read_artifact(selected,contract_path,16384)
        contract=json.loads(raw,object_pairs_hook=_pairs,parse_constant=_constant)
        if type(contract) is not dict or canonical_sha256(contract)!=canonical_sha256(expected_contract):
            raise ValueError('signed growth event save contract differs')

    def run_current_snapshot(self, conn, *, scope, ref, actor, execute):
        _require_transaction(conn)
        if type(scope) is not TenantScope or scope!=self._artifacts.scope or not callable(execute):
            raise PermissionError('current event qualification tenant differs')
        # Match the Registry-before-installation order used by release writers.
        conn.execute('SELECT pg_advisory_xact_lock(228,1)')
        def current(draft,mapping):
            self._qualify(conn,scope,draft)
            result=execute(draft,mapping)
            _reject_deferred(result)
            self._qualify(conn,scope,draft)
            return result
        return self._selections.run_current_snapshot(conn,scope=scope,ref=ref,actor=actor,execute=current)
