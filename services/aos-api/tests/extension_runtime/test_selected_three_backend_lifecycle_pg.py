"""Future isolated four-package lifecycle tests; no default connection or skip.

The fixed runner must first qualify its new cluster, migrate the full formal
schema, create the two positive workspace parent rows, and register this exact
lab in pytest's stash. Import/collection never performs any of those effects.
"""
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import inspect
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType, SimpleNamespace
from uuid import UUID

import pytest
from psycopg.pq import TransactionStatus

import selected_three_backend_case as selected
from aos_api.extension_runtime.artifact_cache import resolve_image_index
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.lifecycle_store import _digest, RuntimeConflict
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.oci_driver import CleanupUncertainError
from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
from aos_api.extension_runtime.preparation_worker import PreparedJob, PreparationWorker
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
from aos_api.extension_runtime.reconciler import ResourceStillLive
from aos_api.extension_runtime.owned_control_consumer import _settled
from aos_api.extension_runtime.supervisor import ResourceIdentity
from aos_api.tenant_scope import TenantScope, apply_transaction_scope

SELECTED_LAB = pytest.StashKey()
CONTAINER_FORMAT = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},'
    '"running":{{json .State.Running}},"owner":{{json (index .Config.Labels "aos.extension.owner")}},'
    '"network":{{json .HostConfig.NetworkMode}},"readonly":{{json .HostConfig.ReadonlyRootfs}},'
    '"user":{{json .Config.User}},"privileged":{{json .HostConfig.Privileged}},'
    '"capdrop":{{json .HostConfig.CapDrop}},"security":{{json .HostConfig.SecurityOpt}},'
    '"binds":{{json .HostConfig.Binds}}}')


class _LabIdentityResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return dict(self._row)


class _LabIdentityConnection:
    def __init__(self, row):
        self.row = row

    def execute(self, statement, parameters=None):
        require('current_database()' in statement and 'pg_database' in statement,
                'lab identity must come from the PostgreSQL catalog')
        require(parameters == ('aos_app',), 'lab identity administrator parameter changed')
        return _LabIdentityResult(self.row)


def test_selected_lab_identity_is_explicit_and_rejects_catalog_drift():
    binding = selected.SelectedLabIdentity(
        database_name='aos_refresh_activation_native',
        database_oid=16384,
        cluster_name='qyh-canonical166-8af8248e67b4128101100eda',
        administrator_role='aos_app')
    row = dict(database_name=binding.database_name, database_oid=binding.database_oid,
        cluster_name=binding.cluster_name, database_owner=binding.administrator_role,
        current_role=binding.administrator_role, session_role=binding.administrator_role,
        administrator_superuser=True, server_version=160014)
    observed = selected.verify_selected_lab_identity(
        _LabIdentityConnection(row), binding, maintenance=True)
    require(observed == row, 'explicit canonical lab identity readback changed')
    restricted = dict(row, current_role='aos_refresh_activation_native_migrator',
        session_role='aos_refresh_activation_native_migrator')
    require(selected.verify_selected_lab_identity(
        _LabIdentityConnection(restricted), binding, maintenance=False) == restricted,
        'restricted runtime role must retain canonical lab identity')
    for invalid in (
            dict(database_name='AOS_BAD', database_oid=16384,
                cluster_name=binding.cluster_name, administrator_role=binding.administrator_role),
            dict(database_name=binding.database_name, database_oid=True,
                cluster_name=binding.cluster_name, administrator_role=binding.administrator_role),
            dict(database_name=binding.database_name, database_oid=16384,
                cluster_name='bad_cluster', administrator_role=binding.administrator_role)):
        with pytest.raises(ValueError, match='explicit selected lab identity'):
            selected.SelectedLabIdentity(**invalid)
    for field, value in (
            ('database_name', 'aos_m2_three_backend'), ('database_oid', 16385),
            ('cluster_name', 'qyh-native166-wrong'), ('database_owner', 'postgres'),
            ('current_role', 'postgres'), ('session_role', 'postgres'),
            ('administrator_superuser', False), ('server_version', 150000)):
        changed = dict(row, **{field: value})
        with pytest.raises((PermissionError, ValueError), match='selected lab identity'):
            selected.verify_selected_lab_identity(
                _LabIdentityConnection(changed), binding, maintenance=True)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class InjectedSelectedMemberFailure(RuntimeError):
    """Known load failure in this new isolated test, not an OCI outcome."""


class SecondSelectedMemberFailure:
    def __init__(self, load_record):
        require(callable(load_record), 'original selected loader required')
        self.load_record, self.seen = load_record, []
        self.error = InjectedSelectedMemberFailure('isolated second selected load failure')

    def __call__(self, member):
        pair = (member.id, member.content_hash)
        require(pair in {(bid, selected.EXPECTED[bid][1]) for bid in selected.BACKEND_IDS}
                and pair not in self.seen and len(self.seen) < 2, 'fixed distinct selected loads required')
        self.seen.append(pair)
        if len(self.seen) == 2:
            raise self.error
        return self.load_record(member)


async def _await_selected_host_failure(session, read_expected):
    """Private shared merge; lazy identity becomes available after worker bind."""
    primary = closing = None
    error = None
    try:
        try:
            await asyncio.wait_for(asyncio.shield(session.task), session.timeout_seconds)
        except BaseException as observed:
            error = read_expected()
            if error is None or observed is not error:
                raise
        else:
            error = read_expected()
            raise ValueError('selected Host did not propagate the injected failure')
    except BaseException as observed:
        primary = observed
    try:
        await _settled(session.close())
    except BaseException as observed:
        closing = observed
    if primary is not None:
        if closing is None or closing is primary or closing is error:
            raise primary
        if isinstance(primary, CleanupUncertainError):
            raise primary from closing
        raise closing from primary
    if error is not None and closing is error:
        return
    if closing is not None:
        raise closing
    raise ValueError('selected Host close did not retain the injected failure')


async def await_exact_host_failure(session, error):
    require(type(error) is InjectedSelectedMemberFailure, 'exact controlled failure required')
    return await _await_selected_host_failure(session, lambda:error)


async def await_unknown_host_failure(session, fault):
    from unknown_create_fault_r52 import SelectedUnknownCreateFault
    require(type(fault) is SelectedUnknownCreateFault, 'exact consumed unknown fault required')
    return await _await_selected_host_failure(session, lambda:fault.error)


@dataclass(frozen=True)
class InitialPolicyDrafts:
    case_id: str
    now: datetime
    requests: tuple


def build_initial_policy_drafts(case_id, now):
    """First independent draft sources only, not the complete configuration."""
    from aos_api.aip_budget_contracts import BudgetRevisionCreate
    from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate, DataClassificationPolicyRevisionCreate
    from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
    require(case_id == 'm2-three-t2' and type(now) is datetime and now.tzinfo is not None
            and now.utcoffset() == timedelta(0), 'fixed T2 identity and aware UTC clock required')
    actor, checker = 'synthetic-' + case_id + '-source-author', 'synthetic-' + case_id + '-source-checker'
    window = dict(effectiveFrom=now - timedelta(seconds=1), effectiveUntil=now + timedelta(minutes=30))
    common = dict(revision=1, environment='development', owner=actor,
        approvalRef='fixture-draft-only:' + case_id, lifecycle='draft', **window)
    budget = BudgetRevisionCreate(budgetId=case_id+'-budget', revision=1, environment='development',
        currency='CNY', dailyLimitMinor=1, monthlyLimitMinor=1, alertThresholdPct=80,
        hardStop=True, unknownUsageBehavior='block', owner=actor, overBudgetApprover=checker,
        lifecycle='draft', **window)
    egress = EgressPolicyRevisionCreate(policyId=case_id+'-egress', **common,
        allowedSchemes=['https'], allowedHosts=['api.agnes-ai.cn'], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior='block',
        regionState='confirmed', region='isolated-fixture-not-production')
    data = DataClassificationPolicyRevisionCreate(policyId=case_id+'-data', **common,
        allowedClassifications=['public_catalog'], prohibitedClassifications=['direct_pii','raw_order_detail',
            'customer_conversation','credential','commercial_sensitive','cross_tenant','unknown'],
        denyUnknown=True, allowDirectPii=False, allowCommercialSensitive=False, allowCrossTenant=False)
    quota = QuotaPolicyRevisionCreate(policyId=case_id+'-quota', **common,
        maxConcurrency=1, maxInputTokens=1, maxOutputTokens=1, hourlyRequestLimit=1, dailyRequestLimit=1,
        reservationLeaseSeconds=60, overflowBehavior='reject', allowPublicProviderFallback=False, allowAutoScale=False)
    return InitialPolicyDrafts(case_id, now, (budget, egress, data, quota))


class _TenantPolicyConnection:
    """Narrow original-Store seam for its internal commit-then-read behavior.

    One fresh isolated connection only. LOCAL bindings are reapplied with the
    original binder, never replaced by session tenant state or elevated roles.
    """
    def __init__(self, conn, scope):
        self._conn, self._scope = conn, scope
        apply_transaction_scope(conn, scope)

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self):
        self._conn.commit()
        apply_transaction_scope(self._conn, self._scope)

    def rollback(self):
        self._conn.rollback()
        apply_transaction_scope(self._conn, self._scope)


@dataclass(frozen=True)
class SelectedT2InstallationPair:
    """Frozen inputs for the future T2 runner; construction grants no phase."""
    original: SimpleNamespace
    successor: SimpleNamespace
    original_producer: SimpleNamespace
    successor_producer: SimpleNamespace

    def __post_init__(self):
        expected = ('m2-three-t2-original', 'm2-three-t2-successor')
        entries = ((self.original, self.original_producer, expected[0]),
                   (self.successor, self.successor_producer, expected[1]))
        identities = []
        for wrapper, producer, case_id in entries:
            if (type(wrapper) is not SimpleNamespace
                    or set(vars(wrapper)) != {'case', 'preparation'}):
                raise TypeError('exact selected T2 case wrapper required')
            case, preparation = wrapper.case, wrapper.preparation
            action = getattr(case, 'action', None)
            if (getattr(case, 'case_id', None) != case_id
                    or getattr(case, 'scope', None) != dict(org_id='org-org', project_id='dev-project')
                    or type(action) is not dict
                    or set(action) != {'org_id', 'project_id', 'installation_id', 'actor', 'roles', 'markings'}
                    or (action['org_id'], action['project_id']) != ('org-org', 'dev-project')
                    or action['actor'] != 'synthetic-' + case_id + '-author'
                    or action['roles'] != ['asset-installer'] or action['markings'] != []):
                raise ValueError('exact selected T2 case identity required')
            try:
                identity = str(UUID(action['installation_id']))
            except (TypeError, ValueError, AttributeError):
                raise ValueError('canonical selected T2 installation required') from None
            if identity != action['installation_id']:
                raise ValueError('canonical selected T2 installation required')
            identities.append(identity)
            dependencies = getattr(preparation, 'dependencies', None)
            runtime = getattr(producer, 'runtime', None)
            configure = getattr(runtime, 'configure_service', None)
            if (getattr(dependencies, 'installation_store', None) is not getattr(case, 'store', None)
                    or getattr(configure, '_store', None) is not case.store
                    or getattr(configure, '_reader', None) is not getattr(case, 'installation_service', None)):
                raise ValueError('selected T2 producer dependency graph differs')
        if identities[0] == identities[1]:
            raise ValueError('two distinct selected T2 installations required')
        if self.original.case.registry is not self.successor.case.registry:
            raise ValueError('one selected T2 Registry required')
        lock_hashes = (getattr(self.original.case.lock, 'lock_hash', None),
                       getattr(self.successor.case.lock, 'lock_hash', None))
        if (lock_hashes[0] != lock_hashes[1] or type(lock_hashes[0]) is not str
                or re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', lock_hashes[0]) is None):
            raise ValueError('one selected T2 package lock required')


def build_t2_registration_request_material(*, pair, slot, installation, runtime, group_id):
    """Build one original registration DTO from exact current read-only facts.

    This function neither reads configuration contents nor calls registration.
    The original registration service must revalidate every fact at execution.
    """
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef, InstallationRecord
    from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
    from aos_api.ecommerce_growth_registration_preflight import require_registration_runtime
    from aos_api.extension_runtime.runtime_view import RuntimeBindingView, RuntimeInstallationView

    if type(pair) is not SelectedT2InstallationPair or slot not in {'original', 'successor'}:
        raise ValueError('exact selected T2 pair slot required')
    pair.__post_init__()
    if type(installation) is not InstallationRecord or type(runtime) is not RuntimeInstallationView:
        raise TypeError('original current installation and runtime views required')
    try:
        canonical_group = str(UUID(group_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError('canonical selected T2 cutover group required') from None
    if canonical_group != group_id:
        raise ValueError('canonical selected T2 cutover group required')

    case = getattr(pair, slot).case
    expected_id = case.action['installation_id']
    current = installation.current
    state = getattr(installation.state, 'value', installation.state)
    current_state = getattr(current.state, 'value', current.state)
    binding = runtime.binding
    if (str(installation.installation_id) != expected_id
            or str(current.installation_id) != expected_id
            or state != 'active' or current_state != 'active'
            or installation.active_revision != installation.current_revision
            or installation.current_revision != current.revision
            or installation.etag_version != installation.current_revision
            or current.lock_hash != case.lock.lock_hash
            or type(current.overlay_revision) is not str or not current.overlay_revision
            or runtime.installationId != expected_id
            or runtime.installationRevision != installation.current_revision
            or runtime.installationEtag != installation.etag_version
            or runtime.installationState != 'active' or runtime.effectiveState != 'ready'):
        raise ValueError('selected T2 current registration facts differ')
    if type(binding) is not RuntimeBindingView:
        raise ValueError('selected T2 current runtime binding required')

    installation_ref = CurrentInstallationRef(installationId=expected_id,
        revision=installation.current_revision, lockHash=current.lock_hash,
        overlayRevision=current.overlay_revision)
    request = FirstDispatchRegistrationRequest(
        schemaVersion='aos.ecommerce.first-dispatch-registration/v1',
        installationRef=installation_ref, generation=binding.generation,
        bindingRevision=binding.revision, executionEpoch=binding.executionEpoch,
        configRef=binding.configRef, groupId=canonical_group,
        idempotencyKey=case.case_id + '-first-registration')
    require_registration_runtime(dict(
        generation=binding.generation,
        installation_revision=binding.installationRevision,
        execution_epoch=binding.executionEpoch,
        config_ref=binding.configRef,
        revision=binding.revision,
        enabled=binding.enabled,
        operation_fence=binding.operationFence,
        desired_state=binding.desiredState,
        observed_state=binding.observedState,
    ), request)
    return FirstDispatchRegistrationRequest.model_validate(
        request.model_dump(mode='python', by_alias=True))


def read_t2_registration_request_material(*, pair, slot, group_id):
    """Read exact current facts through original readers, then build the DTO."""
    from aos_api.extension_runtime.runtime_view import RuntimeViewReader

    if type(pair) is not SelectedT2InstallationPair or slot not in {'original', 'successor'}:
        raise ValueError('exact selected T2 pair slot required')
    pair.__post_init__()
    try:
        if str(UUID(group_id)) != group_id:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ValueError('canonical selected T2 cutover group required') from None
    item = getattr(pair, slot)
    case = item.case
    connector = getattr(case.registry, 'connect', None)
    if not callable(connector):
        raise TypeError('original selected T2 Registry connector required')
    installation_id = case.action['installation_id']
    installation = case.store.get_installation(**case.scope,
        installation_id=installation_id)
    runtime = RuntimeViewReader(installation_reader=case.installation_service,
        connect_factory=connector).get_installation(
            installation_id=installation_id,
            org_id=case.scope['org_id'], project_id=case.scope['project_id'],
            roles=list(case.action['roles']), markings=list(case.action['markings']))
    return build_t2_registration_request_material(pair=pair, slot=slot,
        installation=installation, runtime=runtime, group_id=group_id)


class SelectedT2RegistrationSession:
    """One original first-registration attempt; uncertain outcomes are read only."""
    _BODY_KEYS = frozenset({'schemaVersion', 'tenant', 'receiptId', 'installationId',
        'generation', 'groupId', 'requestHash', 'idempotencyKey', 'actor', 'request',
        'dispatchSnapshot', 'executable', 'createdAt'})

    def __init__(self, pair, *, slot):
        if type(pair) is not SelectedT2InstallationPair or slot not in {'original', 'successor'}:
            raise ValueError('exact selected T2 pair slot required')
        pair.__post_init__()
        self.pair, self.slot = pair, slot
        self.item = getattr(pair, slot)
        self.registration = getattr(getattr(pair, slot + '_producer'), 'registration', None)
        if (not callable(getattr(self.registration, 'register', None))
                or not callable(getattr(self.registration, 'read_receipt', None))):
            raise TypeError('original selected first registration service required')
        self._attempted = False
        self._unknown = None
        self._descriptor = None
        self._receipt = None

    @property
    def unknown(self):
        return self._unknown

    @property
    def receipt_ref(self):
        from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef
        if self._receipt is None:
            return None
        return RegistrationReceiptRef(resourceType='FirstDispatchRegistrationReceipt',
            resourceId=self._receipt['receiptId'], revision=1,
            contentHash=self._receipt['contentHash'])

    def _validate_receipt(self, receipt, *, historical):
        from datetime import datetime
        from aos_api.asset_registry.canonical_json import canonical_sha256
        from aos_api.ecommerce_growth_registration_contracts import (
            FirstDispatchRegistrationRequest, preview_registration,
        )
        from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef

        marker = 'historical' if historical else 'replayed'
        if type(receipt) is not dict or set(receipt) != self._BODY_KEYS | {'contentHash', marker}:
            raise ValueError('selected T2 registration receipt shape differs')
        descriptor = self._descriptor
        request = descriptor['request']
        try:
            parsed = FirstDispatchRegistrationRequest.model_validate(receipt['request'])
            created = datetime.fromisoformat(receipt['createdAt'])
            RegistrationReceiptRef(resourceType='FirstDispatchRegistrationReceipt',
                resourceId=receipt['receiptId'], revision=1, contentHash=receipt['contentHash'])
        except (TypeError, ValueError, OverflowError):
            raise ValueError('selected T2 registration receipt invalid') from None
        body = {key: receipt[key] for key in self._BODY_KEYS}
        if (receipt[marker] is not (True if historical else False)
                or receipt['schemaVersion'] != 'aos.ecommerce.first-dispatch-registration-receipt/v1'
                or receipt['tenant'] != {'orgId': 'org-org', 'projectId': 'dev-project'}
                or receipt['installationId'] != descriptor['installation']
                or receipt['generation'] != request.generation
                or receipt['groupId'] != request.groupId
                or receipt['requestHash'] != descriptor['request_hash']
                or receipt['idempotencyKey'] != descriptor['key']
                or receipt['actor'] != descriptor['actor']
                or parsed != request
                or receipt['dispatchSnapshot'] != preview_registration(request)['proposedDispatchSnapshot']
                or receipt['executable'] is not False
                or created.utcoffset() is None
                or canonical_sha256(body) != receipt['contentHash']):
            raise ValueError('selected T2 registration receipt differs')
        return dict(receipt)

    async def request(self, request, *, freeze_descriptor=None):
        import asyncio
        from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
        from aos_api.extension_runtime.owned_control_consumer import _settled

        if self._attempted or self._unknown is not None:
            raise RuntimeError('selected T2 registration already attempted; reconcile, never resend')
        if type(request) is not FirstDispatchRegistrationRequest:
            raise TypeError('exact first registration request required')
        frozen = FirstDispatchRegistrationRequest.model_validate(
            request.model_dump(mode='python', by_alias=True))
        case = self.item.case
        expected_key = case.case_id + '-first-registration'
        if (frozen.installationRef.installation_id != case.action['installation_id']
                or frozen.idempotencyKey != expected_key):
            raise ValueError('selected T2 registration request identity differs')
        actor = case.action['actor']
        self._descriptor = MappingProxyType(dict(request=frozen,
            request_hash=frozen.request_hash(), installation=case.action['installation_id'],
            key=expected_key, actor=actor))
        if freeze_descriptor is not None:
            if not callable(freeze_descriptor):
                raise TypeError('synchronous registration descriptor freezer required')
            freeze_descriptor(self._descriptor)
        self._attempted = True
        self._unknown = 'registration'
        receipt = await _settled(asyncio.to_thread(self.registration.register,
            scope=TenantScope('org-org', 'dev-project'), request=frozen, actor=actor))
        receipt = self._validate_receipt(receipt, historical=False)
        self._receipt = receipt
        self._unknown = None
        return receipt

    async def reconcile(self):
        import asyncio
        from aos_api.extension_runtime.owned_control_consumer import _settled

        if self._unknown != 'registration' or self._descriptor is None:
            raise RuntimeError('no selected T2 registration outcome requires reconciliation')
        descriptor = self._descriptor
        receipt = await _settled(asyncio.to_thread(self.registration.read_receipt,
            scope=TenantScope('org-org', 'dev-project'),
            installation_id=descriptor['installation'], idempotency_key=descriptor['key'],
            actor=descriptor['actor']))
        receipt = self._validate_receipt(receipt, historical=True)
        self._receipt = receipt
        self._unknown = None
        return receipt


def build_t2_cutover_prepare_request(*, registration_session, cutover_operation_id,
        policy_ref, approval_ref, checkpoint, occurrence_watermark,
        pending_target_receipt_refs):
    """Bind explicit external authority refs to one exact registration origin.

    Construction does not prove or create approval.  The original cutover store
    must re-read and validate all current approval authority during execution.
    """
    from datetime import datetime
    from aos_api.ecommerce_growth_cutover import CutoverExactRef, CutoverPrepareRequest
    from aos_api.ecommerce_growth_cutover_command import CutoverProductCommand
    from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest

    if (type(registration_session) is not SelectedT2RegistrationSession
            or registration_session.slot != 'original'
            or registration_session.unknown is not None
            or registration_session._receipt is None
            or registration_session.receipt_ref is None
            or registration_session._descriptor is None):
        raise ValueError('completed selected T2 first registration required')
    try:
        operation = str(UUID(cutover_operation_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError('canonical selected T2 cutover operation required') from None
    if type(cutover_operation_id) is not str or operation != cutover_operation_id:
        raise ValueError('canonical selected T2 cutover operation required')
    if type(policy_ref) is not CutoverExactRef or type(approval_ref) is not CutoverExactRef:
        raise TypeError('explicit current policy and approval references required')
    if (type(checkpoint) is not dict or type(pending_target_receipt_refs) is not tuple
            or any(type(item) is not CutoverExactRef for item in pending_target_receipt_refs)
            or (occurrence_watermark is not None
                and (type(occurrence_watermark) is not datetime
                     or occurrence_watermark.tzinfo is None))):
        raise TypeError('explicit selected T2 cutover checkpoint and watermarks required')
    policy = CutoverExactRef.model_validate(policy_ref.model_dump(mode='python', by_alias=True))
    approval = CutoverExactRef.model_validate(approval_ref.model_dump(mode='python', by_alias=True))
    pending = tuple(CutoverExactRef.model_validate(
        item.model_dump(mode='python', by_alias=True)) for item in pending_target_receipt_refs)
    frozen = registration_session._descriptor['request']
    if type(frozen) is not FirstDispatchRegistrationRequest:
        raise TypeError('frozen original first registration request required')
    case = registration_session.item.case
    request = CutoverPrepareRequest(cutoverOperationId=operation,
        idempotencyKey=case.case_id + '-cutover-prepare',
        cutoverGroupId=frozen.groupId, expectedGroupRevision=1,
        targetInstallationId=frozen.installationRef.installation_id,
        targetGeneration=frozen.generation,
        targetExecutionEpoch=frozen.executionEpoch,
        targetRuntimeRevision=frozen.bindingRevision,
        policyRef=policy, approvalRef=approval, checkpoint=dict(checkpoint),
        occurrenceWatermark=occurrence_watermark,
        pendingTargetReceiptRefs=pending,
        registrationReceiptRef=registration_session.receipt_ref)
    command = CutoverProductCommand(phase='prepare', request=request)
    return CutoverPrepareRequest.model_validate(
        command.request.model_dump(mode='python', by_alias=True))


class SelectedT2CutoverPrepareSession:
    """One exact prepare attempt; an uncertain outcome can only be read back."""
    def __init__(self, pair, *, slot):
        if type(pair) is not SelectedT2InstallationPair or slot not in {'original', 'successor'}:
            raise ValueError('exact selected T2 pair slot required')
        pair.__post_init__()
        self.pair, self.slot = pair, slot
        self.item = getattr(pair, slot)
        self.producer = getattr(pair, slot + '_producer')
        if (not callable(getattr(getattr(self.producer, 'control', None), 'execute', None))
                or not callable(getattr(getattr(self.producer, 'store', None), 'read_prepare_receipt', None))):
            raise TypeError('original selected cutover control and reader required')
        self._attempted = False
        self._unknown = None
        self._descriptor = None

    @property
    def unknown(self):
        return self._unknown

    def _validate_receipt(self, receipt, *, replayed):
        from aos_api.ecommerce_growth_cutover import CutoverPrepareReceipt
        request = self._descriptor['request']
        if (type(receipt) is not CutoverPrepareReceipt or receipt.replayed is not replayed
                or receipt.tenant.model_dump(mode='json', by_alias=True)
                    != {'orgId': 'org-org', 'projectId': 'dev-project'}
                or receipt.cutover_operation_id != request.cutover_operation_id
                or receipt.cutover_group_id != request.cutover_group_id
                or receipt.expected_group_revision != request.expected_group_revision
                or receipt.target_installation_id != request.target_installation_id
                or receipt.target_generation != request.target_generation
                or receipt.target_execution_epoch != request.target_execution_epoch
                or receipt.target_runtime_revision != request.target_runtime_revision
                or receipt.registration_receipt_ref != request.registration_receipt_ref
                or receipt.policy_ref != request.policy_ref or receipt.approval_ref != request.approval_ref
                or receipt.request_hash != self._descriptor['request_hash']):
            raise ValueError('selected T2 cutover prepare receipt differs')
        return receipt

    async def request(self, request, *, expected_installation_etag):
        import asyncio
        from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._attempted or self._unknown is not None:
            raise RuntimeError('selected T2 cutover prepare already attempted; reconcile, never resend')
        case = self.item.case
        if type(request) is not CutoverPrepareRequest:
            raise TypeError('exact cutover prepare request required')
        frozen = CutoverPrepareRequest.model_validate(request.model_dump(mode='python', by_alias=True))
        expected_key = case.case_id + '-cutover-prepare'
        if (type(expected_installation_etag) is not int or isinstance(expected_installation_etag, bool)
                or expected_installation_etag < 1
                or str(frozen.target_installation_id) != case.action['installation_id']
                or frozen.idempotency_key != expected_key
                or frozen.registration_receipt_ref is None):
            raise ValueError('selected T2 cutover prepare identity or precondition differs')
        actor = case.action['actor']
        self._descriptor = MappingProxyType(dict(request=frozen, request_hash=frozen.request_hash(),
            installation=case.action['installation_id'], key=expected_key, actor=actor,
            expected_installation_etag=expected_installation_etag))
        self._attempted = True
        self._unknown = 'prepare'
        receipt = await _settled(asyncio.to_thread(self.producer.control.execute,
            scope=TenantScope('org-org', 'dev-project'), phase='prepare', request=frozen, actor=actor,
            expected_installation_id=self._descriptor['installation'],
            expected_installation_etag=expected_installation_etag))
        receipt = self._validate_receipt(receipt, replayed=False)
        self._unknown = None
        return receipt

    async def reconcile(self):
        import asyncio
        from aos_api.ecommerce_growth_cutover import CutoverPrepareReceipt
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._unknown != 'prepare' or self._descriptor is None:
            raise RuntimeError('no selected T2 cutover prepare outcome requires reconciliation')
        descriptor = self._descriptor
        result = await _settled(asyncio.to_thread(self.producer.store.read_prepare_receipt,
            scope=TenantScope('org-org', 'dev-project'), installation_id=descriptor['installation'],
            idempotency_key=descriptor['key'], actor=descriptor['actor']))
        if (type(result) is not dict or set(result) != {'receipt', 'historical', 'executable'}
                or result['historical'] is not True or result['executable'] is not False):
            raise ValueError('selected T2 historical prepare envelope differs')
        receipt = CutoverPrepareReceipt.model_validate(result['receipt'])
        receipt = self._validate_receipt(receipt, replayed=True)
        self._unknown = None
        return receipt


class SelectedT2CutoverPhaseSequence:
    """Strict post-prepare phase prefix with read-only uncertain reconciliation."""
    _ORDER = ('pause', 'commit', 'validate', 'resume')

    def __init__(self, prepare_session, prepare_receipt):
        from aos_api.ecommerce_growth_cutover import CutoverPrepareReceipt
        if (type(prepare_session) is not SelectedT2CutoverPrepareSession
                or prepare_session.unknown is not None or not prepare_session._attempted
                or prepare_session._descriptor is None):
            raise ValueError('known selected T2 prepare session required')
        prepare_session._validate_receipt(prepare_receipt, replayed=False)
        if type(prepare_receipt) is not CutoverPrepareReceipt:
            raise TypeError('exact selected T2 prepare receipt required')
        self.prepare_session = prepare_session
        self.prepare = prepare_receipt
        self.item = prepare_session.item
        self.producer = prepare_session.producer
        self._receipts = []
        self._unknown = None
        self._descriptor = None

    @property
    def completed(self):
        return tuple(self._ORDER[index] for index in range(len(self._receipts)))

    @staticmethod
    def _ref(receipt, kind):
        from aos_api.ecommerce_growth_cutover import CutoverExactRef
        return CutoverExactRef(resourceType=kind, resourceId=str(receipt.receipt_id),
            revision=1, contentHash=receipt.content_hash)

    def _validate_phase_receipt(self, receipt, *, replayed):
        from aos_api.ecommerce_growth_cutover import CutoverCommitPhaseReceipt, CutoverFinalizeReceipt
        descriptor, phase = self._descriptor, self._descriptor['phase']
        expected_type = CutoverCommitPhaseReceipt if phase in {'pause', 'commit'} else CutoverFinalizeReceipt
        if (type(receipt) is not expected_type or receipt.replayed is not replayed
                or receipt.phase != phase or receipt.cutover_operation_id != self.prepare.cutover_operation_id
                or receipt.cutover_group_id != self.prepare.cutover_group_id
                or receipt.request_hash != descriptor['request_hash']
                or receipt.tenant.model_dump(mode='json', by_alias=True)
                    != {'orgId': 'org-org', 'projectId': 'dev-project'}):
            raise ValueError('selected T2 cutover phase receipt differs')
        if phase in {'pause', 'commit'}:
            if receipt.prepare_receipt_ref != self._ref(self.prepare, 'CutoverPrepareReceipt'):
                raise ValueError('selected T2 cutover prepare reference differs')
        else:
            if len(self._receipts) < 2 or receipt.commit_receipt_ref != self._ref(
                    self._receipts[1], 'CutoverCommitReceipt'):
                raise ValueError('selected T2 cutover commit reference differs')
        return receipt

    async def request_next(self, request, *, expected_installation_etag, validate_receipt_ref=None):
        import asyncio
        from aos_api.ecommerce_growth_cutover import CutoverCommitRequest, CutoverFinalizeRequest
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._unknown is not None:
            raise RuntimeError('selected T2 cutover phase uncertain; reconcile, never resend')
        if len(self._receipts) >= len(self._ORDER):
            raise RuntimeError('selected T2 cutover phase sequence already complete')
        phase = self._ORDER[len(self._receipts)]
        case = self.item.case
        if type(expected_installation_etag) is not int or isinstance(expected_installation_etag, bool) or expected_installation_etag < 1:
            raise ValueError('exact selected T2 installation etag required')
        if phase in {'pause', 'commit'}:
            if type(request) is not CutoverCommitRequest or validate_receipt_ref is not None:
                raise TypeError('exact selected T2 commit request required')
            frozen = CutoverCommitRequest.model_validate(request.model_dump(mode='python', by_alias=True))
            if (frozen.idempotency_key != case.case_id + '-cutover-commit'
                    or frozen.cutover_operation_id != self.prepare.cutover_operation_id
                    or frozen.prepare_receipt_ref != self._ref(self.prepare, 'CutoverPrepareReceipt')):
                raise ValueError('selected T2 commit request differs')
        else:
            if type(request) is not CutoverFinalizeRequest:
                raise TypeError('exact selected T2 finalize request required')
            frozen = CutoverFinalizeRequest.model_validate(request.model_dump(mode='python', by_alias=True))
            if (len(self._receipts) < 2 or frozen.idempotency_key != case.case_id + '-cutover-finalize'
                    or frozen.cutover_operation_id != self.prepare.cutover_operation_id
                    or frozen.commit_receipt_ref != self._ref(self._receipts[1], 'CutoverCommitReceipt')):
                raise ValueError('selected T2 finalize request differs')
            if phase == 'resume':
                expected_validate = self._ref(self._receipts[2], 'CutoverValidateReceipt')
                if validate_receipt_ref != expected_validate:
                    raise ValueError('selected T2 validate receipt reference differs')
            elif validate_receipt_ref is not None:
                raise ValueError('unexpected selected T2 validate receipt reference')
        self._descriptor = MappingProxyType(dict(phase=phase, request=frozen,
            request_hash=frozen.request_hash(), expected_installation_etag=expected_installation_etag))
        self._unknown = phase
        kwargs = dict(scope=TenantScope('org-org', 'dev-project'), phase=phase, request=frozen,
            actor=case.action['actor'], expected_installation_id=case.action['installation_id'],
            expected_installation_etag=expected_installation_etag)
        if phase == 'resume':
            kwargs['validate_receipt_ref'] = validate_receipt_ref
        receipt = await _settled(asyncio.to_thread(self.producer.control.execute, **kwargs))
        receipt = self._validate_phase_receipt(receipt, replayed=False)
        self._receipts.append(receipt)
        self._unknown = None
        self._descriptor = None
        return receipt

    async def reconcile(self):
        import asyncio
        from aos_api.ecommerce_growth_cutover import CutoverCommitPhaseReceipt, CutoverFinalizeReceipt, CutoverPrepareReceipt
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._unknown is None or self._descriptor is None:
            raise RuntimeError('no selected T2 cutover phase requires reconciliation')
        case = self.item.case
        history = await _settled(asyncio.to_thread(self.producer.store.read_activation_history,
            scope=TenantScope('org-org', 'dev-project'), installation_id=case.action['installation_id'],
            idempotency_key=self.prepare_session._descriptor['key'], actor=case.action['actor']))
        keys = {'schemaVersion', 'historical', 'executable', 'observedStatus', 'activationReceipts', 'rollbacks'}
        if (type(history) is not dict or set(history) != keys
                or history['schemaVersion'] != 'aos.ecommerce.cutover-history/v1'
                or history['historical'] is not True or history['executable'] is not False
                or history['rollbacks'] != [] or type(history['activationReceipts']) is not dict):
            raise ValueError('selected T2 activation history envelope differs')
        phase = self._unknown
        prefix = ('prepare',) + self._ORDER[:self._ORDER.index(phase) + 1]
        if tuple(history['activationReceipts']) != prefix:
            raise ValueError('selected T2 activation history is not the exact phase prefix')
        models = {'prepare': CutoverPrepareReceipt, 'pause': CutoverCommitPhaseReceipt,
            'commit': CutoverCommitPhaseReceipt, 'validate': CutoverFinalizeReceipt, 'resume': CutoverFinalizeReceipt}
        parsed = {name: models[name].model_validate(history['activationReceipts'][name]) for name in prefix}
        expected_prepare = self.prepare.model_copy(update={'replayed': True})
        if parsed['prepare'] != expected_prepare:
            raise ValueError('selected T2 activation prepare history differs')
        for index, known in enumerate(self._receipts):
            if parsed[self._ORDER[index]] != known.model_copy(update={'replayed': True}):
                raise ValueError('selected T2 known activation history differs')
        receipt = self._validate_phase_receipt(parsed[phase], replayed=True)
        self._receipts.append(receipt)
        self._unknown = None
        self._descriptor = None
        return receipt


class SelectedLifecycleLab:
    """Explicit future-runner dependencies, never authority by object presence."""
    def __init__(self, *, runtime_connect, maintenance_connect, command_connect, driver, identity):
        require(all(callable(x) and not inspect.iscoroutinefunction(x) for x in
                    (runtime_connect, maintenance_connect, command_connect)), 'explicit isolated connectors required')
        require(type(driver) is OciDriver and driver.context == 'colima-aos-extension', 'exact isolated driver required')
        require(type(identity) is selected.SelectedLabIdentity, 'explicit isolated lab identity required')
        self.runtime_connect, self.maintenance_connect, self.command_connect = runtime_connect, maintenance_connect, command_connect
        self.driver, self.identity = driver, identity
        self._registry = None
        self._registry_attempted = False
        self._attempted = set()
        self._policy_attempted = set()
        self._guard_attempted = False
        self._guard_observations = []
        self._unknown_recovery_attempted = set()
        self._retirement_attempted = set()
        self._retired_negative_attempted = set()

    @contextmanager
    def guard_maker_connect(self, scope):
        require(type(scope) is TenantScope and scope.key == ('org-org','dev-project'),
                'exact synthetic Guard maker scope required')
        # Formal proposal code owns HostTransaction over this raw transaction;
        # do not pass the commit/rebind policy-Store proxy here.
        with consumer_connection(self.runtime_connect, dict(org_id=scope.org_id, project_id=scope.project_id)) as conn:
            selected.verify_selected_lab_identity(conn, self.identity, maintenance=False)
            yield conn

    def _guard_client_paths(self, issuer, guard_consumer, quota_consumer):
        from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
        from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer
        from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
        root = selected.ROOT / '.evidence/qyh-m2-three-backend-lifecycle-actual-20261023/private'
        clients = ((issuer, GuardPolicyIssuer, '_attempt_directory', 'guard-issuer'),
            (guard_consumer, GuardPolicyConsumer, '_attempts', 'guard-consumer'),
            (quota_consumer, QuotaPolicyConsumer, '_attempts', 'quota-consumer'))
        paths = []
        for client, kind, field, name in clients:
            require(type(client) is kind and client._database == self.identity.database_name,
                    'exact isolated formal Guard client required')
            path = Path(getattr(client, field))
            expected = root / name
            require(path == expected and path.resolve() == expected and not path.is_symlink(),
                    'formal Guard attempt directory differs from future actual contract')
            paths.append(path)
        return tuple(paths)

    def _fresh_guard_attempt_directories(self, issuer, guard_consumer, quota_consumer):
        for path in self._guard_client_paths(issuer, guard_consumer, quota_consumer):
            try:
                info = path.stat(follow_symlinks=False)
                require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                        and stat.S_IMODE(info.st_mode) == 0o700 and not any(path.iterdir()),
                        'new empty private formal Guard attempt directories required')
            except OSError:
                raise ValueError('new private formal Guard attempt directories are absent or inaccessible') from None

    def activate_initial_guard_policies(self, *, drafts, published, maker_bearer, checker_bearer,
                                        issuer, guard_consumer, quota_consumer, expires_at):
        """Future synthetic-realm formal chain only, never a human approval stand-in."""
        from pydantic import SecretStr
        from aos_api.aip_agent_registry_contracts import VersionedAssetRef
        from aos_api.aip_action_models import ActionDraftBundle
        from aos_api.aip_guard_policy_activation import build_guard_activation_target
        from aos_api.aip_guard_policy_issuer import GuardMakerCommand, GuardDecisionCommand, _authenticate, propose_guard_signed
        from aos_api.aip_guard_policy_consumer import GuardConsumeCommand
        from aos_api.aip_network_issuer_attempt import AttemptReceipt, _reserve_attempt_receipt
        from aos_api.aip_budget_store import materialize_revision
        from aos_api.aip_runtime_guard_policy_store import materialize_policy as guard_materialize, canonical_hash
        from aos_api.aip_model_governance_policy_store import materialize_policy as quota_materialize
        require(type(drafts) is InitialPolicyDrafts and type(drafts.requests) is tuple and len(drafts.requests) == 4,
                'fixed complete initial policy drafts required')
        fixed = build_initial_policy_drafts(drafts.case_id, drafts.now)
        require(all(type(item) is type(expected) and item.model_dump(mode='json', by_alias=True)
                    == expected.model_dump(mode='json', by_alias=True) for item, expected in zip(drafts.requests, fixed.requests)),
                'initial policy requests changed')
        require(type(published) is SimpleNamespace and published.phase == 'drafts_only'
                and published.configuration is None and published.activation_authorized is False
                and type(published.drafts) is tuple and len(published.drafts) == 4,
                'original draft-only publication result required')
        require(type(maker_bearer) is SecretStr and type(checker_bearer) is SecretStr,
                'isolated signed identities must remain private SecretStr values')
        scope = TenantScope('org-org','dev-project')
        author, checker = 'synthetic-' + drafts.case_id + '-source-author', 'synthetic-' + drafts.case_id + '-source-checker'
        materializers = (materialize_revision, guard_materialize, guard_materialize, quota_materialize)
        for record, request, materialize in zip(published.drafts, fixed.requests, materializers):
            expected_type = type(materialize(scope, author, request, created_at=drafts.now))
            require(type(record) is expected_type, 'original exact policy draft record required')
            canonical = materialize(scope, author, request, created_at=record.created_at)
            require(record.model_dump(mode='json', by_alias=True) == canonical.model_dump(mode='json', by_alias=True),
                    'published source draft identity or hash changed')
        now = datetime.now(timezone.utc)
        require(type(expires_at) is datetime and expires_at.tzinfo is not None
                and now < expires_at <= now + timedelta(minutes=3)
                and all(item.effective_from <= now < expires_at <= item.effective_until for item in fixed.requests),
                'fresh bounded formal Guard expiry required')
        paths = self._guard_client_paths(issuer, guard_consumer, quota_consumer)
        if self._guard_attempted:
            raise RuntimeError('formal Guard batch already attempted; read-only reconcile, never resend')
        self._fresh_guard_attempt_directories(issuer, guard_consumer, quota_consumer)
        targets = []
        for kind, record, request, consumer, object_type in zip(('egress','data','quota'), published.drafts[1:], fixed.requests[1:],
                (guard_consumer, guard_consumer, quota_consumer), ('EgressPolicyRevision','DataClassificationPolicyRevision','QuotaPolicyRevision')):
            candidate = type(request).model_validate({**request.model_dump(mode='json', by_alias=True),
                'revision': 2, 'lifecycle': 'active'})
            target = build_guard_activation_target(scope=scope, draft=record, candidate=candidate, expected_version=1)
            targets.append((kind, record, candidate, target, consumer, object_type))
        self._guard_attempted = True
        refs = []
        for index, (kind, record, candidate, target, consumer, object_type) in enumerate(targets):
            maker = GuardMakerCommand(orgId=scope.org_id, projectId=scope.project_id, bearerToken=maker_bearer,
                candidate=candidate, expectedVersion=1, idempotencyKey=drafts.case_id+'-guard-maker-'+kind, expiresAt=expires_at)
            _request, principal, authenticated_scope = _authenticate(maker, GuardMakerCommand)
            require(principal.subject == author and authenticated_scope == scope, 'only the fixed synthetic maker may propose')
            if index == 0:
                digest = canonical_hash(dict(task='qyh-m2-three-backend-lifecycle-actual-20261023', batch=drafts.case_id,
                    bindings=[item[3].binding_hash for item in targets], expiresAt=expires_at.isoformat()))
                _reserve_attempt_receipt(paths[0], AttemptReceipt(scope.org_id, scope.project_id,
                    drafts.case_id+'-guard-batch', drafts.case_id+'-guard-batch', digest, principal.subject),
                    namespace='m2-three-backend-guard-batch/v1')
            bundle = propose_guard_signed(maker, connect_factory=self.guard_maker_connect)
            require(type(bundle) is ActionDraftBundle, 'original formal Guard proposal bundle required')
            bundle = ActionDraftBundle.model_validate(bundle.model_dump(mode='json', by_alias=True))
            proposal = bundle.proposal
            expected_payload = dict(candidate=candidate.model_dump(mode='json', by_alias=True), expectedHeadRevision=1,
                expectedHeadVersion=1, sourceContentHash=record.content_hash, targetContentHash=target.target_content_hash,
                bindingHash=target.binding_hash)
            require(proposal.created_by.actor_id == author and proposal.version == 1 and proposal.status.value == 'drafted'
                    and proposal.action_type.action_type_id == target.action_type_id and proposal.action_type.object_type == object_type
                    and proposal.action_binding_hash == target.binding_hash and proposal.payload == expected_payload
                    and proposal.expires_at == expires_at and proposal.task_id is None and proposal.run_id is None
                    and proposal.risk_level.value == 'R2' and re.fullmatch('[0-9a-f]{64}', proposal.proposal_hash)
                    and not bundle.approvals and bundle.draft.proposal_id == proposal.id
                    and bundle.draft.proposal_hash == proposal.proposal_hash and bundle.draft.proposal_version == 1
                    and bundle.draft.status == 'awaiting_approval', 'formal Guard proposal routing or content changed')
            decision = GuardDecisionCommand(orgId=scope.org_id, projectId=scope.project_id, bearerToken=checker_bearer,
                proposalId=proposal.id, idempotencyKey=drafts.case_id+'-guard-decision-'+kind,
                decision=dict(expectedProposalVersion=1, expectedProposalHash=proposal.proposal_hash, decision='approved',
                    reason='isolated synthetic lifecycle verification, not a real-person approval', approvalExpiresAt=expires_at))
            _request, principal, authenticated_scope = _authenticate(decision, GuardDecisionCommand)
            require(principal.subject == checker and authenticated_scope == scope and checker != author,
                    'only the independent fixed synthetic checker may decide')
            approval = issuer.execute(decision)
            if approval.get('status') != 'observed':
                raise RuntimeError('formal Guard approval unresolved; no resend')
            require(approval.get('proposalId') == proposal.id and approval.get('decision') == 'approved'
                    and approval.get('activationAuthorized') is False and type(approval.get('approvalEventId')) is str,
                    'formal Guard approval receipt changed')
            command = GuardConsumeCommand(orgId=scope.org_id, projectId=scope.project_id, bearerToken=maker_bearer,
                proposalId=proposal.id, approvalEventId=approval['approvalEventId'], proposalHash=proposal.proposal_hash,
                targetContentHash=target.target_content_hash, bindingHash=target.binding_hash)
            result = consumer.execute(command)
            if result.get('status') != 'observed':
                raise RuntimeError('formal Guard activation unresolved; no resend')
            ref = result.get('result')
            require(type(ref) is dict and set(ref) == {'resourceType','resourceId','revision','contentHash','proposalId','approvalEventId','receiptId'}
                    and ref['resourceType'] == object_type and ref['resourceId'] == candidate.policy_id
                    and type(ref['revision']) is int and ref['revision'] == 2 and ref['contentHash'] == target.target_content_hash
                    and ref['proposalId'] == proposal.id and ref['approvalEventId'] == approval['approvalEventId']
                    and type(ref['receiptId']) is str and re.fullmatch(('quota' if kind == 'quota' else 'guard')+'-consume-[0-9a-f]{64}',ref['receiptId']),
                    'formal Guard activation result changed')
            refs.append(VersionedAssetRef(assetType=object_type, assetId=ref['resourceId'], revision=2, contentHash=ref['contentHash']))
            self._guard_observations.append(dict(kind=kind, proposal_id=proposal.id, approval_event_id=approval['approvalEventId'],
                receipt_id=ref['receiptId'], resource_ref=refs[-1].model_dump(mode='json', by_alias=True)))
        return SimpleNamespace(phase='guard_refs_only', refs=tuple(refs), budget_active=False, configuration=None, business_authority=False)

    @contextmanager
    def policy_store_connect(self, scope):
        require(type(scope) is TenantScope and scope.key == ('org-org','dev-project'),
                'exact positive draft policy scope required')
        with self.runtime_connect() as conn:
            require(conn.info.transaction_status == TransactionStatus.IDLE, 'fresh idle policy connection required')
            selected.verify_selected_lab_identity(conn, self.identity, maintenance=False)
            yield _TenantPolicyConnection(conn, scope)

    def publish_initial_drafts(self, drafts):
        """Original Stores publish only drafts; no activation or raw INSERT path."""
        from aos_api.aip_budget_store import AipBudgetAuthorityStore, materialize_revision
        from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore, materialize_policy as guard_materialize
        from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore, materialize_policy as governance_materialize
        require(type(drafts) is InitialPolicyDrafts and type(drafts.requests) is tuple and len(drafts.requests) == 4,
                'complete fixed T2 initial drafts required')
        expected = build_initial_policy_drafts(drafts.case_id, drafts.now)
        requests = []
        for item, fixed in zip(drafts.requests, expected.requests):
            require(type(item) is type(fixed), 'original exact draft model required')
            parsed = type(fixed).model_validate(item.model_dump(mode='json', by_alias=True))
            require(parsed.model_dump(mode='json', by_alias=True) == fixed.model_dump(mode='json', by_alias=True),
                    'draft activation or identity/content drift is forbidden')
            requests.append(parsed)
        if drafts.case_id in self._policy_attempted:
            raise RuntimeError('policy draft attempt already started; reconcile, never repeat')
        self._policy_attempted.add(drafts.case_id)
        scope = TenantScope('org-org','dev-project')
        actor = 'synthetic-' + drafts.case_id + '-source-author'
        budget_store = AipBudgetAuthorityStore(self.policy_store_connect)
        guard_store = AipRuntimeGuardPolicyStore(self.policy_store_connect)
        governance_store = AipModelGovernancePolicyStore(self.policy_store_connect)
        operations = ((budget_store.publish, materialize_revision, 'budget'),
            (guard_store.publish_egress, guard_materialize, 'egress'),
            (guard_store.publish_data_classification, guard_materialize, 'data'),
            (governance_store.publish_quota, governance_materialize, 'quota'))
        results = []
        for item, (publish, materialize, kind) in zip(requests, operations):
            result = publish(scope, actor, drafts.case_id+'-draft-'+kind, item, expected_version=0)
            canonical = materialize(scope, actor, item, created_at=result.created_at)
            require(type(result) is type(canonical)
                    and result.model_dump(mode='json', by_alias=True) == canonical.model_dump(mode='json', by_alias=True),
                    'original draft publication result differs')
            results.append(result)
        return SimpleNamespace(phase='drafts_only', configuration=None, activation_authorized=False, drafts=tuple(results))

    def _maintenance(self, conn):
        selected.verify_selected_lab_identity(conn, self.identity, maintenance=True)

    def new_case(self, case_id):
        require(case_id in {'m2-three-t1', 'm2-three-t1-failure', 'm2-three-t1-unknown',
                            'm2-three-t2-original', 'm2-three-t2-successor',
                            'm2-three-t3-never', 'm2-three-t3-reinstall'},
                'only registered lifecycle cases are implemented')
        if case_id in self._attempted:
            raise RuntimeError('case already attempted; reconcile, never repeat')
        self._attempted.add(case_id)
        # Prove the explicit maintenance target BEFORE any Registry write.
        with self.maintenance_connect() as conn:
            require(conn.info.transaction_status == TransactionStatus.IDLE, 'idle maintenance connection required')
            with conn.transaction():
                self._maintenance(conn)
        if self._registry is None:
            if self._registry_attempted:
                raise RuntimeError('Registry setup outcome requires reconciliation')
            self._registry_attempted = True
            self._registry = selected.register_selected_registry(connect=self.runtime_connect,
                packages=selected.load_selected_packages())
        require(type(self._registry) is selected.SelectedRegistry and self._registry.connect is self.runtime_connect,
                'fixture Registry connector differs')
        case = selected.resolve_selected_case(self._registry, case_id=case_id, command_connect=self.command_connect)
        graph = selected.build_selected_preparation(registry=self._registry, installation_store=case.store,
            revalidator=case.revalidator, driver=self.driver, live_directory=LivePreparedJobDirectory(),
            platform='linux/arm64', preparation_only=False)
        with self.maintenance_connect() as conn:
            require(conn.info.transaction_status == TransactionStatus.IDLE, 'idle maintenance connection required')
            with conn.transaction():
                self._maintenance(conn)
                receipts = selected.install_selected_schema_receipts(
                    conn, case=case, preparation=graph, lab_identity=self.identity)
                require(len(receipts) == 3, 'all three physical schema requirements required')
                selected.install_selected_fixture_memberships(
                    conn, case=case, lab_identity=self.identity)
        return SimpleNamespace(case=case, preparation=graph)

    def new_t2_pair(self):
        """Enroll the exact original/successor pair and freeze original graphs only."""
        original = self.new_case('m2-three-t2-original')
        successor = self.new_case('m2-three-t2-successor')
        producers = []
        for item in (original, successor):
            producers.append(selected.build_selected_refresh_history_producer(
                registry=item.case.registry,
                installation_reader=item.case.installation_service,
                preparation=item.preparation))
        return SelectedT2InstallationPair(original=original, successor=successor,
            original_producer=producers[0], successor_producer=producers[1])

    def expected_image(self, case, package_id):
        loaded = [item for item in case.packages.loaded if item.manifest.metadata.id == package_id]
        require(len(loaded) == 1 and package_id in selected.BACKEND_IDS, 'exact selected backend required')
        loaded = loaded[0]
        path = loaded.manifest.spec.runtime.backend.image_index
        artifacts = [a for a in loaded.artifacts if a.relative_path == path]
        require(len(artifacts) == 1, 'unique signed image index required')
        loader = selected.ManifestLoader({selected.ALIAS: selected.PUBLIC / 'selected-public-bundles'},
            trust_roots=case.packages.trust_roots)
        raw = loader.read_verified_artifact(loaded.source_ref, path, expected_digest=artifacts[0].digest, limit=65536)
        return resolve_image_index(raw, expected_hash=artifacts[0].digest, platform='linux/arm64').config_digest

    def snapshot(self, case, prepared):
        require(case.scope == dict(org_id='org-org', project_id='dev-project'), 'exact positive observation scope required')
        with consumer_connection(self.runtime_connect, case.scope) as conn:
            selected.verify_selected_lab_identity(conn, self.identity, maintenance=False)
            target = (case.scope['org_id'], case.scope['project_id'], UUID(case.action['installation_id']))
            bindings = conn.execute('''SELECT generation,installation_revision,package_lock_ref,desired_state,
                observed_state,enabled,operation_fence,config_ref,execution_epoch,resource_handle_ref
                FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s''', target).fetchall()
            require(len(bindings) == 1, 'one exact T1 binding required')
            rows = conn.execute('''SELECT r.resource_id,r.operation_id,r.generation,r.package_id,r.package_hash,
                r.engine_context,r.resource_name,r.owner_token_ref,r.container_id,r.create_claimed_at,
                r.cleanup_state,r.observed_release,(r.expires_at>clock_timestamp()) AS fresh
                FROM extension_runtime_resource_lease r JOIN extension_runtime_operation o
                USING(org_id,project_id,operation_id)
                WHERE r.org_id=%s AND r.project_id=%s AND o.installation_id=%s ORDER BY r.resource_id''', target).fetchall()
            events = conn.execute('''SELECT payload,payload_hash FROM extension_runtime_event
                WHERE org_id=%s AND project_id=%s AND operation_id=%s AND type='resource_registered' ''',
                ('org-org','dev-project',prepared.apply_operation)).fetchall()
        return bindings[0], rows, events

    def verify_live(self, case, prepared, binding, rows, events):
        plan = prepared.job.plan
        require(binding['generation'] == plan.generation
                and binding['installation_revision'] == prepared.installation.current_revision
                and prepared.installation.active_revision == prepared.installation.current_revision
                and binding['package_lock_ref'] == {'lockHash': case.lock.lock_hash}
                and (binding['desired_state'], binding['observed_state']) == ('disabled','ready')
                and binding['enabled'] is False and binding['operation_fence'] is True
                and binding['config_ref'] is None and binding['execution_epoch'] == 1,
                'T1 binding is not exact ready but closed state')
        require(len(rows) == 3 and len(events) == 3
                and {r['resource_id'] for r in rows} == {m.intent.resource_id for m in plan.members}
                and {(r['package_id'],r['package_hash']) for r in rows}
                    == {(bid, selected.EXPECTED[bid][1]) for bid in selected.BACKEND_IDS}
                and len({r['container_id'] for r in rows}) == 3, 'T1 resource set differs from exact plan')
        handle = binding['resource_handle_ref']
        require(type(handle) is dict and handle.get('preparationOperationId') == str(prepared.apply_operation)
                and type(handle.get('resources')) is list and len(handle['resources']) == 3,
                'T1 binding resource proof missing')
        proofs = {p['resourceId']: p for p in handle['resources']}
        observations = {event['payload']['resourceId']: event for event in events}
        require(len(proofs) == len(observations) == 3, 'duplicate T1 resource proof')
        for row in rows:
            identity = ResourceIdentity(row['owner_token_ref'])
            require(row['generation'] == plan.generation and row['operation_id'] == prepared.apply_operation
                    and row['engine_context'] == self.driver.context and row['resource_name'] == identity.name
                    and type(row['container_id']) is str and re.fullmatch('[0-9a-f]{64}',row['container_id'])
                    and row['create_claimed_at'] is not None and row['fresh'] is True
                    and row['cleanup_state'] == 'pending' and row['observed_release'] is False,
                    'T1 persisted resource ownership or liveness differs')
            key = str(row['resource_id'])
            require(key in proofs and key in observations, 'T1 exact resource proof missing')
            proof, event = proofs[key], observations[key]
            require(set(proof) == {'resourceId','containerId','packageHash','claimsHash'}
                    and proof['containerId'] == row['container_id'] and proof['packageHash'] == row['package_hash']
                    and re.fullmatch('sha256:[0-9a-f]{64}', proof['claimsHash'])
                    and event['payload'] == proof and event['payload_hash'] == _digest(proof),
                    'T1 registered event differs from binding proof')
            native = json.loads(self.driver._run('inspect','--format',CONTAINER_FORMAT,row['container_id']))
            security = native.get('security') or []
            require(native['id'] == row['container_id'] and native['name'] == '/' + identity.name
                    and native['owner'] == identity.owner and native['image'] == self.expected_image(case,row['package_id'])
                    and native['running'] is True and native['network'] == 'none' and native['readonly'] is True
                    and native['user'] == '65534:65534' and native['privileged'] is False
                    and native['capdrop'] == ['ALL'] and native['binds'] in (None,[])
                    and 'no-new-privileges' in security and any(x.startswith('seccomp=') for x in security),
                    'T1 native resource identity or isolation differs')
        return tuple(dict(row) for row in rows)

    def assert_released(self, case, prepared, before):
        binding, rows, _events = self.snapshot(case, prepared)
        require(binding['generation'] == prepared.job.plan.generation
                and binding['enabled'] is False and binding['operation_fence'] is True,
                'closed T1 generation must remain fenced')
        identity_fields = ('resource_id','generation','operation_id','package_id','package_hash',
            'engine_context','resource_name','owner_token_ref','container_id')
        require(len(before) == len(rows) == 3
                and {tuple(r[k] for k in identity_fields) for r in before}
                    == {tuple(r[k] for k in identity_fields) for r in rows}, 'T1 cleanup resource identity changed')
        require(all(row['observed_release'] is True and row['cleanup_state'] == 'released' for row in rows),
                'T1 cleanup is not proven released')
        for row in rows:
            require(self.driver.confirm_absent(row['resource_name'], row['owner_token_ref'],
                    expected_container_id=row['container_id']) is True, 'T1 physical resource still exists or is unknown')

    def preparation_snapshot(self, case, operation):
        require(case.scope == dict(org_id='org-org', project_id='dev-project')
                and case.registry.connect is self.runtime_connect, 'exact selected observation scope required')
        target = (*TenantScope(**case.scope).key, UUID(str(operation)))
        installation = UUID(case.action['installation_id'])
        with consumer_connection(self.runtime_connect, case.scope) as conn:
            selected.verify_selected_lab_identity(conn, self.identity, maintenance=False)
            op = conn.execute('''SELECT installation_id,operation_id,kind,status,phase,failure_code,revision,deadline
                FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s''', target).fetchone()
            operations = conn.execute('''SELECT installation_id,operation_id,kind,status,phase,failure_code,revision,deadline
                FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND installation_id=%s
                ORDER BY operation_id LIMIT 3''', (*target[:2], installation)).fetchall()
            resources = conn.execute('''SELECT resource_id,operation_id,generation,package_id,package_hash,
                engine_context,resource_name,owner_token_ref,container_id,create_claimed_at,cleanup_state,observed_release,
                expires_at,(expires_at<=clock_timestamp()) AS expired
                FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND operation_id=%s
                ORDER BY resource_id LIMIT 4''', target).fetchall()
            bindings = conn.execute('''SELECT generation FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s LIMIT 2''', (*target[:2], installation)).fetchall()
            events = conn.execute('''SELECT type,payload,payload_hash FROM extension_runtime_event
                WHERE org_id=%s AND project_id=%s AND operation_id=%s ORDER BY sequence LIMIT 65''', target).fetchall()
            def pending_for(identity):
                return conn.execute('''SELECT count(*) AS pending FROM extension_runtime_outbox b
                    JOIN extension_runtime_event e USING(org_id,project_id,event_id)
                    WHERE b.org_id=%s AND b.project_id=%s AND e.operation_id=%s
                    AND b.consumer_id='runtime-reconciler' AND b.delivered_at IS NULL''',
                    (*target[:2], identity)).fetchone()['pending']
            pending = pending_for(target[2])
            verifies = [row for row in operations if row['kind'] == 'runtime-verify']
            verify_pending = pending_for(verifies[0]['operation_id']) if len(verifies) == 1 else None
        require(len(operations) < 3 and len(resources) == 3 and len(events) < 65,
                'bounded exact preparation observations required')
        history = case.store.get_installation(**case.scope, installation_id=case.action['installation_id'])
        return dict(operation=op, operations=operations, resources=resources, bindings=bindings,
            events=events, pending=pending, verify_pending=verify_pending, installation=history)

    @staticmethod
    def _closed_job(case, job, operation):
        require(type(job) is PreparedJob and job.tenant_scope == TenantScope(**case.scope)
                and job.plan.installation_id == UUID(case.action['installation_id'])
                and job.plan.operation_id == operation and job._closed.done()
                and not job._closed.cancelled() and job._owner._task.done()
                and not job._owner._task.cancelled(), 'exact settled preparation job required')

    def verify_failed_preparation(self, case, job, operation, failure, observation):
        self._closed_job(case, job, operation)
        require(type(failure) is SecondSelectedMemberFailure and job._closed.exception() is failure.error
                and job._owner._task.exception() is failure.error, 'original injected failure identity required')
        op = observation['operation']
        require(op is not None and op['operation_id'] == operation
                and op['installation_id'] == job.plan.installation_id
                and (op['kind'], op['phase'], op['status'], op['failure_code']) ==
                    ('runtime-apply','preparing','failed','PREPARATION_EXECUTION_FAILED')
                and observation['operations'] == [op] and observation['bindings'] == [],
                'only exact uncommitted failed preparation allowed')
        history = observation['installation']
        require(history.state == 'approved' and history.active_revision is None
                and (history.current_revision, history.etag_version) ==
                    (case.approved.current_revision, case.approved.etag_version), 'approved history changed')
        members, rows = job.plan.members, observation['resources']
        require(len(members) == len(rows) == 3
                and {(x.selected.id, x.selected.content_hash) for x in members} ==
                    {(bid, selected.EXPECTED[bid][1]) for bid in selected.BACKEND_IDS}
                and failure.seen == [(x.selected.id, x.selected.content_hash) for x in members[:2]]
                and len({row['resource_id'] for row in rows}) == 3,
                'exact failed three-member set required')
        indexed = {row['resource_id']:row for row in rows}
        require(set(indexed) == {x.intent.resource_id for x in members}, 'resource intent identities differ')
        first = None
        for index, member in enumerate(members):
            row, intent = indexed[member.intent.resource_id], member.intent
            require((row['operation_id'], row['generation'], row['package_id'], row['package_hash'],
                    row['engine_context'], row['resource_name'], row['owner_token_ref']) ==
                (operation, job.plan.generation, member.selected.id, member.selected.content_hash,
                    intent.engine_context, intent.identity.name, intent.identity.owner)
                and row['observed_release'] is True and row['cleanup_state'] == 'released',
                'failed resource ownership or cleanup differs')
            if index == 0:
                require(type(row['container_id']) is str and re.fullmatch('[0-9a-f]{64}', row['container_id'])
                        and isinstance(row['create_claimed_at'], datetime)
                        and row['create_claimed_at'].utcoffset() is not None, 'first resource create proof required')
                first = row
                require(self.driver.confirm_absent(row['resource_name'],row['owner_token_ref'],
                    expected_container_id=row['container_id']) is True, 'created resource absence unknown')
            else:
                require(row['container_id'] is None and row['create_claimed_at'] is None,
                        'unopened resource unexpectedly claimed')
                require(self.driver.confirm_name_absent(row['resource_name'],row['owner_token_ref']) is True,
                        'unclaimed resource name absence unknown')
        events = observation['events']
        require(all(event['payload_hash'] == _digest(event['payload']) for event in events), 'event payload hash differs')
        failures = [event['payload'] for event in events if event['type'] == 'preparation_failed']
        registrations = [event['payload'] for event in events if event['type'] == 'resource_registered']
        from aos_api.extension_runtime.contracts import RegistrationDescription
        loaded = [item for item in case.packages.loaded if item.manifest.metadata.id == first['package_id']]
        require(len(loaded) == 1, 'unique first signed package required')
        claims = RegistrationDescription(contributions=loaded[0].manifest.spec.contributions)
        registration = dict(resourceId=str(first['resource_id']),containerId=first['container_id'],
            packageHash=first['package_hash'],claimsHash=_digest(claims.model_dump(mode='json',by_alias=True)))
        require(failures == [dict(phase='preparing',failureCode='PREPARATION_EXECUTION_FAILED')]
                and registrations == [registration]
                and not any(event['type'] == 'preparation_committed' for event in events),
                'failure or registration events differ')

    def _unknown_record_proof(self, case, job, operation, fault, snapshot, *, stage):
        from unknown_create_fault_r52 import SelectedUnknownCreateFault
        from aos_api.extension_runtime.preparation_plan import PreparationPlan
        self._closed_job(case,job,operation)
        require(type(fault) is SelectedUnknownCreateFault and type(job.plan) is PreparationPlan
                and case.case_id == 'm2-three-t1-unknown'
                and case.scope == dict(org_id='org-org',project_id='dev-project')
                and case.registry.connect is self.runtime_connect and stage in {'uncertain','released','settled'},
                'fixed unknown preparation stage required')
        fault.assert_injected_error(fault.error)
        require(job._closed.exception() is fault.error and job._owner._task.exception() is fault.error
                and isinstance(fault.error.__cause__,RuntimeConflict)
                and fault.create_attempts == 1 and fault.remove_attempts == (1 if stage=='uncertain' else 2),
                'original unknown and finalizer refusal or attempt counts differ')
        plan, op = job.plan, snapshot['operation']
        require(op is not None and op['operation_id'] == operation and op['installation_id'] == plan.installation_id
                and (op['kind'],op['phase'],op['status'],op['failure_code']) ==
                    ('runtime-apply','preparing','failed' if stage=='settled' else 'needs_attention','RESOURCE_CLEANUP_UNCERTAIN')
                and type(op['revision']) is int and op['revision'] > 0 and op['deadline'] == plan.deadline
                and snapshot['operations'] == [op] and snapshot['bindings'] == [], 'unknown operation identity or stage differs')
        history = snapshot['installation']
        require(history.state == 'approved' and history.active_revision is None
                and (history.current_revision,history.etag_version) ==
                    (case.approved.current_revision,case.approved.etag_version), 'unknown preparation changed history')
        members, rows = plan.members, snapshot['resources']
        require(len(members) == len(rows) == 3
                and {(x.selected.id,x.selected.content_hash) for x in members} ==
                    {(bid,selected.EXPECTED[bid][1]) for bid in selected.BACKEND_IDS}
                and len({row['resource_id'] for row in rows}) == 3, 'unknown selected three-member set differs')
        indexed = {row['resource_id']:row for row in rows}
        require(set(indexed) == {x.intent.resource_id for x in members}, 'unknown resource intents differ')
        first = None
        for index, member in enumerate(members):
            row,intent = indexed[member.intent.resource_id],member.intent
            require(intent.replayed is False and member.container_id is None
                    and intent.engine_context == self.driver.context == 'colima-aos-extension'
                    and (row['operation_id'],row['generation'],row['package_id'],row['package_hash'],
                         row['engine_context'],row['resource_name'],row['owner_token_ref']) ==
                        (operation,plan.generation,member.selected.id,member.selected.content_hash,
                         intent.engine_context,intent.identity.name,intent.identity.owner)
                    and row['container_id'] is None and row['expires_at'] == plan.deadline
                    and isinstance(row['expires_at'],datetime) and row['expires_at'].utcoffset() is not None
                    and type(row['expired']) is bool, 'unknown resource identity expiry or NULL receipt differs')
            if index == 0:
                first = row
                require(isinstance(row['create_claimed_at'],datetime)
                        and row['create_claimed_at'].utcoffset() is not None
                        and row['observed_release'] is (stage!='uncertain')
                        and row['cleanup_state'] == ('uncertain' if stage=='uncertain' else 'released')
                        and fault.error.cleanup_reference == dict(context=intent.engine_context,
                            name=intent.identity.name,owner=intent.identity.owner), 'unknown first-resource proof differs')
            else:
                require(row['create_claimed_at'] is None and row['observed_release'] is True
                        and row['cleanup_state'] == 'released', 'unknown unopened intent not released')
        if stage != 'uncertain':
            require(first['expired'] is True, 'released unknown resource was not observed naturally expired')
        events = snapshot['events']
        require(all(event['payload_hash'] == _digest(event['payload']) for event in events), 'unknown event hash differs')
        def payloads(kind):return [event['payload'] for event in events if event['type']==kind]
        first_payload = dict(resourceId=str(first['resource_id']))
        cancelled = payloads('resource_intent_cancelled')
        require(payloads('resource_uncertain') == [first_payload]
                and len(cancelled) == 2 and all(set(p)=={'resourceId'} for p in cancelled)
                and {p['resourceId'] for p in cancelled} == {str(x.intent.resource_id) for x in members[1:]}
                and payloads('resource_released') == ([] if stage=='uncertain' else [first_payload])
                and payloads('failed_preparation_settled') == ([dict(phase='preparing')] if stage=='settled' else [])
                and not any(payloads(kind) for kind in ('resource_registered','preparation_committed','preparation_failed')),
                'unknown lifecycle event sequence differs')
        return first

    def verify_unknown_preparation(self, case, job, operation, fault, snapshot, *, stage):
        self._unknown_record_proof(case,job,operation,fault,snapshot,stage=stage)
        for index, member in enumerate(job.plan.members):
            identity = member.intent.identity
            if index == 0:
                require(self.driver.confirm_absent(identity.name,identity.owner,
                    expected_container_id=fault.oracle_cid) is True, 'unknown first oracle or name still present')
            else:
                require(self.driver.confirm_name_absent(identity.name,identity.owner) is True,
                        'unknown unopened owned name present')

    async def wait_unknown_expiry(self, case, job, operation, fault, *, timeout_seconds=330):
        require(type(timeout_seconds) is int and 1 <= timeout_seconds <= 330, 'bounded natural expiry wait required')
        deadline = asyncio.get_running_loop().time()+timeout_seconds
        while True:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('natural expiry observation timed out; never rewrite expiry')
            snapshot = await _settled(asyncio.to_thread(self.preparation_snapshot,case,operation))
            first = self._unknown_record_proof(case,job,operation,fault,snapshot,stage='uncertain')
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('natural expiry read settled after deadline')
            if first['expired'] is True:
                return snapshot
            await asyncio.sleep(.25)

    async def recover_unknown_preparation(self, case, job, operation, fault, *, timeout_seconds=330):
        require(type(timeout_seconds) is int and 1 <= timeout_seconds <= 330
                and operation not in self._unknown_recovery_attempted, 'unknown recovery already attempted or invalid bound')
        self._unknown_recovery_attempted.add(operation)
        snapshot = await _settled(asyncio.to_thread(self.preparation_snapshot,case,operation))
        await _settled(asyncio.to_thread(self.verify_unknown_preparation,case,job,operation,fault,snapshot,stage='uncertain'))
        first = self._unknown_record_proof(case,job,operation,fault,snapshot,stage='uncertain')
        require(first['expired'] is False, 'initial fresh-resource refusal must be observed')
        recovery = ExpiredResourceRecovery(connect=self.runtime_connect,driver=self.driver)
        target = dict(**case.scope,resource_id=job.plan.members[0].intent.resource_id)
        before = fault.remove_attempts
        try:
            await _settled(asyncio.to_thread(recovery.run_one,**target))
        except ResourceStillLive:
            pass  # Known no-OCI admission refusal, not a retry of unknown create.
        else:
            raise ValueError('fresh original recovery did not refuse the resource')
        require(fault.create_attempts == 1 and fault.remove_attempts == before, 'fresh recovery touched engine')
        expired = await self.wait_unknown_expiry(case,job,operation,fault,timeout_seconds=timeout_seconds)
        await _settled(asyncio.to_thread(self.verify_unknown_preparation,case,job,operation,fault,expired,stage='uncertain'))
        result = await _settled(asyncio.to_thread(recovery.run_one,**target))
        require(result == 'released' and fault.create_attempts == 1 and fault.remove_attempts == before+1,
                'expired recovery unresolved or engine attempt count differs; no retry')
        released = await _settled(asyncio.to_thread(self.preparation_snapshot,case,operation))
        await _settled(asyncio.to_thread(self.verify_unknown_preparation,case,job,operation,fault,released,stage='released'))
        revision = released['operation']['revision']
        settled = await _settled(asyncio.to_thread(recovery.settle_preparation,**case.scope,
            operation_id=operation,expected_revision=revision))
        require(settled.operation_id == operation and settled.phase == 'preparing' and settled.status == 'failed'
                and settled.revision == revision+1 and settled.replayed is False, 'original failed-settle receipt differs')
        final = await _settled(asyncio.to_thread(self.preparation_snapshot,case,operation))
        require(final['operation']['revision'] == settled.revision, 'failed-settle current revision differs')
        await _settled(asyncio.to_thread(self.verify_unknown_preparation,case,job,operation,fault,final,stage='settled'))

    async def reconcile_preparation_outbox(self, case, job, operation, worker, *,
            failure=None, unknown=None, prepared=None, before=None, timeout_seconds=120):
        unknown_branch = False
        if unknown is not None:
            from unknown_create_fault_r52 import SelectedUnknownCreateFault
            unknown_branch = type(unknown) is SelectedUnknownCreateFault and failure is None and prepared is None and before is None
        require(type(timeout_seconds) is int and 1 <= timeout_seconds <= 120
                and type(worker) is PreparationWorker
                and ((type(failure) is SecondSelectedMemberFailure and unknown is None and prepared is None and before is None)
                    or unknown_branch or (failure is None and unknown is None and prepared is not None and before is not None)),
                'one fixed closed preparation branch required')
        expected = 'failed' if failure is not None or unknown_branch else 'succeeded'
        def observe():
            snapshot = self.preparation_snapshot(case, operation)
            if failure is not None:
                self.verify_failed_preparation(case,job,operation,failure,snapshot)
            elif unknown_branch:
                self.verify_unknown_preparation(case,job,operation,unknown,snapshot,stage='settled')
            else:
                self._closed_job(case,job,operation)
                op, history = snapshot['operation'], snapshot['installation']
                require(prepared.job is job and job._closed.exception() is None
                        and job._owner._task.exception() is None
                        and op is not None and op['operation_id'] == operation
                        and op['installation_id'] == job.plan.installation_id
                        and (op['kind'],op['phase'],op['status']) == ('runtime-apply','succeeded','succeeded')
                        and len(snapshot['operations']) == 2
                        and all(x['installation_id'] == job.plan.installation_id for x in snapshot['operations'])
                        and {(x['operation_id'],x['kind'],x['phase'],x['status']) for x in snapshot['operations']} ==
                            {(operation,'runtime-apply','succeeded','succeeded'),
                             (prepared.verify_operation,'runtime-verify','succeeded','succeeded')}
                        and snapshot['verify_pending'] == 0 and history.state == 'active'
                        and (history.current_revision,history.active_revision,history.etag_version) ==
                            (prepared.installation.current_revision,prepared.installation.active_revision,
                             prepared.installation.etag_version), 'closed verified preparation changed')
                self.assert_released(case,prepared,before)
            require(type(snapshot['pending']) is int and snapshot['pending'] >= 0, 'exact pending count required')
            return snapshot['pending']
        # A known terminal status and absence proof precedes any consumer action.
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        pending = await _settled(asyncio.to_thread(observe))
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError('terminal observation expired before consumer construction')
        consumer = PreparationConsumer(connect=self.runtime_connect,worker=worker,
            installation_id=case.action['installation_id'],**case.scope)
        try:
            while pending:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError('terminal event observation timed out; no runtime retry')
                # Revalidate immediately before each original terminal-only delivery.
                pending = await _settled(asyncio.to_thread(observe))
                if not pending:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError('terminal observation expired before next delivery; no runtime retry')
                result = await _settled(consumer.run_once())
                require(result is None or (result.operation_id == operation and result.operation_status == expected
                        and result.delivery_status == 'acknowledged'), 'terminal event delivery differs')
                pending = await _settled(asyncio.to_thread(observe))
                if pending:
                    await asyncio.sleep(.05)
            require(await _settled(asyncio.to_thread(observe)) == 0, 'terminal events remain pending')
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('terminal observation completed after deadline; no runtime retry')
        finally:
            await _settled(consumer.stop())


    def retirement_snapshot(self, case):
        require(case.scope == dict(org_id='org-org',project_id='dev-project'), 'exact retirement scope required')
        target=('org-org','dev-project',UUID(case.action['installation_id']))
        with consumer_connection(self.runtime_connect,case.scope) as conn:
            selected.verify_selected_lab_identity(conn, self.identity, maintenance=False)
            head=conn.execute('''SELECT i.installation_pk,i.installation_id,i.current_revision,i.etag_version,r.state
                FROM bundle_installation i JOIN bundle_installation_revision r
                  ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk
                  AND r.revision=i.current_revision
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',target).fetchone()
            require(head is not None,'exact retirement Installation required')
            bindings=conn.execute('''SELECT * FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s''',target).fetchall()
            require(len(bindings)==1,'one retirement generation required')
            def data(query,args=target):
                return [row['data'] for row in conn.execute(query,args).fetchall()]
            revisions=data('''SELECT to_jsonb(r) AS data FROM bundle_installation_revision r
                JOIN bundle_installation i USING(org_id,project_id,installation_pk)
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s ORDER BY r.revision''')
            installation_events=data('''SELECT to_jsonb(e) AS data FROM bundle_installation_event e
                JOIN bundle_installation i USING(org_id,project_id,installation_pk)
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s ORDER BY e.sequence''')
            commands=data('''SELECT to_jsonb(c) AS data FROM bundle_installation_command c
                WHERE org_id=%s AND project_id=%s AND response_json->>'installationId'=%s
                ORDER BY operation,idempotency_key''',('org-org','dev-project',case.action['installation_id']))
            operations=data('''SELECT to_jsonb(o) AS data FROM extension_runtime_operation o
                WHERE org_id=%s AND project_id=%s AND installation_id=%s ORDER BY operation_id''')
            resources=data('''SELECT to_jsonb(r) AS data FROM extension_runtime_resource_lease r
                JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
                WHERE r.org_id=%s AND r.project_id=%s AND o.installation_id=%s ORDER BY r.resource_id''')
            events=data('''SELECT to_jsonb(e) AS data FROM extension_runtime_event e
                JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
                WHERE e.org_id=%s AND e.project_id=%s AND o.installation_id=%s ORDER BY e.operation_id,e.sequence''')
            receipts=conn.execute('''SELECT r.*,content_hash='sha256:'||encode(
                sha256(convert_to(authority_data::text,'UTF8')),'hex') AS hash_valid
                FROM extension_runtime_uninstall_receipt r
                WHERE org_id=%s AND project_id=%s AND installation_id=%s ORDER BY receipt_id''',target).fetchall()
            counts=conn.execute('''SELECT
                (SELECT count(*) FROM extension_runtime_configuration WHERE org_id=%s AND project_id=%s AND installation_id=%s) AS configurations,
                (SELECT count(*) FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND installation_id=%s AND kind IN ('configure','enable','disable')) AS controls,
                (SELECT count(*) FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND installation_id=%s AND status NOT IN ('succeeded','failed','cancelled')) AS unresolved,
                (SELECT count(*) FROM extension_dispatch_cutover_operation WHERE org_id=%s AND project_id=%s AND target_installation_id=%s) AS cutovers,
                (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s) AS dispatches,
                (SELECT count(*) FROM automation_occurrence WHERE org_id=%s AND project_id=%s AND installation_id=%s) AS occurrences,
                (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id=%s AND project_id=%s AND installation_id=%s) AS executions''',target*7).fetchone()
        return dict(head=dict(head),binding=dict(bindings[0]),revisions=revisions,installation_events=installation_events,commands=commands,
            operations=operations,resources=resources,events=events,receipts=[dict(x) for x in receipts],counts=dict(counts))

    def verify_never_enabled(self, case, prepared, before, snapshot):
        require(case.case_id in {'m2-three-t3-never','m2-three-t3-reinstall'}
                and case.scope==dict(org_id='org-org',project_id='dev-project'),'fixed never-enabled case required')
        self._closed_job(case,prepared.job,prepared.apply_operation)
        require(prepared.job._closed.exception() is None and prepared.job._owner._task.exception() is None,
                'successful closed original preparation required')
        head,binding=snapshot['head'],snapshot['binding']
        require(head['state']=='active' and str(head['installation_id'])==case.action['installation_id']
                and (head['current_revision'],head['etag_version'])==
                    (prepared.installation.current_revision,prepared.installation.etag_version)
                and prepared.installation.active_revision==head['current_revision']
                and binding['generation']==prepared.job.plan.generation
                and str(binding['installation_id'])==case.action['installation_id']
                and (binding['org_id'],binding['project_id'])==('org-org','dev-project')
                and binding['installation_revision']==head['current_revision']
                and binding['package_lock_ref'].get('lockHash')==case.lock.lock_hash
                and binding['desired_state']=='disabled' and binding['observed_state']=='unknown'
                and binding['enabled'] is False and binding['operation_fence'] is True and binding['config_ref'] is None,
                'never-enabled head or binding differs')
        require(set(snapshot['counts'])=={'configurations','controls','unresolved','cutovers','dispatches','occurrences','executions'}
                and all(type(x) is int and x==0 for x in snapshot['counts'].values())
                and snapshot['receipts']==[] and snapshot['commands'] and snapshot['events']
                and len(snapshot['revisions'])==head['current_revision']
                and len(snapshot['installation_events'])==head['current_revision']
                and snapshot['revisions'][-1]['state']=='active','never-enabled history or zero-activity proof differs')
        require(len(snapshot['operations'])==2 and {
            (str(x['operation_id']),str(x['installation_id']),x['kind'],x['phase'],x['status']) for x in snapshot['operations']}=={
            (str(prepared.apply_operation),case.action['installation_id'],'runtime-apply','succeeded','succeeded'),
            (str(prepared.verify_operation),case.action['installation_id'],'runtime-verify','succeeded','succeeded')},
            'only the two original successful preparation operations required')
        fields=('resource_id','generation','operation_id','package_id','package_hash','engine_context',
                'resource_name','owner_token_ref','container_id')
        identity=lambda row:tuple(str(row[k]) for k in fields)
        rows=snapshot['resources']
        require(len(rows)==len(before)==3 and len({str(x['resource_id']) for x in rows})==3
                and {identity(x) for x in rows}=={identity(x) for x in before}
                and all(x['cleanup_state']=='released' and x['observed_release'] is True for x in rows),
                'never-enabled exact three released resources required')
        for row in rows:
            require(self.driver.confirm_absent(row['resource_name'],row['owner_token_ref'],
                expected_container_id=row['container_id']) is True,'never-enabled physical absence is unknown')

    def verify_retired(self, case, prepared, before, baseline, after, receipt):
        from aos_api.asset_registry.installation_store import CommandReceipt
        require(type(receipt) is CommandReceipt and receipt.status_code==200 and receipt.replayed is False,
                'original nonreplayed uninstall Receipt required')
        revision=baseline['head']['current_revision']
        require(after['head']=={**baseline['head'],'current_revision':revision+1,'etag_version':revision+1,'state':'uninstalled'}
                and receipt.response_etag==f'"{revision+1}"'
                and receipt.response_json.get('installationId')==case.action['installation_id']
                and receipt.response_json.get('state')=='uninstalled'
                and receipt.response_json.get('etagVersion')==revision+1,'exact uninstall Installation transition differs')
        require(after['binding']=={**baseline['binding'],'desired_state':'uninstalled','observed_state':'stopped',
                'revision':baseline['binding']['revision']+1},'retirement changed generation, epoch or binding authority')
        require(len(after['revisions'])==len(baseline['revisions'])+1
                and after['revisions'][:-1]==baseline['revisions']
                and after['revisions'][-1]['revision']==revision+1 and after['revisions'][-1]['state']=='uninstalled'
                and all(after[key]==baseline[key] for key in ('resources','operations','events','counts')),
                'uninstall changed immutable history or runtime effects')
        install_events=after['installation_events']
        require(len(install_events)==len(baseline['installation_events'])+1
                and install_events[:-1]==baseline['installation_events']
                and all(install_events[-1].get(k)==v for k,v in dict(sequence=revision+1,
                    from_revision=revision,to_revision=revision+1,from_state='active',to_state='uninstalled',
                    actor=case.action['actor']).items()),'uninstall changed installation event history')
        index=lambda rows:{(r['operation'],r['idempotency_key']):r for r in rows}
        old,new=index(baseline['commands']),index(after['commands'])
        key=('bundle_installations.uninstall',case.case_id+'-uninstall')
        require(len(new)==len(after['commands'])==len(old)+1 and set(new)==set(old)|{key}
                and key not in old and all(new[k]==v for k,v in old.items())
                and new[key]['subject']==case.action['actor'] and new[key]['response_json']==receipt.response_json
                and new[key]['response_etag']==receipt.response_etag,'exact one uninstall command or history differs')
        rows=after['receipts'];require(len(rows)==1,'one native retirement Receipt required');row=rows[0]
        expected=dict(orgId='org-org',projectId='dev-project',installationId=case.action['installation_id'],
            generation=str(prepared.job.plan.generation),installationRevision=revision,
            bindingRevision=baseline['binding']['revision']+1,retirementKind='never_enabled',releasedResourceCount=3,
            configurationCount=0,enableCount=0,dispatchCount=0,businessExecutionCount=0,actor=case.action['actor'])
        require((row['org_id'],row['project_id'])==('org-org','dev-project')
                and str(row['installation_id'])==case.action['installation_id']
                and row['generation']==prepared.job.plan.generation and row['installation_revision']==revision
                and row['binding_revision']==baseline['binding']['revision']+1
                and row['retirement_kind']=='never_enabled' and row['disable_operation_id'] is None
                and row['activation_operation_id'] is None and row['actor']==case.action['actor']
                and row['authority_data']==expected and row['hash_valid'] is True
                and re.fullmatch('sha256:[0-9a-f]{64}',row['content_hash']), 'native retirement Receipt authority differs')
        for resource in before:
            require(self.driver.confirm_absent(resource['resource_name'],resource['owner_token_ref'],
                expected_container_id=resource['container_id']) is True,'retired physical resource is not absent')

    def retire_never_enabled(self, case, prepared, before):
        from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
        identity=case.action['installation_id']
        if identity in self._retirement_attempted:
            raise RuntimeError('retirement already attempted; reconcile, never repeat')
        baseline=self.retirement_snapshot(case)
        self.verify_never_enabled(case,prepared,before,baseline)
        self._retirement_attempted.add(identity)
        receipt=case.installation_service.uninstall(**case.action,
            request=UninstallInstallationRequest(reason='M2 isolated never-enabled retirement'),
            idempotency_key=case.case_id+'-uninstall',if_match=f'"{baseline["head"]["etag_version"]}"')
        after=self.retirement_snapshot(case)
        self.verify_retired(case,prepared,before,baseline,after,receipt)
        return after

    def reject_retired_preparation(self, case, prepared, retired):
        from aos_api.asset_registry.errors import RevisionConflictError
        identity=case.action['installation_id']
        require(case.case_id=='m2-three-t3-never' and case.scope==dict(org_id='org-org',project_id='dev-project')
                and retired['head']['state']=='uninstalled' and str(retired['head']['installation_id'])==identity,
                'exact retired negative target required')
        if identity in self._retired_negative_attempted:
            raise RuntimeError('retired negative already attempted; no resend')
        self._retired_negative_attempted.add(identity)
        called=[]
        def tripwire():
            called.append(True)
            raise RuntimeError('retired preparation reached admission')
        for label,etag,error,message in (
            ('stale',prepared.installation.etag_version,RevisionConflictError,'installation revision does not match'),
            ('current',retired['head']['etag_version'],RuntimeConflict,'installation state does not permit preparation')):
            try:
                case.lifecycle.request_preparation(**case.action,kind='runtime-apply',
                    idempotency_key=case.case_id+'-retired-'+label,if_match=f'"{etag}"',preparation_admission=tripwire)
            except error as exc:
                require(str(exc)==message,'retired preparation failed for another reason')
            else:
                raise ValueError('retired preparation was not rejected')
            require(not called and self.retirement_snapshot(case)==retired,
                    'retired request reached admission or changed history')

    def verify_reinstall(self, old_case, old_prepared, old_before, retired, case, prepared, before):
        require(old_case.case_id=='m2-three-t3-never' and case.case_id=='m2-three-t3-reinstall'
                and case.scope==old_case.scope==dict(org_id='org-org',project_id='dev-project')
                and case.action['installation_id']!=old_case.action['installation_id']
                and prepared.job.plan.generation!=old_prepared.job.plan.generation
                and case.packages is old_case.packages,'new four-package Installation and generation required')
        expected={('aos',bid,version,digest) for bid,(version,digest) in selected.EXPECTED.items()}
        for current in (old_case,case):
            require(len(current.lock.payload.resolved)==4 and {
                (x.publisher,x.id,x.version,x.content_hash) for x in current.lock.payload.resolved}==expected,
                'reinstall signed four-package membership differs')
        require(len(before)==len(old_before)==3 and all(
            len({str(x[field]) for x in before})==3 and not {str(x[field]) for x in before}&{str(x[field]) for x in old_before}
            for field in ('resource_id','container_id','resource_name','owner_token_ref')),
            'reinstall reused an old physical or resource identity')
        require(self.retirement_snapshot(old_case)==retired,'reinstall changed old retirement history')
        for row in old_before:
            require(self.driver.confirm_absent(row['resource_name'],row['owner_token_ref'],
                expected_container_id=row['container_id']) is True,'reinstall resurrected an old resource')


@pytest.fixture(scope='module')
def selected_lab(pytestconfig):
    lab = pytestconfig.stash.get(SELECTED_LAB, None)
    if type(lab) is not SelectedLifecycleLab:
        raise RuntimeError('fixed qualified three-backend runner required; no default connection')
    return lab


def test_t1_exact_four_package_prepare_verify_and_physical_release(selected_lab, monkeypatch):
    async def exercise():
        fixture = await _settled(asyncio.to_thread(selected_lab.new_case, 'm2-three-t1'))
        case = fixture.case
        async with selected.SelectedPreparationSession(
                case=case, preparation=fixture.preparation, lab_identity=selected_lab.identity) as session:
            prepared = await session.prepare_and_verify()
            binding, rows, events = await _settled(asyncio.to_thread(selected_lab.snapshot, case, prepared))
            before = await _settled(asyncio.to_thread(selected_lab.verify_live, case, prepared, binding, rows, events))
        await _settled(asyncio.to_thread(selected_lab.assert_released, case, prepared, before))
        historical = await _settled(asyncio.to_thread(case.store.get_installation,
            **case.scope, installation_id=case.action['installation_id']))
        require(historical.state == 'active' and historical.etag_version == prepared.installation.etag_version,
                'closing T1 owner must not rewrite Installation history')
        worker = fixture.preparation.scheduler.factory.worker
        async def refuse_restart(**_kwargs):
            raise ValueError('terminal reconciliation must not start a worker')
        with monkeypatch.context() as local:
            local.setattr(worker,'start',refuse_restart)
            await selected_lab.reconcile_preparation_outbox(case,prepared.job,prepared.apply_operation,worker,
                prepared=prepared,before=before)
    asyncio.run(exercise())


def test_t1_second_member_failure_releases_only_owned_resources(selected_lab, monkeypatch):
    async def exercise():
        fixture = await _settled(asyncio.to_thread(selected_lab.new_case,'m2-three-t1-failure'))
        case, graph = fixture.case, fixture.preparation
        worker = graph.scheduler.factory.worker
        failure, jobs = SecondSelectedMemberFailure(worker.load_record), []
        started = False
        original_start = worker.start
        async def capture_once(**kwargs):
            nonlocal started
            require(not started, 'failed preparation must never restart')
            started = True
            job = await original_start(**kwargs)
            jobs.append(job)
            return job
        with monkeypatch.context() as local:
            local.setattr(worker,'load_record',failure)
            local.setattr(worker,'start',capture_once)
            session = selected.SelectedPreparationSession(
                case=case, preparation=graph, lab_identity=selected_lab.identity)
            await session.start()
            try:
                operation = await session.request('runtime-apply')
            except BaseException:
                await _settled(session.close())
                raise
            await await_exact_host_failure(session,failure.error)
            require(len(jobs) == 1, 'one original failed job required')
            job = jobs[0]
            snapshot = await _settled(asyncio.to_thread(selected_lab.preparation_snapshot,case,operation))
            await _settled(asyncio.to_thread(selected_lab.verify_failed_preparation,
                case,job,operation,failure,snapshot))
            await selected_lab.reconcile_preparation_outbox(case,job,operation,worker,failure=failure)
            require(len(jobs) == 1, 'terminal observation restarted preparation')
    asyncio.run(exercise())


def test_t1_unknown_create_natural_expiry_recovery_without_recreate(selected_lab, monkeypatch):
    async def exercise():
        from unknown_create_fault_r52 import SelectedUnknownCreateFault
        fixture = await _settled(asyncio.to_thread(selected_lab.new_case,'m2-three-t1-unknown'))
        case, graph = fixture.case, fixture.preparation
        worker, driver = graph.scheduler.factory.worker, selected_lab.driver
        fault, jobs, started = SelectedUnknownCreateFault(driver), [], False
        original_start = worker.start
        with monkeypatch.context() as local:
            async def capture_once(**kwargs):
                nonlocal started
                require(not started, 'unknown preparation must never restart')
                started = True
                job = await original_start(**kwargs)
                jobs.append(job)
                try:
                    # No await on the successful path before bind/driver patch.
                    image = selected_lab.expected_image(case,job.plan.members[0].selected.id)
                    fault.bind(job,image)
                    local.setattr(driver,'create_session',fault.create_session)
                    local.setattr(driver,'remove_owned',fault.remove_owned)
                except BaseException:
                    await _settled(job.stop())
                    raise
                return job
            local.setattr(worker,'start',capture_once)
            session = selected.SelectedPreparationSession(
                case=case, preparation=graph, lab_identity=selected_lab.identity)
            await session.start()
            try:
                operation = await session.request('runtime-apply')
            except BaseException:
                await _settled(session.close())
                raise
            await await_unknown_host_failure(session,fault)
            require(len(jobs) == 1, 'one captured unknown preparation required')
            job = jobs[0]
            await selected_lab.recover_unknown_preparation(case,job,operation,fault)
            await selected_lab.reconcile_preparation_outbox(case,job,operation,worker,unknown=fault)
            require(len(jobs) == 1 and fault.create_attempts == 1 and fault.remove_attempts == 2,
                    'unknown recovery recreated resources or repeated cleanup')
    asyncio.run(exercise())


def test_t3_never_enabled_uninstall_reinstall_preserves_history(selected_lab, monkeypatch):
    async def exercise():
        fixture=await _settled(asyncio.to_thread(selected_lab.new_case,'m2-three-t3-never'))
        case=fixture.case
        async with selected.SelectedPreparationSession(
                case=case, preparation=fixture.preparation, lab_identity=selected_lab.identity) as session:
            prepared=await session.prepare_and_verify()
            binding,rows,events=await _settled(asyncio.to_thread(selected_lab.snapshot,case,prepared))
            before=await _settled(asyncio.to_thread(selected_lab.verify_live,case,prepared,binding,rows,events))
        await _settled(asyncio.to_thread(selected_lab.assert_released,case,prepared,before))
        async def refuse_restart(**_kwargs):
            raise ValueError('terminal retirement reconciliation must not start a worker')
        worker=fixture.preparation.scheduler.factory.worker
        with monkeypatch.context() as local:
            local.setattr(worker,'start',refuse_restart)
            await selected_lab.reconcile_preparation_outbox(case,prepared.job,prepared.apply_operation,worker,
                prepared=prepared,before=before)
        retired=await _settled(asyncio.to_thread(selected_lab.retire_never_enabled,case,prepared,before))
        await _settled(asyncio.to_thread(selected_lab.reject_retired_preparation,case,prepared,retired))
        replacement=await _settled(asyncio.to_thread(selected_lab.new_case,'m2-three-t3-reinstall'))
        new_case=replacement.case
        async with selected.SelectedPreparationSession(
                case=new_case, preparation=replacement.preparation,
                lab_identity=selected_lab.identity) as session:
            new_prepared=await session.prepare_and_verify()
            binding,rows,events=await _settled(asyncio.to_thread(selected_lab.snapshot,new_case,new_prepared))
            new_before=await _settled(asyncio.to_thread(selected_lab.verify_live,new_case,new_prepared,binding,rows,events))
            await _settled(asyncio.to_thread(selected_lab.verify_reinstall,case,prepared,before,retired,
                new_case,new_prepared,new_before))
        await _settled(asyncio.to_thread(selected_lab.assert_released,new_case,new_prepared,new_before))
        worker=replacement.preparation.scheduler.factory.worker
        with monkeypatch.context() as local:
            local.setattr(worker,'start',refuse_restart)
            await selected_lab.reconcile_preparation_outbox(new_case,new_prepared.job,new_prepared.apply_operation,worker,
                prepared=new_prepared,before=new_before)
        await _settled(asyncio.to_thread(selected_lab.retire_never_enabled,new_case,new_prepared,new_before))
        require(await _settled(asyncio.to_thread(selected_lab.retirement_snapshot,case))==retired,
                'replacement cleanup changed old immutable history')
    asyncio.run(exercise())
