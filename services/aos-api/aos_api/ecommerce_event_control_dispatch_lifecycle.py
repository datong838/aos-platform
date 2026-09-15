"""Current signed release and exact approval around the restricted optional dispatch CAS."""
from contextlib import contextmanager
import json
from typing import Literal
from uuid import UUID

from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from pydantic import ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.ecommerce_growth_host_composition import EVENT_CONTROL_OPERATION
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_registration_qualification import qualify_registration_release
from aos_api.ecommerce_product_event_approval import require_current_event_dispatch_approval
from aos_api.ecommerce_product_event_control_qualified_owner import CONTROL_CONTRACT, CONTROL_CONTRACT_PATH
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineInstallationRef
from aos_api.tenant_scope import TenantScope


class EventControlDispatchRequest(AipContractModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
        revalidate_instances='always', hide_input_in_errors=True)
    schema_version: Literal['aos.ecommerce.event-control-dispatch/v1']
    phase: Literal['expand', 'fence', 'shrink']
    installation_ref: PipelineInstallationRef
    generation: str
    execution_epoch: int = Field(ge=1, le=2**63-1)
    runtime_revision: int = Field(ge=1, le=2**63-1)
    cutover_group_id: str
    expected_group_revision: int = Field(ge=1, le=2**63-1)
    case_id: str = Field(min_length=1, max_length=240)
    schedule_policy_id: str = Field(min_length=1, max_length=240)
    approval_ref: PipelineExactRef
    idempotency_key: str = Field(min_length=1, max_length=160)

    @field_validator('generation', 'cutover_group_id')
    @classmethod
    def uuid_text(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical event dispatch UUID required')
        return value

    @field_validator('case_id', 'schedule_policy_id', 'idempotency_key')
    @classmethod
    def canonical_text(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('canonical event dispatch identity required')
        return value

    @model_validator(mode='after')
    def exact_approval(self):
        if self.approval_ref.resource_type != 'ActionApprovalEvent':
            raise ValueError('exact event dispatch approval required')
        return self

    def wire(self):
        return self.model_dump(mode='json', by_alias=True, exclude_none=True)

    def approval_intent(self):
        value = self.wire()
        value.pop('approvalRef')
        return value


class EventControlDispatchLifecycle:
    def __init__(self, *, connect, installation_store, artifacts, release_policy):
        if (not callable(connect) or type(installation_store) is not PostgresInstallationStore
                or type(artifacts) is not CurrentRuntimeReleaseArtifacts
                or type(release_policy) is not ReleasePolicy):
            raise TypeError('current event dispatch lifecycle dependencies required')
        self._connect, self._store, self._artifacts, self._policy = (
            connect, installation_store, artifacts, release_policy)

    @contextmanager
    def _serializable(self):
        with self._connect() as conn:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('event dispatch lifecycle requires an idle connection')
            previous = conn.isolation_level
            conn.isolation_level = IsolationLevel.SERIALIZABLE
            try:
                yield conn
            finally:
                conn.isolation_level = previous

    def _qualify(self, conn, scope, request):
        if self._artifacts.scope != scope:
            raise PermissionError('current event dispatch artifact tenant differs')
        current = CurrentInstallationRef.model_validate(request.installation_ref.model_dump(by_alias=True))
        baseline = self._store.load_active_baseline_in_transaction(conn, org_id=scope.org_id,
            project_id=scope.project_id, requested_ref=current)
        qualified = qualify_registration_release(conn, lock=baseline.lock, release_policy=self._policy)
        selected = [item for item in baseline.lock.payload.resolved if item.id == 'solution.ecommerce.growth']
        if len(selected) != 1:
            raise ValueError('current growth package must be unique')
        claims = [claim for claim in selected[0].contributions if claim.kind == 'api'
            and claim.operation_id == EVENT_CONTROL_OPERATION]
        if (len(claims) != 1 or claims[0].method != 'POST' or claims[0].mode != 'exclusive'
                or claims[0].path != '/ecommerce/growth/investigations/events/control'
                or qualified.get('contentHash') != selected[0].content_hash):
            raise PermissionError('signed event control declaration required')
        record = self._artifacts.load_record(selected[0])
        if not ManifestLoader._is_exported_path(CONTROL_CONTRACT_PATH, record.manifest.spec.exports.schemas):
            raise PermissionError('signed event control contract export required')
        if json.loads(self._artifacts.read_artifact(selected[0], CONTROL_CONTRACT_PATH, 16384)) != CONTROL_CONTRACT:
            raise ValueError('signed event control contract differs')

    def transition(self, *, scope: TenantScope, request: EventControlDispatchRequest, actor: str):
        if type(scope) is not TenantScope or type(request) is not EventControlDispatchRequest:
            raise TypeError('trusted scope and event dispatch request required')
        request = EventControlDispatchRequest.model_validate(request.model_dump(mode='python', by_alias=True))
        if type(actor) is not str or not actor or actor != actor.strip() or not actor.isprintable():
            raise PermissionError('canonical event dispatch actor required')
        with consumer_connection(self._serializable, dict(org_id=scope.org_id, project_id=scope.project_id)) as conn:
            require_runtime_role(conn, org_id=scope.org_id, project_id=scope.project_id,
                protected_tables=('public.extension_operation_dispatch_binding',
                                  'public.extension_event_control_dispatch_receipt'))
            self._qualify(conn, scope, request)
            require_current_event_dispatch_approval(transaction=HostTransaction(conn), scope=scope,
                case_id=request.case_id, policy_id=request.schedule_policy_id,
                approval_ref=request.approval_ref, executor=actor,
                dispatch_intent=request.approval_intent())
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            response = conn.execute('SELECT public.extension_event_control_dispatch_transition_a0v_054(%s,%s) AS receipt',
                (Jsonb(request.wire()), actor)).fetchone()['receipt']
            conn.execute('SET LOCAL ROLE aos_runtime')
            row = conn.execute('SELECT authority_data,content_hash,request_hash,actor FROM '
                'public.extension_event_control_dispatch_receipt WHERE org_id=%s AND project_id=%s '
                'AND idempotency_key=%s', (*scope.key, request.idempotency_key)).fetchone()
            if (row is None or row['actor'] != actor or row['request_hash'] != canonical_sha256(request.wire())
                    or response.get('contentHash') != row['content_hash']
                    or {**row['authority_data'], 'contentHash': row['content_hash']} !=
                       {key: value for key, value in response.items() if key != 'replayed'}):
                raise ValueError('event dispatch receipt readback differs')
            return response
