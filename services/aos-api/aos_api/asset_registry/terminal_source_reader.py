"""Terminal source facts: private v13 wire kernel under construction.

The concrete Port is an unwired candidate. Complete historical authority, SQL,
native qualification and complex-history positives remain unfinished. Decoded
facts never grant execution authority.
"""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime, time
import json
import hashlib
import math
from types import MappingProxyType
from uuid import UUID
from psycopg.types.json import Jsonb

from aos_api.asset_registry.contracts import BundleArtifact, BundleKind, BundleManifest, MAX_ARTIFACT_SIZE
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload, StoredCompositionLock, InstallationRecord,
    InstallationRevision, InstallationDecision, InstallationEvent, InstallationEventEvidence, CreateInstallationRequest,
)
from aos_api.asset_registry.composition_store import _snapshot_from_json
from aos_api.asset_registry.control_policy import REINSTALL_INSTALLATION_OPERATION, require_control_role, validate_idempotency_key
from aos_api.asset_registry.dependency_graph import _to_resolved_bundle
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.installation_service import _require_lock_markings
from aos_api.asset_registry.installation_store import LockedInstallation, _event_json
from aos_api.asset_registry.legacy_runtime_boundary import legacy_content_predicate
from aos_api.asset_registry import installation_evidence
from aos_api.asset_registry.release_policy import verify_content_descriptor
from aos_api.asset_registry.registry_service import _parse_artifacts
from aos_api.asset_registry.reinstall_contracts import ReinstallSourceRef
from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.lifecycle_store import _digest, _require_transaction, _request_hash, _values
from aos_api.extension_runtime.registration import registration_fingerprint
from aos_api.extension_runtime import ui_current_principal
from aos_api.extension_runtime.lifecycle import _PATHS
from aos_api.extension_runtime.generation_attempts import _TERMINAL, _TERMINAL_REASONS, _ERROR_TYPE, _HASH
from aos_api.extension_runtime.configuration_contracts import ConfigurationRef, ConfigureTarget
from aos_api.extension_runtime.disable_contracts import DisableTarget
from aos_api.extension_runtime import configuration_store
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_cutover import (
    CutoverPrepareRequest, CutoverCommitRequest, CutoverFinalizeRequest, CutoverApprovalRefreshRequest,
    CutoverRollbackRequest, CutoverExactRef,
    EcommerceGrowthCutoverStore, EcommerceGrowthCutoverError,
)
from aos_api.ecommerce_growth_lifecycle import (
    EcommerceGrowthDisableDependent, EcommerceGrowthLifecycleError, _snapshot as _growth_snapshot,
)
from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
from aos_api.ecommerce_dispatch_configuration_receipt import decode_receipt as _decode_dispatch_refresh_receipt
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_origin import verify_registration_origin
from aos_api.ecommerce_growth_withdrawal_receipt import decode_withdrawal_receipt
from aos_api.ecommerce_growth_runtime_store import (
    _strict_exact_ref as _command_exact_ref, _strict_response as _command_response,
    _OPERATIONS as _COMMAND_OPERATIONS,
)
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest, decode_successor_receipt
from aos_api.asset_registry.reinstall_origin_store import PostgresReinstallOriginAppender
from aos_api.tenant_scope import TenantScope


_SCHEMA_VERSION = "aos.reinstall-terminal-source-facts/v13"
_MAX_PACKET_BYTES = 8 * 1024 * 1024
_MAX_JSON_BYTES = 1024 * 1024
_MAX_PACKET_ROWS = 8192
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 200000
_MAX_ROW_VISITS = 32768
_MAX_WORK_BYTES = 32 * 1024 * 1024
_MAX_WORK_NODES = 800000


@dataclass(frozen=True, slots=True)
class _Relation:
    columns: tuple[tuple[str, str], ...]
    key: tuple[str, ...]
    cap: int


_RELATIONS = MappingProxyType({
    'public.bundle_installation': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_pk', 'uuid!'), ('installation_id', 'uuid!'), ('current_revision', 'bigint!'), ('active_revision', 'bigint?'), ('previous_active_revision', 'bigint?'), ('etag_version', 'bigint!')), ('org_id', 'project_id', 'installation_pk'), 1),
    'public.extension_runtime_binding': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('installation_revision', 'bigint!'), ('package_lock_ref', 'jsonb!'), ('profile_ref', 'text!'), ('config_ref', 'jsonb?'), ('execution_epoch', 'bigint!'), ('desired_state', 'text!'), ('observed_state', 'text!'), ('enabled', 'boolean!'), ('operation_fence', 'boolean!'), ('resource_handle_ref', 'jsonb?'), ('revision', 'bigint!')), ('org_id', 'project_id', 'installation_id', 'generation'), 1),
    'public.extension_operation_dispatch_binding': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('operation_id', 'text!'), ('handler_kind', 'text!'), ('installation_id', 'uuid?'), ('generation', 'uuid?'), ('execution_epoch', 'bigint?'), ('operation_fence', 'boolean!'), ('revision', 'bigint!'), ('cutover_group_id', 'uuid!'), ('cutover_group_revision', 'bigint!'), ('updated_by', 'text!'), ('updated_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'operation_id'), 2048),
    'public.extension_runtime_operation': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('operation_id', 'uuid!'), ('installation_id', 'uuid!'), ('kind', 'text!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('requested_by', 'text!'), ('approved_by', 'text?'), ('approval_ref', 'jsonb?'), ('expected_installation_etag', 'bigint!'), ('expected_binding_revision', 'bigint?'), ('status', 'text!'), ('phase', 'text!'), ('revision', 'bigint!'), ('deadline', 'timestamp with time zone!'), ('failure_code', 'text?'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'operation_id'), 2048),
    'public.extension_dispatch_cutover_operation': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('cutover_operation_id', 'uuid!'), ('kind', 'text!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('status', 'text!'), ('cutover_group_id', 'uuid!'), ('expected_group_revision', 'bigint!'), ('target_group_revision', 'bigint!'), ('target_installation_id', 'uuid!'), ('target_generation', 'uuid!'), ('target_execution_epoch', 'bigint!'), ('target_runtime_revision', 'bigint!'), ('operation_ids', 'jsonb!'), ('old_dispatch_snapshot', 'jsonb!'), ('new_dispatch_snapshot', 'jsonb!'), ('checkpoint', 'jsonb!'), ('occurrence_watermark', 'timestamp with time zone?'), ('pending_target_receipt_refs', 'jsonb!'), ('policy_ref', 'jsonb!'), ('approval_ref', 'jsonb!'), ('requested_by', 'text!'), ('created_at', 'timestamp with time zone!'), ('updated_at', 'timestamp with time zone!'), ('parent_cutover_operation_id', 'uuid?'), ('parent_receipt_ref', 'jsonb?'), ('failure_reason', 'text?')), ('org_id', 'project_id', 'cutover_operation_id'), 2048),
    'public.extension_dispatch_lifecycle_operation': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('runtime_operation_id', 'uuid!'), ('activation_operation_id', 'uuid!'), ('cutover_group_id', 'uuid!'), ('status', 'text!'), ('request_hash', 'text!'), ('operation_ids', 'jsonb!'), ('extension_snapshot', 'jsonb!'), ('fenced_snapshot', 'jsonb!'), ('legacy_snapshot', 'jsonb!'), ('fenced_group_revision', 'bigint!'), ('requested_by', 'text!'), ('created_at', 'timestamp with time zone!'), ('updated_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'runtime_operation_id'), 2048),
    'public.extension_runtime_dependency_ref': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('consumer_installation', 'uuid!'), ('consumer_generation', 'uuid!'), ('provider_installation', 'uuid!'), ('provider_generation', 'uuid!'), ('kind', 'text!'), ('active', 'boolean!'), ('revision', 'bigint!')), ('org_id', 'project_id', 'consumer_installation', 'consumer_generation', 'provider_installation', 'provider_generation', 'kind'), 2048),
    'public.extension_runtime_resource_lease': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('resource_id', 'uuid!'), ('operation_id', 'uuid!'), ('generation', 'uuid!'), ('package_id', 'text!'), ('package_hash', 'text!'), ('engine_context', 'text!'), ('resource_name', 'text!'), ('container_id', 'text?'), ('create_claimed_at', 'timestamp with time zone?'), ('cleanup_state', 'text!'), ('expires_at', 'timestamp with time zone!'), ('observed_release', 'boolean!')), ('org_id', 'project_id', 'resource_id'), 2048),
    'public.extension_runtime_execution_attempt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('attempt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('operation_kind', 'text!'), ('operation_key', 'text!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('state', 'text!'), ('lease_until', 'timestamp with time zone!'), ('revision', 'bigint!'), ('accepted_at', 'timestamp with time zone!'), ('heartbeat_at', 'timestamp with time zone?'), ('completed_at', 'timestamp with time zone?'), ('terminal_reason_code', 'text?'), ('terminal_error_type', 'text?')), ('org_id', 'project_id', 'attempt_id'), 2048),
    'public.automation_schedule_binding': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('policy_id', 'text!'), ('policy_revision', 'bigint!'), ('policy_hash', 'text!'), ('operation_id', 'text!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('timezone', 'text!'), ('cadence', 'text!'), ('weekly_day', 'smallint?'), ('local_time', 'time without time zone?'), ('effective_from', 'timestamp with time zone!'), ('effective_until', 'timestamp with time zone?'), ('approved', 'boolean!'), ('enabled', 'boolean!'), ('watermark', 'timestamp with time zone?'), ('revision', 'bigint!')), ('org_id', 'project_id', 'policy_id', 'policy_revision'), 2048),
    'public.automation_occurrence': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('occurrence_id', 'uuid!'), ('policy_id', 'text!'), ('policy_revision', 'bigint!'), ('policy_hash', 'text!'), ('operation_id', 'text!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('scheduled_at', 'timestamp with time zone?'), ('local_slot', 'text?'), ('trigger_source', 'text!'), ('source_event_id', 'text?'), ('status', 'text!'), ('deadline', 'timestamp with time zone!'), ('claim_owner', 'text?'), ('claim_until', 'timestamp with time zone?'), ('receipt_ref', 'jsonb?'), ('created_at', 'timestamp with time zone!'), ('updated_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'occurrence_id'), 2048),
    'public.automation_occurrence_dispatch_attempt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('attempt_id', 'uuid!'), ('occurrence_id', 'uuid!'), ('claim_owner', 'text!'), ('target_idempotency_key', 'text!'), ('status', 'text!'), ('claimed_at', 'timestamp with time zone!'), ('claim_until', 'timestamp with time zone!'), ('receipt_ref', 'jsonb?'), ('resolved_at', 'timestamp with time zone?')), ('org_id', 'project_id', 'attempt_id'), 2048),
    'public.automation_occurrence_outbox': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('event_id', 'uuid!'), ('occurrence_id', 'uuid!'), ('payload', 'jsonb!'), ('payload_hash', 'text!'), ('attempt', 'integer!'), ('next_attempt', 'timestamp with time zone!'), ('claim_until', 'timestamp with time zone?'), ('delivered_at', 'timestamp with time zone?')), ('org_id', 'project_id', 'event_id'), 2048),
    'public.extension_runtime_event': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('operation_id', 'uuid!'), ('sequence', 'bigint!'), ('event_id', 'uuid!'), ('type', 'text!'), ('payload', 'jsonb!'), ('payload_hash', 'text!'), ('occurred_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'operation_id', 'sequence'), 4096),
    'public.extension_runtime_outbox': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('event_id', 'uuid!'), ('consumer_id', 'text!'), ('attempt', 'integer!'), ('next_attempt', 'timestamp with time zone!'), ('claim_until', 'timestamp with time zone?'), ('delivered_at', 'timestamp with time zone?')), ('org_id', 'project_id', 'event_id', 'consumer_id'), 2048),
    'public.extension_dispatch_claim_gate': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('cutover_group_id', 'uuid!'), ('cutover_operation_id', 'uuid!'), ('claim_paused', 'boolean!'), ('revision', 'bigint!'), ('updated_by', 'text!'), ('updated_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'cutover_group_id'), 2048),
    'public.bundle_composition': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('composition_pk', 'uuid!'), ('composition_id', 'uuid!'), ('registry_snapshot_json', 'jsonb!'), ('registry_snapshot_hash', 'text!')), ('org_id', 'project_id', 'composition_pk'), 1),
    'public.bundle_composition_lock': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('composition_pk', 'uuid!'), ('revision', 'bigint!'), ('lock_payload', 'jsonb!'), ('lock_hash', 'text!'), ('permission_diff_json', 'jsonb!'), ('permission_diff_hash', 'text!'), ('migration_plan_json', 'jsonb!'), ('migration_plan_hash', 'text!'), ('contribution_diff_json', 'jsonb!'), ('contribution_diff_hash', 'text!')), ('org_id', 'project_id', 'composition_pk', 'revision'), 1),
    'public.bundle_installation_revision': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_pk', 'uuid!'), ('revision', 'bigint!'), ('parent_revision', 'bigint?'), ('state', 'text!'), ('composition_pk', 'uuid!'), ('lock_revision', 'bigint!'), ('lock_hash', 'text!'), ('permission_diff_hash', 'text!'), ('migration_plan_hash', 'text!'), ('contribution_diff_hash', 'text!'), ('overlay_revision', 'text!'), ('decision_id', 'uuid?')), ('org_id', 'project_id', 'installation_pk', 'revision'), 2048),
    'public.bundle_installation_event': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_pk', 'uuid!'), ('sequence', 'bigint!'), ('from_revision', 'bigint?'), ('to_revision', 'bigint!'), ('from_state', 'text?'), ('to_state', 'text!'), ('actor', 'text!'), ('evidence_json', 'jsonb?'), ('evidence_hash', 'text?')), ('org_id', 'project_id', 'installation_pk', 'sequence'), 2048),
    'public.extension_runtime_configuration': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('configuration_id', 'uuid!'), ('revision', 'bigint!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('previous_hash', 'text?'), ('request_hash', 'text!'), ('idempotency_key', 'text!'), ('actor', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'installation_id', 'generation', 'configuration_id', 'revision'), 2048),
    'public.extension_runtime_execution_attempt_event': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('attempt_id', 'uuid!'), ('sequence', 'bigint!'), ('event_id', 'uuid!'), ('type', 'text!'), ('state', 'text!'), ('revision', 'bigint!'), ('occurred_at', 'timestamp with time zone!'), ('terminal_reason_code', 'text?'), ('terminal_error_type', 'text?')), ('org_id', 'project_id', 'attempt_id', 'sequence'), 2048),
    'public.extension_dispatch_cutover_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('cutover_operation_id', 'uuid!'), ('phase', 'text!'), ('request_hash', 'text!'), ('authority_data', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.extension_dispatch_lifecycle_event': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('runtime_operation_id', 'uuid!'), ('sequence', 'bigint!'), ('event_type', 'text!'), ('payload', 'jsonb!'), ('payload_hash', 'text!'), ('occurred_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'runtime_operation_id', 'sequence'), 2048),
    'public.extension_dispatch_lifecycle_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('runtime_operation_id', 'uuid!'), ('phase', 'text!'), ('request_hash', 'text!'), ('authority_data', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.extension_dispatch_configuration_refresh_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('cutover_group_id', 'uuid!'), ('receipt_id', 'uuid!'), ('revision', 'bigint!'), ('activation_operation_id', 'uuid!'), ('activation_resume_receipt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('previous_receipt_id', 'uuid?'), ('previous_hash', 'text?'), ('actor', 'text!'), ('idempotency_key', 'text!'), ('request', 'jsonb!'), ('request_hash', 'text!'), ('body', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'cutover_group_id', 'activation_operation_id', 'revision'), 128),
    'public.extension_dispatch_successor_registration_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('group_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.extension_runtime_uninstall_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('disable_operation_id', 'uuid?'), ('activation_operation_id', 'uuid?'), ('installation_revision', 'bigint!'), ('binding_revision', 'bigint!'), ('actor', 'text!'), ('authority_data_text', 'text!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!'), ('retirement_kind', 'text!'), ('unactivated_disable_operation_id', 'uuid?'), ('runtime_enable_operation_id', 'uuid?'), ('runtime_disable_operation_id', 'uuid?')), ('org_id', 'project_id', 'receipt_id'), 1),
    'public.extension_event_control_dispatch_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('idempotency_key', 'text!'), ('phase', 'text!'), ('request_hash', 'text!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('runtime_revision', 'bigint!'), ('cutover_group_id', 'uuid!'), ('expected_group_revision', 'bigint!'), ('target_group_revision', 'bigint!'), ('case_id', 'text!'), ('policy_id', 'text!'), ('approval_ref', 'jsonb!'), ('before_snapshot', 'jsonb!'), ('after_snapshot', 'jsonb!'), ('actor', 'text!'), ('authority_data', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.extension_dispatch_cutover_event': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('cutover_operation_id', 'uuid!'), ('sequence', 'bigint!'), ('event_id', 'uuid!'), ('event_type', 'text!'), ('payload', 'jsonb!'), ('payload_hash', 'text!'), ('occurred_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'cutover_operation_id', 'sequence'), 2048),
    'public.extension_dispatch_cutover_approval_refresh_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('cutover_operation_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('prepare_receipt_ref', 'jsonb!'), ('old_approval_ref', 'jsonb!'), ('new_approval_ref', 'jsonb!'), ('authority_data', 'jsonb!'), ('content_hash', 'text!'), ('refreshed_by', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.extension_dispatch_registration_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('group_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.extension_dispatch_withdrawal_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('registration_receipt_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
    'public.ecommerce_growth_runtime_command_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('operation_id', 'text!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('dispatch_revision', 'bigint!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('cutover_group_id', 'uuid!'), ('cutover_group_revision', 'bigint!'), ('runtime_revision', 'bigint!'), ('response', 'jsonb!'), ('target_receipt_ref', 'jsonb!'), ('actor', 'text!'), ('occurred_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'operation_id', 'idempotency_key'), 2048),
})

# Native-table closure for distinct old installations; current source caps remain unchanged.
_PREDECESSOR_RELATIONS = MappingProxyType({
    **{name: (_Relation(_RELATIONS[name].columns, _RELATIONS[name].key, 2048)
           if name == "public.extension_runtime_binding" else _RELATIONS[name])
    for name in (
        'public.extension_runtime_binding',
        'public.extension_runtime_operation',
        'public.extension_runtime_event',
        'public.extension_runtime_outbox',
        'public.extension_runtime_configuration',
        'public.extension_runtime_dependency_ref',
        'public.extension_runtime_resource_lease',
        'public.extension_runtime_execution_attempt',
        'public.extension_runtime_execution_attempt_event',
        'public.extension_operation_dispatch_binding',
        'public.extension_dispatch_claim_gate',
        'public.extension_dispatch_cutover_operation',
        'public.extension_dispatch_cutover_receipt',
        'public.extension_dispatch_cutover_event',
        'public.extension_dispatch_cutover_approval_refresh_receipt',
        'public.extension_dispatch_configuration_refresh_receipt',
        'public.extension_dispatch_lifecycle_operation',
        'public.extension_dispatch_lifecycle_receipt',
        'public.extension_dispatch_lifecycle_event',
        'public.automation_occurrence',
        'public.automation_occurrence_dispatch_attempt',
    )},
    **{
        'public.bundle_installation': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_pk', 'uuid!'), ('installation_id', 'uuid!'), ('current_revision', 'bigint!'), ('active_revision', 'bigint?'), ('previous_active_revision', 'bigint?'), ('etag_version', 'bigint!'), ('display_name', 'text!'), ('created_at', 'timestamp with time zone!'), ('updated_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'installation_pk'), 2048),
        'public.bundle_installation_revision': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_pk', 'uuid!'), ('revision', 'bigint!'), ('parent_revision', 'bigint?'), ('state', 'text!'), ('composition_pk', 'uuid!'), ('lock_revision', 'bigint!'), ('lock_hash', 'text!'), ('permission_diff_hash', 'text!'), ('migration_plan_hash', 'text!'), ('contribution_diff_hash', 'text!'), ('overlay_revision', 'text!'), ('decision_id', 'uuid?'), ('requested_by', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'installation_pk', 'revision'), 2048),
        'public.bundle_installation_event': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('installation_pk', 'uuid!'), ('sequence', 'bigint!'), ('from_revision', 'bigint?'), ('to_revision', 'bigint!'), ('from_state', 'text?'), ('to_state', 'text!'), ('actor', 'text!'), ('evidence_json', 'jsonb?'), ('evidence_hash', 'text?'), ('reason', 'text?'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'installation_pk', 'sequence'), 2048),
        'public.bundle_composition': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('composition_pk', 'uuid!'), ('composition_id', 'uuid!'), ('registry_snapshot_json', 'jsonb!'), ('registry_snapshot_hash', 'text!')), ('org_id', 'project_id', 'composition_pk'), 2048),
        'public.bundle_composition_lock': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('composition_pk', 'uuid!'), ('revision', 'bigint!'), ('lock_payload', 'jsonb!'), ('lock_hash', 'text!'), ('permission_diff_json', 'jsonb!'), ('permission_diff_hash', 'text!'), ('migration_plan_json', 'jsonb!'), ('migration_plan_hash', 'text!'), ('contribution_diff_json', 'jsonb!'), ('contribution_diff_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'composition_pk', 'revision'), 2048),
        'public.bundle_installation_decision': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('decision_id', 'uuid!'), ('installation_pk', 'uuid!'), ('submitted_revision', 'bigint!'), ('decision', 'text!'), ('actor', 'text!'), ('lock_hash', 'text!'), ('permission_diff_hash', 'text!'), ('migration_plan_hash', 'text!'), ('contribution_diff_hash', 'text!'), ('reason', 'text?'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'decision_id'), 2048),
        'public.extension_dispatch_registration_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('group_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
        'public.extension_dispatch_successor_registration_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('group_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
        'public.extension_dispatch_withdrawal_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('receipt_id', 'uuid!'), ('registration_receipt_id', 'uuid!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('payload', 'jsonb!'), ('content_hash', 'text!'), ('created_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'receipt_id'), 2048),
        'public.automation_schedule_binding': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('policy_id', 'text!'), ('policy_revision', 'bigint!'), ('policy_hash', 'text!'), ('operation_id', 'text!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('timezone', 'text!'), ('cadence', 'text!'), ('weekly_day', 'smallint?'), ('local_time', 'time without time zone?'), ('effective_from', 'timestamp with time zone!'), ('effective_until', 'timestamp with time zone?'), ('approved', 'boolean!'), ('enabled', 'boolean!'), ('watermark', 'timestamp with time zone?'), ('revision', 'bigint!')), ('org_id', 'project_id', 'policy_id', 'policy_revision'), 2048),
        'public.ecommerce_growth_runtime_command_receipt': _Relation((('org_id', 'text!'), ('project_id', 'text!'), ('operation_id', 'text!'), ('idempotency_key', 'text!'), ('request_hash', 'text!'), ('dispatch_revision', 'bigint!'), ('installation_id', 'uuid!'), ('generation', 'uuid!'), ('execution_epoch', 'bigint!'), ('cutover_group_id', 'uuid!'), ('cutover_group_revision', 'bigint!'), ('runtime_revision', 'bigint!'), ('response', 'jsonb!'), ('target_receipt_ref', 'jsonb!'), ('actor', 'text!'), ('occurred_at', 'timestamp with time zone!')), ('org_id', 'project_id', 'operation_id', 'idempotency_key'), 2048),
    },
})

_REGISTRY = MappingProxyType({
    'public.asset_bundle': _Relation((('bundle_pk', 'uuid!'), ('publisher', 'text!'), ('bundle_id', 'text!'), ('kind', 'text!')), ('bundle_pk',), 512),
    'public.asset_bundle_version': _Relation((('version_pk', 'uuid!'), ('bundle_pk', 'uuid!'), ('version', 'text!'), ('manifest_json', 'jsonb!'), ('content_hash', 'text!')), ('version_pk',), 512),
    'public.asset_bundle_artifact': _Relation((('version_pk', 'uuid!'), ('relative_path', 'text!'), ('digest', 'text!'), ('size', 'bigint!'), ('media_type', 'text!')), ('version_pk', 'relative_path'), 2048),
})



class _WorkLedger:
    """One private ledger is retained across all checks of a single root."""
    __slots__ = ("row_visits", "work_bytes", "node_visits")

    def __init__(self):
        self.row_visits = 0
        self.work_bytes = 0
        self.node_visits = 0

    def _charge(self, *, rows=0, byte_count=0, node_count=0):
        if any(type(n) is not int or n < 0 for n in (rows, byte_count, node_count)):
            raise ValueError("invalid terminal facts work accounting")
        proposed = (self.row_visits + rows, self.work_bytes + byte_count, self.node_visits + node_count)
        if any(n > limit for n, limit in zip(proposed, (_MAX_ROW_VISITS, _MAX_WORK_BYTES, _MAX_WORK_NODES))):
            raise ValueError("terminal facts budget exceeded")
        self.row_visits, self.work_bytes, self.node_visits = proposed


def _invalid():
    raise ValueError("invalid terminal facts")


def _string_size(value, limit):
    # Fixed-size chunks avoid materializing the complete escaped UTF8 value.
    if len(value) > limit or "\x00" in value:
        _invalid()
    size = 2
    try:
        for index in range(0, len(value), 4096):
            piece = json.dumps(value[index:index + 4096], ensure_ascii=False)
            size += len(piece.encode("utf-8")) - 2
            if size > limit:
                raise ValueError("terminal facts budget exceeded")
    except UnicodeError:
        raise ValueError("invalid terminal facts") from None
    return size


def _measure_json(value, ledger, limit):
    if type(ledger) is not _WorkLedger:
        _invalid()
    size = 0
    nodes = 0
    active = set()
    stack = [(value, 0, False)]

    def add_bytes(count):
        nonlocal size
        if size + count > limit:
            raise ValueError("terminal facts budget exceeded")
        ledger._charge(byte_count=count)
        size += count

    def add_node():
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_JSON_NODES:
            raise ValueError("terminal facts budget exceeded")
        ledger._charge(node_count=1)

    while stack:
        item, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(item))
            continue
        if depth > _MAX_JSON_DEPTH:
            raise ValueError("terminal facts budget exceeded")
        add_node()
        kind = type(item)
        if kind is str:
            add_bytes(_string_size(item, limit))
        elif item is None:
            add_bytes(4)
        elif kind is bool:
            add_bytes(4 if item else 5)
        elif kind in (int, float):
            if kind is float and not math.isfinite(item):
                _invalid()
            try:
                add_bytes(len(json.dumps(item, allow_nan=False)))
            except (ValueError, OverflowError):
                raise ValueError("invalid terminal facts") from None
        elif kind in (dict, list):
            if id(item) in active:
                _invalid()
            if len(item) > _MAX_JSON_NODES:
                raise ValueError("terminal facts budget exceeded")
            active.add(id(item))
            stack.append((item, depth, True))
            add_bytes(2 + max(0, len(item) - 1) + (len(item) if kind is dict else 0))
            if kind is dict:
                for key, child in reversed(list(item.items())):
                    if type(key) is not str:
                        _invalid()
                    add_node()
                    add_bytes(_string_size(key, limit))
                    stack.append((child, depth + 1, False))
            else:
                stack.extend((child, depth + 1, False) for child in reversed(item))
        else:
            _invalid()
    return size, nodes


def _scalar(value, descriptor, ledger):
    if type(ledger) is not _WorkLedger:
        _invalid()
    ledger._charge(node_count=1)
    nullable = descriptor.endswith("?")
    kind = descriptor[:-1]
    if value is None:
        if nullable:
            return None
        _invalid()
    if kind == "jsonb":
        byte_count, node_count = _measure_json(value, ledger, _MAX_JSON_BYTES)
        # The owned copy is another bounded visit; charge before allocating it.
        ledger._charge(byte_count=byte_count, node_count=node_count)
        return deepcopy(value)
    if kind in ("smallint", "integer", "bigint"):
        bits = {"smallint": 16, "integer": 32, "bigint": 64}[kind]
        if type(value) is not int or not -(2 ** (bits - 1)) <= value < 2 ** (bits - 1):
            _invalid()
        return value
    if kind == "boolean":
        if type(value) is not bool:
            _invalid()
        return value
    if type(value) is not str:
        _invalid()
    try:
        if "\x00" in value:
            _invalid()
        byte_count = len(value.encode("utf-8"))
    except (ValueError, UnicodeError):
        raise ValueError("invalid terminal facts") from None
    ledger._charge(byte_count=byte_count)
    try:
        if kind == "uuid":
            parsed = UUID(value)
            if str(parsed) != value:
                _invalid()
            return parsed
        if kind == "timestamp with time zone":
            parsed = datetime.fromisoformat(value)
            if parsed.utcoffset() is None:
                _invalid()
            return parsed
        if kind == "time without time zone":
            parsed = time.fromisoformat(value)
            if parsed.utcoffset() is not None:
                _invalid()
            return parsed
        if kind == "text":
            return value
    except (ValueError, TypeError, OverflowError, UnicodeError):
        raise ValueError("invalid terminal facts") from None
    _invalid()


def _exact_fields(value, fields, ledger):
    if type(value) is not dict or not all(type(key) is str for key in value) or set(value) != set(fields):
        _invalid()
    ledger._charge(node_count=1 + len(value))


@dataclass(frozen=True, slots=True)
class _DecodedFacts:
    relations: object
    registry: object
    predecessors: object


def _decode_packet(packet, ledger):
    """Decode all fixed families. This is neither a principal check nor a Port."""
    if type(ledger) is not _WorkLedger:
        _invalid()
    _exact_fields(packet, ("schema", "relations", "registry", "predecessors"), ledger)
    if type(packet["schema"]) is not str or packet["schema"] != _SCHEMA_VERSION:
        _invalid()
    total_rows = 0
    for group, schemas in (("relations", _RELATIONS), ("registry", _REGISTRY), ("predecessors", _PREDECESSOR_RELATIONS)):
        _exact_fields(packet[group], schemas, ledger)
        for name, schema in schemas.items():
            rows = packet[group][name]
            if type(rows) is not list or len(rows) > schema.cap:
                _invalid()
            total_rows += len(rows)
    if total_rows > _MAX_PACKET_ROWS:
        raise ValueError("terminal facts budget exceeded")
    _measure_json(packet, ledger, _MAX_PACKET_BYTES)
    decoded = {}
    for group, schemas in (("relations", _RELATIONS), ("registry", _REGISTRY), ("predecessors", _PREDECESSOR_RELATIONS)):
        families = {}
        for name, schema in schemas.items():
            rows = []
            seen = set()
            for raw in packet[group][name]:
                ledger._charge(rows=1)
                _exact_fields(raw, (column for column, _ in schema.columns), ledger)
                row = {column: _scalar(raw[column], descriptor, ledger) for column, descriptor in schema.columns}
                if name == "public.asset_bundle":
                    try:
                        row["kind"] = BundleKind(row["kind"])
                    except ValueError:
                        raise ValueError("invalid terminal facts") from None
                if name == "public.asset_bundle_version" and type(row["manifest_json"]) is not dict:
                    _invalid()
                if name == "public.asset_bundle_artifact" and not 0 <= row["size"] <= MAX_ARTIFACT_SIZE:
                    _invalid()
                if name == "public.extension_runtime_uninstall_receipt":
                    raw_bytes = len(row["authority_data_text"].encode("utf-8"))
                    ledger._charge(byte_count=raw_bytes, node_count=1)
                    if raw_bytes > _MAX_JSON_BYTES:
                        raise ValueError("terminal facts budget exceeded")
                ledger._charge(node_count=len(schema.key))
                key = tuple(row[column] for column in schema.key)
                if key in seen:
                    _invalid()
                seen.add(key)
                rows.append(MappingProxyType(row))
            families[name] = tuple(rows)
        decoded[group] = MappingProxyType(families)
    return _DecodedFacts(decoded["relations"], decoded["registry"], decoded["predecessors"])


def _model_work(value, ledger, passes):
    """Reserve repeated serialized-input work, not measured Pydantic CPU/RSS."""
    size, nodes = _measure_json(value, ledger, _MAX_JSON_BYTES)
    ledger._charge(byte_count=size * (passes - 1), node_count=nodes * (passes - 1))


def _one(rows):
    if len(rows) != 1:
        _invalid()
    return rows[0]


def _checked_lock(lock, ledger):
    if type(lock) is not StoredCompositionLock or type(ledger) is not _WorkLedger:
        _invalid()
    # Reconstruct the canonical objects; model_copy must not bypass validation.
    lock_json = lock.model_dump(mode="json", by_alias=True, exclude_none=False, warnings="error")
    _model_work(lock_json, ledger, 16)
    return StoredCompositionLock.model_validate_json(json.dumps(lock_json, ensure_ascii=False, allow_nan=False))


def _principal_values(values, *, allow_empty):
    if (type(values) is not tuple or len(values) > 500 or (not values and not allow_empty)
            or any(type(value) is not str or not value or value != value.strip() or not value.isprintable()
                   for value in values) or len(set(values)) != len(values)):
        _invalid()


def _read_current_permissions(conn, *, scope, actor, source_lock, target_lock, ledger):
    """Read each lock's current caller facts on the caller-owned transaction."""
    _require_transaction(conn)
    if (type(scope) is not TenantScope or type(ledger) is not _WorkLedger or type(actor) is not str
            or not actor or actor != actor.strip() or not actor.isprintable()):
        _invalid()
    scope = TenantScope(scope.org_id, scope.project_id)
    locks = (_checked_lock(source_lock, ledger), _checked_lock(target_lock, ledger))
    principals = []
    for lock in locks:
        required = tuple(lock.payload.permission_diff.target.markings)
        _principal_values(required, allow_empty=True)
        # Reserve expected metadata/validation work before executing the original
        # reader. SQL scan cost and actual lock retention require native evidence.
        ledger._charge(rows=2 + len(required))
        _model_work({"subject": actor, "scope": list(scope.key), "required": list(required)}, ledger, 4)
        principal = ui_current_principal.read_current_ui_principal(
            conn=conn, scope=scope, subject=actor, required_markings=required)
        if (type(principal) is not ui_current_principal.CurrentUiPrincipal
                or type(principal.scope) is not TenantScope or principal.scope.key != scope.key
                or type(principal.subject) is not str or principal.subject != actor):
            _invalid()
        _principal_values(principal.roles, allow_empty=False)
        _principal_values(principal.markings, allow_empty=True)
        _model_work({"roles": list(principal.roles), "markings": list(principal.markings)}, ledger, 4)
        require_control_role(roles=principal.roles, operation=REINSTALL_INSTALLATION_OPERATION)
        _require_lock_markings(lock, markings=principal.markings, conceal=False)
        principals.append(principal)
    return tuple(principals)


def _verify_source_history(facts, *, scope, source, locked_source, source_lock, ledger):
    """Bind complete projected history to original locked record facts, not authority."""
    if (type(facts) is not _DecodedFacts or type(scope) is not TenantScope
            or type(source) is not ReinstallSourceRef or type(locked_source) is not LockedInstallation
            or type(locked_source.installation_pk) is not UUID or type(ledger) is not _WorkLedger
            or type(locked_source.record) is not InstallationRecord
            or type(source.terminal_revision) is not int):
        _invalid()
    scope = TenantScope(scope.org_id, scope.project_id)
    record = locked_source.record
    if (type(record.events) is not list or not 0 < len(record.events) <= 2048
            or type(record.current) is not InstallationRevision
            or type(record.decision) is not InstallationDecision
            or any(type(event) is not InstallationEvent or
                   (event.evidence is not None and type(event.evidence) is not InstallationEventEvidence)
                   for event in record.events)):
        _invalid()
    numbers = [(record.current_revision, False), (record.etag_version, False),
               (record.active_revision, True), (record.previous_active_revision, True),
               (record.current.revision, False), (record.current.parent_revision, True),
               (record.current.lock_revision, False), (record.decision.submitted_revision, False)]
    for event in record.events:
        ledger._charge(node_count=3)
        numbers.extend(((event.sequence, False), (event.from_revision, True), (event.to_revision, False)))
    for value, nullable in numbers:
        ledger._charge(node_count=1)
        if value is None and nullable:
            continue
        if type(value) is not int or not 1 <= value <= 9223372036854775807:
            _invalid()
    payload = source.model_dump(mode="json", by_alias=True, warnings="error")
    _model_work(payload, ledger, 4)
    source = ReinstallSourceRef.model_validate_json(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    payload = record.model_dump(mode="json", by_alias=True, exclude_none=False, warnings="error")
    _model_work(payload, ledger, 16)
    record = InstallationRecord.model_validate_json(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    checked = _checked_lock(source_lock, ledger)
    if ((locked_source.org_id, locked_source.project_id) != scope.key
            or record.state != "uninstalled" or record.installation_id != source.installation_id
            or record.current_revision != source.terminal_revision or record.etag_version != source.terminal_revision
            or record.current.lock_hash != source.lock_hash or source.lock_hash != checked.lock_hash
            or record.current.composition_id != checked.composition_id
            or record.current.lock_revision != checked.revision):
        _invalid()
    _verify_installation_history_rows(record, locked_source.installation_pk, facts.relations,
        scope=scope, checked=checked, ledger=ledger, projected_context=False)
    tail = record.events[-1]
    if tail.evidence is None or tail.evidence.type != "uninstall" or record.current.created_at != tail.created_at:
        _invalid()
    return record


def _verify_installation_history_rows(record, installation_pk, relations, *, scope, checked, ledger, projected_context):
    """Share original history/evidence checks without requiring a terminal state."""
    if (type(record) is not InstallationRecord or type(installation_pk) is not UUID
            or type(scope) is not TenantScope or type(checked) is not StoredCompositionLock
            or type(ledger) is not _WorkLedger or type(projected_context) is not bool):
        _invalid()
    hashes = ("lock_hash", "permission_diff_hash", "migration_plan_hash", "contribution_diff_hash")
    if any(getattr(record.current, name) != getattr(checked, name) for name in hashes):
        _invalid()
    groups = {}
    for name in ("public.bundle_installation", "public.bundle_installation_revision", "public.bundle_installation_event"):
        rows = relations[name]
        for row in rows:
            ledger._charge(rows=1, node_count=3)
            if (row["org_id"], row["project_id"]) != scope.key or row["installation_pk"] != installation_pk:
                _invalid()
        groups[name] = rows
    head = _one(groups["public.bundle_installation"])
    if (str(head["installation_id"]) != record.installation_id
            or any(head[name] != getattr(record, name) for name in
                   ("current_revision", "etag_version", "active_revision", "previous_active_revision"))):
        _invalid()
    composition = _one(relations["public.bundle_composition"])
    if ((composition["org_id"], composition["project_id"]) != scope.key
            or str(composition["composition_id"]) != checked.composition_id):
        _invalid()
    revisions = groups["public.bundle_installation_revision"]
    events = groups["public.bundle_installation_event"]
    if len(revisions) != record.current_revision or len(events) != record.current_revision:
        _invalid()
    revision_index = {row["revision"]: row for row in revisions}
    event_index = {row["sequence"]: row for row in events}
    if len(revision_index) != len(revisions) or len(event_index) != len(events):
        _invalid()
    for event in record.events:
        ledger._charge(rows=2, node_count=14)
        row = revision_index.get(event.to_revision)
        raw = event_index.get(event.sequence)
        if row is None or raw is None:
            _invalid()
        decision_id = None if event.to_state in ("draft", "submitted") else record.decision.decision_id
        if (row["parent_revision"] != event.from_revision or row["state"] != event.to_state
                or row["composition_pk"] != composition["composition_pk"]
                or row["lock_revision"] != checked.revision
                or row["overlay_revision"] != record.current.overlay_revision
                or (None if row["decision_id"] is None else str(row["decision_id"])) != decision_id
                or any(row[name] != getattr(checked, name) for name in hashes)):
            _invalid()
        if raw["evidence_json"] is not None:
            _model_work(raw["evidence_json"], ledger, 8)
        # reason/created_at are original Store context, absent from the fixed
        # wire projection; this is not a second SQL observation of those fields.
        context = raw if projected_context else {**raw, "reason": event.reason, "created_at": event.created_at}
        projected = InstallationEvent.model_validate(_event_json(context))
        if projected_context:
            revision = _installation_revision_from_row(row, record.installation_id, checked.composition_id)
            if (revision.created_at != event.created_at
                    or revision.requested_by != record.current.requested_by
                    or revision.requested_by != record.events[0].actor
                    or (revision.revision == record.current_revision and revision != record.current)):
                _invalid()
        if projected != event:
            _invalid()
        required_kinds = {kind for kind, (_, to_state) in installation_evidence._TRANSITIONS.items()
                          if event.to_state == to_state and
                          event.from_state in installation_evidence._ALLOWED_FROM_STATES[kind]}
        if event.evidence is None:
            if required_kinds:
                _invalid()
        else:
            if event.evidence.type not in required_kinds or event.evidence.observed_at != event.created_at:
                _invalid()
            arguments = dict(installation_id=record.installation_id, from_revision=event.from_revision,
                to_revision=event.to_revision, from_state=event.from_state,
                **{name: getattr(checked, name) for name in hashes}, decision_id=record.decision.decision_id,
                observed_at=event.evidence.observed_at)
            installation_evidence.verify_event_evidence(event.evidence, **arguments)
            basis = installation_evidence.build_evidence_basis(evidence_type=event.evidence.type, **arguments)
            _model_work(basis, ledger, 4)
            if basis["toState"] != event.to_state:
                _invalid()
        if event.from_state == "submitted" and event.to_state == "approved":
            if (event.from_revision != record.decision.submitted_revision
                    or event.actor != record.decision.actor or event.created_at != record.decision.created_at):
                _invalid()
    for pointer in (record.active_revision, record.previous_active_revision):
        if pointer is not None and revision_index[pointer]["state"] != "active":
            _invalid()
    return record


def _installation_revision_from_row(row, installation_id, composition_id):
    return InstallationRevision.model_validate(dict(
        installationId=installation_id, revision=row["revision"], parentRevision=row["parent_revision"],
        state=row["state"], compositionId=composition_id, lockRevision=row["lock_revision"],
        lockHash=row["lock_hash"], permissionDiffHash=row["permission_diff_hash"],
        migrationPlanHash=row["migration_plan_hash"], contributionDiffHash=row["contribution_diff_hash"],
        overlayRevision=row["overlay_revision"], requestedBy=row["requested_by"],
        decisionId=None if row["decision_id"] is None else str(row["decision_id"]), createdAt=row["created_at"]))


def _predecessor_stored_lock(facts, *, scope, installation_id, ledger):
    """Rebuild the original typed lock using only actual old rows, including its clock."""
    if type(installation_id) is not UUID:
        _invalid()
    _check_predecessor_scope(facts, scope, ledger)
    p = facts.predecessors
    def select(family, predicate):
        rows = p[family]
        ledger._charge(rows=len(rows), node_count=len(rows) * 2)
        return tuple(row for row in rows if predicate(row))
    try:
        heads = select("public.bundle_installation", lambda row: row["installation_id"] == installation_id)
        if not heads:
            return None
        head = _one(heads)
        revision = _one(select("public.bundle_installation_revision", lambda row:
            row["installation_pk"] == head["installation_pk"] and row["revision"] == head["current_revision"]))
        composition = _one(select("public.bundle_composition", lambda row: row["composition_pk"] == revision["composition_pk"]))
        locked = _one(select("public.bundle_composition_lock", lambda row:
            row["composition_pk"] == revision["composition_pk"] and row["revision"] == revision["lock_revision"]))
        _model_work(locked["lock_payload"], ledger, 16)
        lock = StoredCompositionLock.model_validate(dict(compositionId=str(composition["composition_id"]),
            revision=locked["revision"], payload=locked["lock_payload"], lockHash=locked["lock_hash"],
            permissionDiffHash=locked["permission_diff_hash"], migrationPlanHash=locked["migration_plan_hash"],
            contributionDiffHash=locked["contribution_diff_hash"], createdAt=locked["created_at"]))
        checked = _checked_lock(lock, ledger)
        _check_composition_lock_rows(composition, locked, scope=scope, checked=checked, ledger=ledger)
        return checked
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor stored lock facts") from None


def _predecessor_installation_record(facts, *, scope, installation_id, source_lock, ledger):
    """Reconstruct one original old record; resource and registration proof stays pending."""
    if (type(facts) is not _DecodedFacts or type(scope) is not TenantScope
            or type(installation_id) is not UUID or type(ledger) is not _WorkLedger):
        _invalid()
    _check_predecessor_scope(facts, scope, ledger)
    checked = _checked_lock(source_lock, ledger)
    p = facts.predecessors
    def select(family, field, value):
        rows = p[family]
        ledger._charge(rows=len(rows), node_count=len(rows) * 2)
        return tuple(row for row in rows if row[field] == value)
    try:
        head = _one(select("public.bundle_installation", "installation_id", installation_id))
        pk = head["installation_pk"]
        revisions = select("public.bundle_installation_revision", "installation_pk", pk)
        events = select("public.bundle_installation_event", "installation_pk", pk)
        current = _one(tuple(row for row in revisions if row["revision"] == head["current_revision"]))
        composition = _one(select("public.bundle_composition", "composition_pk", current["composition_pk"]))
        locks = select("public.bundle_composition_lock", "composition_pk", current["composition_pk"])
        locked = _one(tuple(row for row in locks if row["revision"] == current["lock_revision"]))
        _check_composition_lock_rows(composition, locked, scope=scope, checked=checked, ledger=ledger)
        decision = _one(select("public.bundle_installation_decision", "installation_pk", pk))
        if decision["decision_id"] != current["decision_id"]:
            _invalid()
        revision = _installation_revision_from_row(current, str(installation_id), str(composition["composition_id"]))
        model_decision = InstallationDecision.model_validate(dict(
            decisionId=str(decision["decision_id"]), installationId=str(installation_id),
            submittedRevision=decision["submitted_revision"], decision=decision["decision"], actor=decision["actor"],
            lockHash=decision["lock_hash"], permissionDiffHash=decision["permission_diff_hash"],
            migrationPlanHash=decision["migration_plan_hash"], contributionDiffHash=decision["contribution_diff_hash"],
            reason=decision["reason"], createdAt=decision["created_at"]))
        ledger._charge(rows=len(events), node_count=24 + len(events) * 8)
        record = InstallationRecord.model_validate(dict(
            installationId=str(installation_id), displayName=head["display_name"], state=revision.state,
            currentRevision=head["current_revision"], activeRevision=head["active_revision"],
            previousActiveRevision=head["previous_active_revision"], etagVersion=head["etag_version"],
            createdAt=head["created_at"], updatedAt=head["updated_at"], current=revision,
            decision=model_decision, events=[_event_json(row) for row in events]))
        payload = record.model_dump(mode="json", by_alias=True, exclude_none=False, warnings="error")
        _model_work(payload, ledger, 16)
        record = InstallationRecord.model_validate_json(json.dumps(payload, ensure_ascii=False, allow_nan=False))
        _verify_installation_history_rows(record, pk, MappingProxyType({
            "public.bundle_installation": (head,), "public.bundle_installation_revision": revisions,
            "public.bundle_installation_event": events, "public.bundle_composition": (composition,),
        }), scope=scope, checked=checked, ledger=ledger, projected_context=True)
        return LockedInstallation(scope.org_id, scope.project_id, pk, record)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _RegistryFactView:
    registry: Mapping


def _registry_selection_view(facts, checked, ledger):
    """Actual selected rows only; callers must retain whole-registry coverage obligations."""
    coordinates = {(item.publisher, item.id, item.version) for item in checked.payload.resolved}
    names = {(publisher, name) for publisher, name, _ in coordinates}
    ledger._charge(rows=sum(len(rows) for rows in facts.registry.values()), node_count=len(coordinates) * 4)
    bundles = tuple(row for row in facts.registry["public.asset_bundle"] if (row["publisher"], row["bundle_id"]) in names)
    parents = {row["bundle_pk"]: row for row in bundles}
    versions = tuple(row for row in facts.registry["public.asset_bundle_version"] if row["bundle_pk"] in parents
        and (parents[row["bundle_pk"]]["publisher"], parents[row["bundle_pk"]]["bundle_id"], row["version"]) in coordinates)
    version_ids = {row["version_pk"] for row in versions}
    artifacts = tuple(row for row in facts.registry["public.asset_bundle_artifact"] if row["version_pk"] in version_ids)
    return _RegistryFactView(MappingProxyType({"public.asset_bundle": bundles,
        "public.asset_bundle_version": versions, "public.asset_bundle_artifact": artifacts}))


def _predecessor_source_packages(facts, record, *, scope, source_lock, ledger):
    """Check one actual old lock's content subset; global registry coverage stays pending."""
    if (type(facts) is not _DecodedFacts or type(record) is not InstallationRecord
            or type(scope) is not TenantScope or type(ledger) is not _WorkLedger):
        _invalid()
    checked = _checked_lock(source_lock, ledger)
    p = facts.predecessors
    ledger._charge(rows=len(p["public.bundle_composition"]) + len(p["public.bundle_composition_lock"]), node_count=8)
    composition = _one(tuple(row for row in p["public.bundle_composition"]
        if str(row["composition_id"]) == record.current.composition_id))
    locked = _one(tuple(row for row in p["public.bundle_composition_lock"]
        if row["composition_pk"] == composition["composition_pk"] and row["revision"] == record.current.lock_revision))
    checked, candidates = _check_composition_lock_rows(composition, locked, scope=scope, checked=checked, ledger=ledger)
    view = _registry_selection_view(facts, checked, ledger)
    return _registry_content(view, checked, candidates, ledger)


def _predecessor_preparation_resources(facts, *, scope, installation_id, source_lock, ledger):
    """Read every Q-owned retained resource for one actual old installation."""
    try:
        locked = _predecessor_installation_record(facts, scope=scope, installation_id=installation_id,
            source_lock=source_lock, ledger=ledger)
        contents = _predecessor_source_packages(facts, locked.record, scope=scope, source_lock=source_lock, ledger=ledger)
        p = facts.predecessors
        families = ("public.extension_runtime_operation", "public.extension_runtime_event", "public.extension_runtime_resource_lease")
        ledger._charge(rows=sum(len(p[name]) for name in families), node_count=8)
        operations = tuple(row for row in p[families[0]] if row["installation_id"] == installation_id)
        operation_ids = {row["operation_id"] for row in operations}
        events = tuple(row for row in p[families[1]] if row["operation_id"] in operation_ids)
        resources = tuple(row for row in p[families[2]] if row["operation_id"] in operation_ids)
        return _preparation_resources_from_rows(locked.record, contents, MappingProxyType({
            families[0]: operations, families[1]: events, families[2]: resources,
        }), scope=scope, source_lock=source_lock, ledger=ledger)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor preparation facts") from None


def _fact_uuid(value):
    if type(value) is not str:
        _invalid()
    try:
        parsed = UUID(value)
    except ValueError:
        _invalid()
    if str(parsed) != value:
        _invalid()
    return parsed


@dataclass(frozen=True, slots=True)
class _PreparedSource:
    operation_id: UUID
    generation: UUID
    installation_revision: int
    resource_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class _PreparationFacts:
    operations: object
    resources: object
    events: object
    preparations: tuple[_PreparedSource, ...]
    record: InstallationRecord
    contents: tuple[_SelectedContent, ...]


def _runtime_event_rows(operations, rows, *, scope, ledger):
    events = {operation: {} for operation in operations}
    for row in rows:
        ledger._charge(rows=1, node_count=5)
        group = events.get(row["operation_id"])
        if ((row["org_id"], row["project_id"]) != scope.key or group is None
                or row["sequence"] < 1 or row["sequence"] in group or type(row["payload"]) is not dict):
            _invalid()
        _model_work(row["payload"], ledger, 2)
        if row["payload_hash"] != _digest(row["payload"]):
            _invalid()
        group[row["sequence"]] = row
    for operation, group in events.items():
        ledger._charge(node_count=len(group) * 2)
        revision = operations[operation]["revision"]
        if len(group) != revision or any(sequence not in group for sequence in range(1, len(group) + 1)):
            _invalid()
    return events


def _verify_preparation_resources(facts, *, scope, source, locked_source, source_lock, ledger):
    """Link every retained preparation/resource; no six-branch admission result."""
    record = _verify_source_history(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    contents = _verify_source_packages(facts, scope, source_lock, ledger)
    return _preparation_resources_from_rows(record, contents, facts.relations,
        scope=scope, source_lock=source_lock, ledger=ledger)


def _preparation_resources_from_rows(record, contents, relations, *, scope, source_lock, ledger):
    """Original complete preparation/resource proof kernel for a real installation."""
    if (type(record) is not InstallationRecord or type(contents) is not tuple
            or type(scope) is not TenantScope or type(source_lock) is not StoredCompositionLock
            or type(ledger) is not _WorkLedger):
        _invalid()
    expected = {}
    runtime_ids = []
    for item in contents:
        ledger._charge(rows=1, node_count=3)
        if item.manifest.spec.runtime is not None:
            runtime_ids.append(item.selected.id)
        if item.description is not None:
            expected[item.selected.id, item.selected.content_hash] = item.claims_hash
    operations = {}
    for row in relations["public.extension_runtime_operation"]:
        ledger._charge(rows=1, node_count=4)
        if ((row["org_id"], row["project_id"]) != scope.key
                or str(row["installation_id"]) != record.installation_id
                or row["operation_id"] in operations or row["revision"] < 1):
            _invalid()
        operations[row["operation_id"]] = row
    events = _runtime_event_rows(operations, relations["public.extension_runtime_event"], scope=scope, ledger=ledger)
    resource_events = {}
    event_fields = {"resource_created": {"resourceId", "containerId"},
                    "resource_registered": {"resourceId", "containerId", "packageHash", "claimsHash"},
                    "resource_uncertain": {"resourceId"}, "resource_released": {"resourceId"},
                    "resource_intent_cancelled": {"resourceId"}}
    for row in relations["public.extension_runtime_event"]:
        if row["type"] in event_fields:
            payload = row["payload"]
            if set(payload) != event_fields[row["type"]]:
                _invalid()
            resource_id = _fact_uuid(payload["resourceId"])
            resource_events.setdefault(resource_id, []).append(row)
    resources = {}
    resources_by_operation = {operation: {} for operation in operations}
    observations = {}
    for row in relations["public.extension_runtime_resource_lease"]:
        ledger._charge(rows=1, node_count=8)
        operation = operations.get(row["operation_id"])
        if ((row["org_id"], row["project_id"]) != scope.key or operation is None
                or operation["kind"] != "runtime-apply" or row["resource_id"] in resources
                or row["observed_release"] is not True or row["cleanup_state"] != "released"
                or (row["package_id"], row["package_hash"]) not in expected):
            _invalid()
        resources[row["resource_id"]] = row
        resources_by_operation[row["operation_id"]][row["resource_id"]] = row
        seen = {}
        for event in resource_events.get(row["resource_id"], ()):
            ledger._charge(rows=1, node_count=3)
            if event["operation_id"] != row["operation_id"] or event["type"] in seen:
                _invalid()
            seen[event["type"]] = event
        released = [seen[kind] for kind in ("resource_released", "resource_intent_cancelled") if kind in seen]
        if len(released) != 1 or released[0]["sequence"] != max((event["sequence"] for event in seen.values()), default=0):
            _invalid()
        container = row["container_id"]
        if container is not None:
            if (len(container) != 64 or any(char not in "0123456789abcdef" for char in container)
                    or row["create_claimed_at"] is None or "resource_created" not in seen
                    or seen["resource_created"]["payload"] != {"resourceId": str(row["resource_id"]), "containerId": container}):
                _invalid()
        elif "resource_created" in seen or "resource_registered" in seen:
            _invalid()
        if "resource_intent_cancelled" in seen and (container is not None or row["create_claimed_at"] is not None):
            _invalid()
        if "resource_registered" in seen:
            registered = seen["resource_registered"]
            if (registered["payload"] != {"resourceId": str(row["resource_id"]), "containerId": container,
                    "packageHash": row["package_hash"], "claimsHash": expected[row["package_id"], row["package_hash"]]}
                    or seen["resource_created"]["sequence"] >= registered["sequence"]
                    or registered["sequence"] >= released[0]["sequence"]):
                _invalid()
        observations[row["resource_id"]] = seen
    if set(resource_events) - set(resources):
        _invalid()
    for group in resources_by_operation.values():
        ledger._charge(node_count=len(group))
        if len({row["generation"] for row in group.values()}) > 1:
            _invalid()
    installation_preparations = {event.to_revision: event for event in record.events
        if event.evidence is not None and event.evidence.type == "runtime_preparation"}
    used_revisions = set()
    used_generations = set()
    prepared = []
    proof_fields = {"installationId", "installationRevision", "evidenceRef", "evidenceHash", "lockHash",
                    "generation", "resources", "expectedRevision"}
    for operation_id, group in events.items():
        proofs = [event for event in group.values() if event["type"] == "preparation_committed"]
        ledger._charge(rows=len(group), node_count=len(group))
        if not proofs:
            continue
        if (len(proofs) != 1 or not 1 <= len(runtime_ids) <= 64
                or len(set(runtime_ids)) != len(runtime_ids) or len(expected) != len(runtime_ids)):
            _invalid()
        event = proofs[0]; payload = event["payload"]; operation = operations[operation_id]
        if (set(payload) != proof_fields or type(payload["installationRevision"]) is not int
                or type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 1
                or payload["expectedRevision"] + 2 != event["sequence"]
                or payload["installationId"] != record.installation_id or payload["lockHash"] != source_lock.lock_hash
                or operation["kind"] != "runtime-apply" or operation["phase"] != "succeeded"
                or operation["status"] not in {"succeeded", "failed"}):
            _invalid()
        installation_event = installation_preparations.get(payload["installationRevision"])
        generation = _fact_uuid(payload["generation"])
        if (installation_event is None or payload["installationRevision"] in used_revisions
                or generation in used_generations or operation["requested_by"] != installation_event.actor
                or operation["expected_installation_etag"] != installation_event.from_revision
                or payload["evidenceRef"] != installation_event.evidence.evidence_ref
                or payload["evidenceHash"] != installation_event.evidence.evidence_hash):
            _invalid()
        actual = resources_by_operation[operation_id]
        items = payload["resources"]
        if type(items) is not list or len(items) != len(actual) or len(actual) != len(expected):
            _invalid()
        used_resources = set(); packages = set()
        for item in items:
            ledger._charge(rows=1, node_count=8)
            if type(item) is not dict or set(item) != {"resourceId", "containerId", "packageHash", "claimsHash"}:
                _invalid()
            resource_id = _fact_uuid(item["resourceId"]); resource = actual.get(resource_id)
            if resource is None or resource_id in used_resources or resource["generation"] != generation:
                _invalid()
            key = resource["package_id"], resource["package_hash"]
            seen = observations[resource_id]
            if (key in packages or "resource_registered" not in seen
                    or seen["resource_registered"]["payload"] != item
                    or seen["resource_registered"]["sequence"] >= event["sequence"]
                    or seen["resource_released"]["sequence"] <= event["sequence"]):
                _invalid()
            used_resources.add(resource_id); packages.add(key)
        if used_resources != set(actual) or packages != set(expected):
            _invalid()
        used_revisions.add(payload["installationRevision"]); used_generations.add(generation)
        prepared.append(_PreparedSource(operation_id, generation, payload["installationRevision"], tuple(used_resources)))
    if used_revisions != set(installation_preparations):
        _invalid()
    return _PreparationFacts(MappingProxyType(operations), MappingProxyType(resources),
        MappingProxyType({key: tuple(group.values()) for key, group in events.items()}), tuple(prepared), record, contents)


@dataclass(frozen=True, slots=True)
class _RuntimeNotificationFacts:
    preparation_facts: _PreparationFacts
    pending_event_ids: tuple[UUID, ...]
    delivered_event_ids: tuple[UUID, ...]


def _verify_runtime_notifications(facts, *, scope, source, locked_source, source_lock, ledger):
    """Classify current known terminal consumers; never ACK or expire a claim."""
    prepared = _verify_preparation_resources(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    return _runtime_notification_rows(prepared, facts.relations["public.extension_runtime_outbox"],
        scope=scope, ledger=ledger)


def _runtime_notification_rows(prepared, rows, *, scope, ledger):
    """Original complete terminal notification classification, without ACK."""
    if type(prepared) is not _PreparationFacts or type(scope) is not TenantScope or type(ledger) is not _WorkLedger:
        _invalid()
    event_index = {}
    # These are the five concrete filtered consumers audited with this source.
    # A new consumer/kind requires its own contract, including delivered rows.
    ack_only_kinds = frozenset({"runtime-apply", "runtime-verify", "enable", "configure", "disable"})
    for operation_id, operation in prepared.operations.items():
        ledger._charge(rows=1, node_count=4)
        path = _PATHS.get(operation["kind"])
        if (path is None or operation["phase"] not in path
                or operation["status"] not in {"succeeded", "failed", "cancelled"}
                or (operation["status"] == "succeeded" and operation["phase"] != path[-1])):
            _invalid()
        for event in prepared.events[operation_id]:
            ledger._charge(rows=1, node_count=2)
            if event["event_id"] in event_index:
                _invalid()
            event_index[event["event_id"]] = operation_id
    seen = set(); pending = []; delivered = []
    for row in rows:
        ledger._charge(rows=1, node_count=7)
        operation_id = event_index.get(row["event_id"])
        if ((row["org_id"], row["project_id"]) != scope.key
                or operation_id is None or row["event_id"] in seen
                or row["consumer_id"] != "runtime-reconciler"
                or prepared.operations[operation_id]["kind"] not in ack_only_kinds
                or type(row["attempt"]) is not int or not 0 <= row["attempt"] <= 2147483647
                or row["claim_until"] is not None
                or (row["delivered_at"] is not None and row["attempt"] < 1)):
            _invalid()
        seen.add(row["event_id"])
        (pending if row["delivered_at"] is None else delivered).append(row["event_id"])
    if seen != set(event_index):
        _invalid()
    return _RuntimeNotificationFacts(prepared, tuple(pending), tuple(delivered))


@dataclass(frozen=True, slots=True)
class _AttemptDependencyFacts:
    notifications: _RuntimeNotificationFacts
    binding: object
    attempts: object
    dependencies: tuple


def _attempt_reason_shape(row):
    reason, error = row["terminal_reason_code"], row["terminal_error_type"]
    if error is not None and (type(error) is not str or _ERROR_TYPE.fullmatch(error) is None):
        _invalid()
    if row["state"] == "succeeded":
        if reason is not None or error is not None:
            _invalid()
    elif row["state"] == "failed":
        if reason is None:
            if error is not None:
                _invalid()
        elif reason not in _TERMINAL_REASONS:
            _invalid()
    elif row["state"] == "abandoned":
        if reason not in (None, "ATTEMPT_LEASE_EXPIRED") or error is not None:
            _invalid()
    else:
        _invalid()


def _verify_attempt_dependencies(facts, *, scope, source, locked_source, source_lock, ledger):
    """Read terminal attempt history and both dependency directions; no recovery."""
    notifications = _verify_runtime_notifications(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    bindings = facts.relations["public.extension_runtime_binding"]
    binding = _one(bindings) if bindings else None
    if binding is not None:
        ledger._charge(rows=1, node_count=8)
        if ((binding["org_id"], binding["project_id"]) != scope.key
                or str(binding["installation_id"]) != source.installation_id
                or binding["desired_state"] != "uninstalled" or binding["observed_state"] != "stopped"
                or binding["enabled"] is not False or binding["operation_fence"] is not True
                or binding["package_lock_ref"] != {"lockHash": source_lock.lock_hash}):
            _invalid()
    return _attempt_dependency_rows(notifications, binding, facts.relations,
        scope=scope, installation_id=source.installation_id, ledger=ledger)


def _attempt_dependency_rows(notifications, binding, relations, *, scope, installation_id, ledger):
    """Original terminal attempt/event and both-direction dependency history."""
    if (type(notifications) is not _RuntimeNotificationFacts or type(scope) is not TenantScope
            or type(installation_id) is not str or type(ledger) is not _WorkLedger
            or installation_id != notifications.preparation_facts.record.installation_id):
        _invalid()
    attempts = {}; natural = set()
    for row in relations["public.extension_runtime_execution_attempt"]:
        ledger._charge(rows=1, node_count=12)
        if (binding is None or (row["org_id"], row["project_id"]) != scope.key
                or str(row["installation_id"]) != installation_id or row["generation"] != binding["generation"]
                or not 1 <= row["execution_epoch"] < binding["execution_epoch"]
                or row["state"] not in _TERMINAL or row["completed_at"] is None or row["revision"] < 2
                or row["operation_kind"] not in {"signed_read", "recoverable_store"}
                or not 1 <= len(row["operation_key"]) <= 160 or not 1 <= len(row["idempotency_key"]) <= 240
                or _HASH.fullmatch(row["request_hash"]) is None or row["attempt_id"] in attempts):
            _invalid()
        _attempt_reason_shape(row)
        key = row["generation"], row["execution_epoch"], row["operation_kind"], row["idempotency_key"]
        if key in natural:
            _invalid()
        natural.add(key); attempts[row["attempt_id"]] = row
    groups = {key: {} for key in attempts}; event_ids = set()
    for event in relations["public.extension_runtime_execution_attempt_event"]:
        ledger._charge(rows=1, node_count=6)
        group = groups.get(event["attempt_id"])
        if ((event["org_id"], event["project_id"]) != scope.key or group is None
                or event["event_id"] in event_ids or event["sequence"] in group
                or event["sequence"] != event["revision"] or event["sequence"] < 1):
            _invalid()
        group[event["sequence"]] = event; event_ids.add(event["event_id"])
    for attempt_id, row in attempts.items():
        group = groups[attempt_id]
        ledger._charge(node_count=len(group) * 2)
        if len(group) != row["revision"] or any(sequence not in group for sequence in range(1, len(group) + 1)):
            _invalid()
        for sequence, event in group.items():
            ledger._charge(rows=1, node_count=5)
            if sequence == row["revision"]:
                if (event["state"] != row["state"] or event["type"] != "attempt_" + row["state"]
                        or event["terminal_reason_code"] != row["terminal_reason_code"]
                        or event["terminal_error_type"] != row["terminal_error_type"]):
                    _invalid()
            elif (event["state"] != "running"
                    or event["type"] != ("attempt_accepted" if sequence == 1 else "attempt_heartbeat")
                    or event["terminal_reason_code"] is not None or event["terminal_error_type"] is not None):
                _invalid()
        if (row["heartbeat_at"] is not None) != (row["revision"] > 2):
            _invalid()
    dependencies = relations["public.extension_runtime_dependency_ref"]
    for row in dependencies:
        ledger._charge(rows=1, node_count=8)
        if ((row["org_id"], row["project_id"]) != scope.key or binding is None
                or row["kind"] not in {"capability", "data", "reconcile"}
                or row["revision"] < 1 or row["active"] is not False):
            _invalid()
        source_ends = [row[end + "_generation"] for end in ("consumer", "provider")
                       if str(row[end + "_installation"]) == installation_id]
        if not source_ends or any(generation != binding["generation"] for generation in source_ends):
            _invalid()
    return _AttemptDependencyFacts(notifications, binding, MappingProxyType(attempts), tuple(dependencies))


def _authority_object(raw, content_hash, ledger):
    """Verify the original SQL text bytes, then parse under shared work limits."""
    if type(raw) is not str or type(content_hash) is not str or type(ledger) is not _WorkLedger:
        _invalid()
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid terminal facts") from None
    if len(encoded) > _MAX_JSON_BYTES:
        raise ValueError("terminal facts budget exceeded")
    ledger._charge(byte_count=len(encoded) * 2)
    if content_hash != "sha256:" + hashlib.sha256(encoded).hexdigest():
        _invalid()
    # Budget preflight only. json.loads remains the syntax authority; do not
    # allocate a deeply nested or oversized token graph before enforcing caps.
    quoted = escaped = atom = False
    depth = nodes = 0
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        token = False
        if char == '"':
            quoted = True; atom = False; token = True
        elif char in "[{":
            depth += 1; atom = False; token = True
            if depth > _MAX_JSON_DEPTH + 1:
                raise ValueError("terminal facts budget exceeded")
        elif char in "]}":
            depth -= 1; atom = False
            if depth < 0:
                _invalid()
        elif char in " \t\r\n,:":
            atom = False
        elif not atom:
            atom = True; token = True
        if token:
            nodes += 1; ledger._charge(node_count=1)
            if nodes > _MAX_JSON_NODES:
                raise ValueError("terminal facts budget exceeded")
    if quoted or depth:
        _invalid()
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _invalid()
            result[key] = value
        return result
    def constant(value):
        _invalid()
    try:
        body = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError, OverflowError):
        raise ValueError("invalid terminal facts") from None
    if type(body) is not dict:
        _invalid()
    _measure_json(body, ledger, _MAX_JSON_BYTES)
    return body


@dataclass(frozen=True, slots=True)
class _UninstallReceiptFacts:
    context: _AttemptDependencyFacts
    receipt: object
    authority: object


def _read_uninstall_receipt(facts, *, scope, source, locked_source, source_lock, ledger):
    """Read exact receipt shapes; their claims still require branch proof graphs."""
    context = _verify_attempt_dependencies(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    rows = facts.relations["public.extension_runtime_uninstall_receipt"]
    binding = context.binding
    if binding is None and not rows:
        return _UninstallReceiptFacts(context, None, None)
    if binding is None:
        _invalid()
    row = _one(rows); ledger._charge(rows=1, node_count=12)
    record = context.notifications.preparation_facts.record
    if ((row["org_id"], row["project_id"]) != scope.key
            or str(row["installation_id"]) != source.installation_id or row["generation"] != binding["generation"]
            or row["installation_revision"] + 1 != source.terminal_revision
            or binding["installation_revision"] != row["installation_revision"]
            or row["binding_revision"] != binding["revision"] or row["binding_revision"] <= 1
            or record.events[-1].from_state != "active" or row["actor"] != record.events[-1].actor):
        _invalid()
    references = ("disable_operation_id", "activation_operation_id", "unactivated_disable_operation_id",
                  "runtime_enable_operation_id", "runtime_disable_operation_id")
    masks = {"detached": (True, True, False, False, False), "never_enabled": (False,) * 5,
             "configured_unactivated": (False, False, True, False, False),
             "unconfigured_disabled": (False, False, True, False, False),
             "enabled_undispatched": (False, False, False, True, True)}
    kind = row["retirement_kind"]
    if kind not in masks or tuple(row[name] is not None for name in references) != masks[kind]:
        _invalid()
    body = _authority_object(row["authority_data_text"], row["content_hash"], ledger)
    common = {"orgId", "projectId", "installationId", "generation", "installationRevision", "releasedResourceCount", "actor"}
    extras = {"detached": {"schemaVersion", "bindingFromRevision", "bindingToRevision", "disableOperationId",
                "activationOperationId", "cutoverGroupId", "legacyDispatchCount", "claimedOccurrenceCount", "openDispatchAttemptCount", "runningRuntimeAttemptCount"},
        "never_enabled": {"bindingRevision", "retirementKind", "configurationCount", "enableCount", "dispatchCount", "businessExecutionCount"},
        "unconfigured_disabled": {"bindingRevision", "retirementKind", "configurationCount", "enableCount", "dispatchCount", "businessExecutionCount", "disableOperationId"},
        "configured_unactivated": {"bindingRevision", "retirementKind", "configRef", "disableOperationId", "successfulEnableCount", "dispatchCount", "businessExecutionCount"},
        "enabled_undispatched": {"bindingRevision", "retirementKind", "configRef", "disableOperationId", "enableOperationId", "successfulEnableCount", "dispatchCount", "businessExecutionCount"}}
    ledger._charge(node_count=len(body))
    if (set(body) != common | extras[kind]
            or (body["orgId"], body["projectId"]) != scope.key
            or body["installationId"] != source.installation_id or body["generation"] != str(binding["generation"])
            or body["installationRevision"] != row["installation_revision"] or body["actor"] != row["actor"]):
        _invalid()
    numeric = [name for name in body if name.endswith("Count") or name in
               ("installationRevision", "bindingRevision", "bindingFromRevision", "bindingToRevision")]
    for name in numeric:
        if type(body[name]) is not int or not 0 <= body[name] <= 9223372036854775807:
            _invalid()
    resource_rows = context.notifications.preparation_facts.resources.values()
    ledger._charge(rows=len(resource_rows), node_count=len(resource_rows))
    resource_count = sum(kind != "detached" or resource["generation"] == binding["generation"] for resource in resource_rows)
    if resource_count < 1 or body["releasedResourceCount"] != resource_count:
        _invalid()
    if kind == "detached":
        if (body["schemaVersion"] != "ar2-runtime-uninstall/v1"
                or body["bindingFromRevision"] + 1 != row["binding_revision"]
                or body["bindingToRevision"] != row["binding_revision"]
                or body["disableOperationId"] != str(row["disable_operation_id"])
                or body["activationOperationId"] != str(row["activation_operation_id"])
                or body["legacyDispatchCount"] != 9
                or any(body[name] != 0 for name in ("claimedOccurrenceCount", "openDispatchAttemptCount", "runningRuntimeAttemptCount"))):
            _invalid()
        _fact_uuid(body["cutoverGroupId"])
    else:
        if (body["bindingRevision"] != row["binding_revision"] or body["retirementKind"] != kind
                or body["dispatchCount"] != 0 or body["businessExecutionCount"] != 0):
            _invalid()
        if kind in {"never_enabled", "unconfigured_disabled"}:
            if binding["config_ref"] is not None or body["configurationCount"] != 0 or body["enableCount"] != 0:
                _invalid()
            if kind == "unconfigured_disabled" and body["disableOperationId"] != str(row["unactivated_disable_operation_id"]):
                _invalid()
        else:
            _model_work(body["configRef"], ledger, 4)
            config = ConfigurationRef.model_validate_json(json.dumps(body["configRef"], ensure_ascii=False, allow_nan=False))
            if config.model_dump(mode="json") != binding["config_ref"]:
                _invalid()
            enabled = kind == "enabled_undispatched"
            disable_column = "runtime_disable_operation_id" if enabled else "unactivated_disable_operation_id"
            if (body["disableOperationId"] != str(row[disable_column]) or body["successfulEnableCount"] != int(enabled)
                    or (enabled and body["enableOperationId"] != str(row["runtime_enable_operation_id"]))):
                _invalid()
    return _UninstallReceiptFacts(context, row, MappingProxyType(body))


@dataclass(frozen=True, slots=True)
class _ConfigurationHistory:
    versions: object
    current: ConfigurationRef | None


def _configuration_history(facts, *, scope, installation_id, generation, binding_ref, ledger):
    """Decode every retained version; a staged successor need not be applied.

    The projected request hash has no independent historical CAS operands.
    Its shape is checked, never reconstructed from guessed binding versions.
    """
    groups = {}; versions = {}; keys = set()
    target = (*scope.key, UUID(installation_id), generation)
    try:
        for row in facts.relations["public.extension_runtime_configuration"]:
            ledger._charge(rows=1, node_count=12)
            if ((row["org_id"], row["project_id"]) != scope.key
                    or row["installation_id"] != target[2] or row["generation"] != generation
                    or type(row["revision"]) is not int or not 1 <= row["revision"] < 2**63
                    or type(row["actor"]) is not str or not 1 <= len(row["actor"]) <= 240
                    or not row["actor"].isprintable() or row["actor"] != row["actor"].strip()
                    or _HASH.fullmatch(row["request_hash"]) is None):
                _invalid()
            key = validate_idempotency_key(row["idempotency_key"])
            if key in keys:
                _invalid()
            keys.add(key)
            _model_work(row["payload"], ledger, 8)
            reference, document = configuration_store._decode(target, row)
            identity = row["configuration_id"]; revision = row["revision"]
            group = groups.setdefault(identity, {})
            if revision in group:
                _invalid()
            group[revision] = row
            versions[identity, revision] = (reference, document)
        for identity, group in groups.items():
            ledger._charge(node_count=len(group) * 3)
            previous = None
            for expected, revision in enumerate(sorted(group), 1):
                row = group[revision]
                if revision != expected or row["previous_hash"] != previous:
                    _invalid()
                previous = row["content_hash"]
        current = None
        if binding_ref is not None:
            _model_work(binding_ref, ledger, 4)
            current = ConfigurationRef.model_validate_json(json.dumps(binding_ref, allow_nan=False))
            item = versions.get((UUID(current.configurationId), current.revision))
            if item is None or item[0] != current:
                _invalid()
        return _ConfigurationHistory(MappingProxyType(versions), current)
    except (ValueError, TypeError, OverflowError, configuration_store.RuntimeConflict, AssetRegistryError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _VerifiedRuntimeGraph:
    receipt: _UninstallReceiptFacts
    verification_operation: UUID
    preparation: _PreparedSource
    configurations: _ConfigurationHistory


def _verified_runtime_graph(facts, *, scope, source, locked_source, source_lock, ledger):
    """Link original verification producers; control timelines remain separate."""
    receipt = _read_uninstall_receipt(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    context = receipt.context
    prepared = context.notifications.preparation_facts
    binding = context.binding
    if binding is None or receipt.receipt is None or binding["profile_ref"] != "internal-python-v1":
        _invalid()
    operation_id, preparation = _runtime_verification_proof(prepared, binding,
        installation_id=source.installation_id, ledger=ledger)
    configurations = _configuration_history(facts, scope=scope, installation_id=source.installation_id,
        generation=binding["generation"], binding_ref=binding["config_ref"], ledger=ledger)
    return _VerifiedRuntimeGraph(receipt, operation_id, preparation, configurations)


def _runtime_verification_proof(prepared, binding, *, installation_id, ledger):
    """Original verification producer and actual binding/resource linkage."""
    if (type(prepared) is not _PreparationFacts or type(ledger) is not _WorkLedger
            or type(installation_id) is not str or installation_id != prepared.record.installation_id
            or str(binding["installation_id"]) != installation_id):
        _invalid()
    installation_events = {event.to_revision: event for event in prepared.record.events
        if event.evidence is not None and event.evidence.type == "verification"}
    linked = {}; used = set()
    fields = {"installationId", "installationRevision", "generation", "preparationOperationId",
              "evidenceHash", "healthCheckedAt", "enabled"}
    for operation_id, events in prepared.events.items():
        operation = prepared.operations[operation_id]
        proofs = [event for event in events if event["type"] == "verification_committed"]
        ledger._charge(rows=len(events), node_count=len(events) * 2)
        if not proofs:
            if operation["kind"] == "runtime-verify" and operation["status"] == "succeeded":
                _invalid()
            continue
        if (len(proofs) != 1 or operation["kind"] != "runtime-verify"
                or operation["status"] != "succeeded" or operation["phase"] != "succeeded"
                or operation["revision"] != 5 or operation["failure_code"] is not None
                or operation["expected_binding_revision"] is not None
                or _HASH.fullmatch(operation["request_hash"]) is None):
            _invalid()
        ordered = sorted(events, key=lambda event: event["sequence"])
        if [event["type"] for event in ordered] != ["accepted", "validating", "committing", "verification_committed", "succeeded"]:
            _invalid()
        for index, expected in ((0, {"kind": "runtime-verify"}), (1, {"previousPhase": "accepted"}),
                                (2, {"previousPhase": "validating"}), (4, {"previousPhase": "committing"})):
            if ordered[index]["payload"] != expected:
                _invalid()
        body = proofs[0]["payload"]
        if (set(body) != fields or type(body["installationRevision"]) is not int
                or body["enabled"] is not False or body["installationId"] != installation_id):
            _invalid()
        event = installation_events.get(body["installationRevision"])
        if (event is None or event.to_revision in used or event.to_revision != binding["installation_revision"]
                or operation["requested_by"] != event.actor
                or operation["expected_installation_etag"] != event.from_revision
                or body["evidenceHash"] != event.evidence.evidence_hash
                or _fact_uuid(body["generation"]) != binding["generation"]):
            _invalid()
        preparation_id = _fact_uuid(body["preparationOperationId"])
        matches = [item for item in prepared.preparations if item.operation_id == preparation_id
            and item.generation == binding["generation"] and item.installation_revision == event.from_revision]
        ledger._charge(node_count=len(prepared.preparations) * 3)
        if len(matches) != 1 or prepared.operations[preparation_id]["status"] != "succeeded":
            _invalid()
        proof = _one([item for item in prepared.events[preparation_id] if item["type"] == "preparation_committed"])
        handle = {"preparationOperationId": str(preparation_id), "resources": proof["payload"]["resources"]}
        if binding["resource_handle_ref"] != handle:
            _invalid()
        checked_at = _scalar(body["healthCheckedAt"], "timestamp with time zone!", ledger)
        # Runtime event occurred_at uses transaction now(); it is not this clock.
        if not 0 <= (event.evidence.observed_at - checked_at).total_seconds() <= 3:
            _invalid()
        used.add(event.to_revision); linked[operation_id] = matches[0]
    if used != set(installation_events) or len(linked) != 1:
        _invalid()
    return next(iter(linked.items()))


@dataclass(frozen=True, slots=True)
class _PredecessorVerificationFacts:
    preparations: _PreparationFacts
    binding: Mapping
    verification_operation: UUID
    preparation: _PreparedSource
    configurations: _ConfigurationHistory
    partition: Mapping


def _predecessor_runtime_verification(facts, *, scope, installation_id, generation, source_lock, ledger):
    """Historical verification leaf; no receipt or whole-source admission is fabricated."""
    if type(generation) is not UUID:
        _invalid()
    try:
        prepared = _predecessor_preparation_resources(facts, scope=scope, installation_id=installation_id,
            source_lock=source_lock, ledger=ledger)
        p = facts.predecessors
        ledger._charge(rows=len(p["public.extension_runtime_binding"]), node_count=8)
        binding = MappingProxyType(_one(tuple(row for row in p["public.extension_runtime_binding"]
            if row["installation_id"] == installation_id and row["generation"] == generation)))
        if ((binding["org_id"], binding["project_id"]) != scope.key
                or binding["profile_ref"] != "internal-python-v1"
                or binding["package_lock_ref"] != {"lockHash": source_lock.lock_hash}):
            _invalid()
        operation_id, preparation = _runtime_verification_proof(prepared, binding,
            installation_id=str(installation_id), ledger=ledger)
        ledger._charge(rows=len(p["public.extension_runtime_configuration"]), node_count=8)
        configurations = tuple(row for row in p["public.extension_runtime_configuration"]
            if row["installation_id"] == installation_id and row["generation"] == generation)
        view = _ConfigurationFactView(MappingProxyType({"public.extension_runtime_configuration": configurations}))
        history = _configuration_history(view, scope=scope, installation_id=str(installation_id),
            generation=generation, binding_ref=binding["config_ref"], ledger=ledger)
        return _PredecessorVerificationFacts(prepared, binding, operation_id, preparation, history, facts.predecessors)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor verification facts") from None


@dataclass(frozen=True, slots=True)
class _PredecessorProtocolFacts:
    verification: _PredecessorVerificationFacts
    context: _AttemptDependencyFacts
    partition: Mapping


def _predecessor_runtime_protocol(facts, verification, *, scope, ledger):
    """Read old terminal notifications and attempts on the same actual proof parent."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(verification) is not _PredecessorVerificationFacts
            or verification.partition is not facts.predecessors):
        _invalid()
    p = facts.predecessors; prepared = verification.preparations
    installation_id = verification.binding["installation_id"]
    try:
        event_ids = {row["event_id"] for rows in prepared.events.values() for row in rows}
        families = ("public.extension_runtime_outbox", "public.extension_runtime_execution_attempt",
            "public.extension_runtime_execution_attempt_event", "public.extension_runtime_dependency_ref")
        ledger._charge(rows=sum(len(p[name]) for name in families), node_count=len(event_ids) * 2)
        outboxes = tuple(row for row in p[families[0]] if row["event_id"] in event_ids)
        notifications = _runtime_notification_rows(prepared, outboxes, scope=scope, ledger=ledger)
        attempts = tuple(row for row in p[families[1]] if row["installation_id"] == installation_id)
        attempt_ids = {row["attempt_id"] for row in attempts}
        events = tuple(row for row in p[families[2]] if row["attempt_id"] in attempt_ids)
        dependencies = tuple(row for row in p[families[3]]
            if row["consumer_installation"] == installation_id or row["provider_installation"] == installation_id)
        context = _attempt_dependency_rows(notifications, verification.binding, MappingProxyType({
            families[1]: attempts, families[2]: events, families[3]: dependencies,
        }), scope=scope, installation_id=str(installation_id), ledger=ledger)
        return _PredecessorProtocolFacts(verification, context, p)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor runtime protocol facts") from None


@dataclass(frozen=True, slots=True)
class _ControlCommit:
    operation_id: UUID
    kind: str
    from_revision: int
    to_revision: int
    execution_epoch: int
    config_ref: ConfigurationRef | None


@dataclass(frozen=True, slots=True)
class _ControlHistory:
    graph: _VerifiedRuntimeGraph
    targets: object
    commits: object
    cancelled: tuple[UUID, ...]
    stale: tuple[UUID, ...]


def _control_history(facts, *, scope, source, locked_source, source_lock, ledger):
    """Verify accepted targets and their original terminal producers, not reachability."""
    graph = _verified_runtime_graph(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    prepared = graph.receipt.context.notifications.preparation_facts
    binding = graph.receipt.context.binding
    history = _control_commit_history(prepared.operations, prepared.events, scope=scope,
        installation_id=UUID(source.installation_id), generation=binding["generation"],
        installation_revision=binding["installation_revision"], binding_revision=binding["revision"],
        configurations=graph.configurations, preparation_operation_id=graph.preparation.operation_id, ledger=ledger)
    return _ControlHistory(graph, history.targets, history.commits, history.cancelled, history.stale)


@dataclass(frozen=True, slots=True)
class _ControlCommitHistory:
    targets: Mapping
    commits: Mapping
    cancelled: tuple
    stale: tuple


def _control_commit_history(operations, events_by_operation, *, scope, installation_id, generation,
        installation_revision, binding_revision, configurations, preparation_operation_id, ledger):
    """The original accepted-target and terminal-producer kernel, without a terminal source."""
    if (type(scope) is not TenantScope or type(installation_id) is not UUID or type(generation) is not UUID
            or type(preparation_operation_id) is not UUID or type(configurations) is not _ConfigurationHistory
            or type(ledger) is not _WorkLedger):
        _invalid()
    targets = {}; commits = {}; cancelled = {}; stale = []; natural = set()
    proof_kinds = {"configure": "configuration_committed", "enable": "enabled_committed", "disable": "disabled_committed"}
    try:
        for operation_id, operation in operations.items():
            kind = operation["kind"]
            events = sorted(events_by_operation[operation_id], key=lambda event: event["sequence"])
            ledger._charge(rows=len(events), node_count=len(events) * 3)
            if kind not in proof_kinds:
                if any(event["type"] in proof_kinds.values() for event in events):
                    _invalid()
                continue
            key = (kind, validate_idempotency_key(operation["idempotency_key"]))
            if key in natural or operation["expected_installation_etag"] != installation_revision:
                _invalid()
            natural.add(key)
            target_key = "bindingTarget" if kind == "disable" else "configurationTarget"
            accepted = events[0]
            payload = accepted["payload"]
            if (accepted["sequence"] != 1 or accepted["type"] != "accepted"
                    or set(payload) != {"kind", target_key} or payload["kind"] != kind):
                _invalid()
            _model_work(payload[target_key], ledger, 6)
            model = DisableTarget if kind == "disable" else ConfigureTarget
            target = model.model_validate_json(json.dumps(payload[target_key], allow_nan=False))
            if (UUID(target.generation) != generation
                    or target.bindingRevision != operation["expected_binding_revision"]
                    or operation["request_hash"] != _request_hash(kind=kind, actor=operation["requested_by"],
                        etag=operation["expected_installation_etag"], deadline=operation["deadline"],
                        **{"binding_target" if kind == "disable" else "configuration_target": target.model_dump(mode="json")})):
                _invalid()
            if kind != "disable":
                actual = configurations.versions.get((UUID(target.configRef.configurationId), target.configRef.revision))
                if actual is None or actual[0] != target.configRef:
                    _invalid()
            targets[operation_id] = target
            path = _PATHS[kind]
            if operation["status"] == "succeeded":
                expected_types = [*path[:-1], proof_kinds[kind], path[-1]]
                if operation["failure_code"] is not None or [event["type"] for event in events] != expected_types:
                    _invalid()
                for index in range(1, len(path) - 1):
                    if events[index]["payload"] != {"previousPhase": path[index - 1]}:
                        _invalid()
                if events[-1]["payload"] != {"previousPhase": path[-2]}:
                    _invalid()
                body = events[-2]["payload"]
                common = {"installationId", "generation", "bindingRevision", "executionEpoch"}
                extras = {"configure": {"configRef", "enabled", "observedState"},
                          "enable": {"configRef", "preparationOperationId", "healthCheckedAt"},
                          "disable": {"resourcesRetained"}}
                if (set(body) != common | extras[kind] or body["installationId"] != str(installation_id)
                        or body["generation"] != target.generation
                        or any(type(body[name]) is not int or not 1 <= body[name] < 2**63
                               for name in ("bindingRevision", "executionEpoch"))
                        or body["bindingRevision"] != target.bindingRevision + (1 if kind == "enable" else 2)):
                    _invalid()
                config_ref = None
                if kind != "disable":
                    _model_work(body["configRef"], ledger, 4)
                    config_ref = ConfigurationRef.model_validate_json(json.dumps(body["configRef"], allow_nan=False))
                    if config_ref != target.configRef:
                        _invalid()
                if kind == "configure" and (body["enabled"] is not False or body["observedState"] != "unknown"):
                    _invalid()
                if kind == "enable":
                    if _fact_uuid(body["preparationOperationId"]) != preparation_operation_id:
                        _invalid()
                    # No independent per-enable control clock is projected here.
                    _scalar(body["healthCheckedAt"], "timestamp with time zone!", ledger)
                if kind == "disable" and body["resourcesRetained"] is not True:
                    _invalid()
                commits[operation_id] = _ControlCommit(operation_id, kind, target.bindingRevision,
                    body["bindingRevision"], body["executionEpoch"], config_ref)
            elif operation["status"] == "cancelled" and kind in {"configure", "enable"}:
                phase = operation["phase"]
                if phase not in {"accepted", "validating"} or operation["failure_code"] is not None:
                    _invalid()
                prefix = list(path[:path.index(phase) + 1])
                if [event["type"] for event in events] != prefix + ["cancelled_for_disable"]:
                    _invalid()
                if phase == "validating" and events[1]["payload"] != {"previousPhase": "accepted"}:
                    _invalid()
                body = events[-1]["payload"]
                if set(body) != {"previousPhase", "disableOperationId", "actor"} or body["previousPhase"] != phase:
                    _invalid()
                cancelled[operation_id] = (_fact_uuid(body["disableOperationId"]), body["actor"])
            elif operation["status"] == "failed" and kind == "disable":
                if (operation["phase"] != "accepted" or operation["failure_code"] != "DISABLE_TARGET_STALE"
                        or [event["type"] for event in events] != ["accepted", "disable_target_stale"]):
                    _invalid()
                body = events[-1]["payload"]
                if (set(body) != {"installationId", "generation", "acceptedBindingRevision", "currentBindingRevision", "failureCode"}
                        or body["installationId"] != str(installation_id) or body["generation"] != target.generation
                        or type(body["acceptedBindingRevision"]) is not int or type(body["currentBindingRevision"]) is not int
                        or body["acceptedBindingRevision"] != target.bindingRevision
                        or not target.bindingRevision < body["currentBindingRevision"] < binding_revision
                        or body["failureCode"] != operation["failure_code"]):
                    _invalid()
                stale.append(operation_id)
            else:
                _invalid()
        for operation_id, (disable_id, actor) in cancelled.items():
            other = commits.get(disable_id)
            if (other is None or other.kind != "disable" or other.from_revision != targets[operation_id].bindingRevision
                    or actor != operations[disable_id]["requested_by"]):
                _invalid()
        return _ControlCommitHistory(MappingProxyType(targets), MappingProxyType(commits), tuple(cancelled), tuple(stale))
    except (ValueError, TypeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _BindingVersion:
    execution_epoch: int
    config_ref: ConfigurationRef | None
    enabled: bool
    observed_state: str


@dataclass(frozen=True, slots=True)
class _ControlTimeline:
    history: _ControlHistory
    before_uninstall_revision: int
    execution_epoch: int
    cleanup_revision: int | None
    versions: object


@dataclass(frozen=True, slots=True)
class _CutoverBindingStep:
    operation_id: UUID
    kind: str
    from_revision: int
    to_revision: int
    execution_epoch: int


def _control_timeline(facts, *, scope, source, locked_source, source_lock, ledger):
    """Derive a bounded reachable binding history from original CAS operands.

    Transaction-start timestamps cannot order cross-operation effects. The
    source writer/lock provenance and physical cleanup remain separate evidence.
    """
    history = _control_history(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    return _derive_control_timeline(history, ledger)


def _cutover_binding_steps(cutovers, generation, ledger):
    steps = []
    ledger._charge(rows=len(cutovers.activations), node_count=12 * len(cutovers.activations))
    for identity, cutover in cutovers.activations.items():
        prepare = cutover.prepared.receipt
        if prepare.target_generation != generation:
            continue
        for phase, offset in (("pause", 0), ("resume", 1)):
            if phase not in cutover.receipts:
                continue
            revision = prepare.target_runtime_revision + offset
            if not 1 <= revision < revision + 1 < 2**63:
                _invalid()
            steps.append(_CutoverBindingStep(identity, "cutover-" + phase, revision, revision + 1, prepare.target_execution_epoch))
    return steps


def _derive_control_timeline(history, ledger, *, detached=None):
    """One CAS kernel; additional steps can only come from the verified joined graph."""
    if type(history) is not _ControlHistory:
        _invalid()
    if detached is not None and (type(detached) is not _DetachedRefreshGraph or detached.lifecycle.history is not history):
        _invalid()
    graph = history.graph
    binding = graph.receipt.context.binding
    prepared = graph.receipt.context.notifications.preparation_facts
    current_resources = [item for item in prepared.resources.values() if item["generation"] == binding["generation"]]
    ledger._charge(rows=len(prepared.resources), node_count=len(current_resources))
    if not current_resources:
        _invalid()
    steps = list(history.commits.values())
    if detached is not None:
        steps.extend(_cutover_binding_steps(detached.cutovers, binding["generation"], ledger))
    result = _binding_step_timeline(steps, expected_revision=binding["revision"] - 1,
        execution_epoch=binding["execution_epoch"], configuration=graph.configurations.current, ledger=ledger)
    versions = result.versions
    for operation_id in history.stale:
        target = history.targets[operation_id]
        event = max(prepared.events[operation_id], key=lambda row: row["sequence"])
        ledger._charge(rows=1, node_count=4)
        if target.bindingRevision not in versions or event["payload"]["currentBindingRevision"] not in versions:
            _invalid()
    return _ControlTimeline(history, result.revision, result.execution_epoch, result.cleanup_revision, result.versions)


@dataclass(frozen=True, slots=True)
class _BindingStepTimeline:
    revision: int
    execution_epoch: int
    cleanup_revision: int | None
    versions: Mapping


def _binding_step_timeline(steps, *, expected_revision, execution_epoch, configuration, ledger):
    """One original CAS-version kernel, independent of terminal installation state."""
    if (type(expected_revision) is not int or not 1 <= expected_revision < 2**63
            or type(execution_epoch) is not int or not 1 <= execution_epoch < 2**63
            or type(ledger) is not _WorkLedger):
        _invalid()
    ordered = sorted(steps, key=lambda commit: commit.from_revision)
    if len({step.from_revision for step in ordered}) != len(ordered):
        _invalid()
    last_enable = max((index for index, commit in enumerate(ordered) if commit.kind in {"enable", "cutover-resume"}), default=-1)
    revision = 1
    state = _BindingVersion(1, None, False, "ready")
    versions = {revision: state}
    cleanup_revision = None
    active_pause = None

    def cleanup_before(expected, index):
        nonlocal revision, state, cleanup_revision
        # The first release/uncertain observation can change a ready/enabled
        # binding once. An enable after any cleanup contradicts owned resources.
        if (expected != revision + 1 or cleanup_revision is not None or index <= last_enable
                or (not state.enabled and state.observed_state == "unknown")):
            _invalid()
        revision += 1
        state = _BindingVersion(state.execution_epoch + int(state.enabled), state.config_ref, False, "unknown")
        versions[revision] = state
        cleanup_revision = revision

    for index, commit in enumerate(ordered):
        ledger._charge(rows=1, node_count=12)
        if commit.from_revision != revision:
            cleanup_before(commit.from_revision, index)
        if commit.kind == "cutover-pause":
            if (not state.enabled or state.observed_state != "ready" or state.config_ref is None
                    or commit.execution_epoch != state.execution_epoch):
                _invalid()
            state = _BindingVersion(state.execution_epoch, state.config_ref, False, "ready")
            active_pause = commit.operation_id
        elif commit.kind == "cutover-resume":
            if (cleanup_revision is not None or active_pause != commit.operation_id or state.enabled
                    or state.observed_state != "ready" or commit.execution_epoch != state.execution_epoch):
                _invalid()
            state = _BindingVersion(state.execution_epoch, state.config_ref, True, "ready")
            active_pause = None
        elif commit.kind == "enable":
            if (cleanup_revision is not None or state.enabled or state.observed_state not in {"unknown", "ready"}
                    or state.config_ref is None or commit.config_ref != state.config_ref):
                _invalid()
            state = _BindingVersion(state.execution_epoch + 1, state.config_ref, True, "ready")
            active_pause = None
        else:
            # Original fence is committed separately and always advances epoch.
            fenced = _BindingVersion(state.execution_epoch + 1, state.config_ref, False, "draining")
            versions[revision + 1] = fenced
            state = _BindingVersion(fenced.execution_epoch,
                commit.config_ref if commit.kind == "configure" else state.config_ref, False, "unknown")
            active_pause = None
        if commit.execution_epoch != state.execution_epoch:
            _invalid()
        revision = commit.to_revision
        versions[revision] = state
    expected = expected_revision
    if expected != revision:
        cleanup_before(expected, len(ordered))
    # All current resources have terminal release observations. If no earlier
    # cleanup changed B, these observations must leave this final B unchanged.
    if state.enabled or state.observed_state != "unknown":
        _invalid()
    if (execution_epoch != state.execution_epoch
            or configuration != state.config_ref):
        _invalid()
    return _BindingStepTimeline(revision, state.execution_epoch, cleanup_revision, MappingProxyType(versions))


_PREPARATION_LEASE_EVENTS = frozenset({"runtime_lease_renewed", "runtime_inflight_lease_renewed", "runtime_lease_rehydrated"})


def _renewal_history(prepared, operation_id, events, ledger, timeline):
    """Retain exact original lease events without granting a live lease."""
    ledger._charge(rows=len(events), node_count=len(events))
    renewals = [event for event in events if event["type"] in _PREPARATION_LEASE_EVENTS]
    if not renewals:
        return
    if type(timeline) is not _ControlTimeline or timeline.history.graph.preparation.operation_id != operation_id:
        _invalid()
    graph = timeline.history.graph
    owner = graph.preparation
    return _renewal_proof(prepared, owner, events, renewals, commits=timeline.history.commits,
        versions=timeline.versions, attempts=graph.receipt.context.attempts, ledger=ledger)


def _renewal_proof(prepared, owner, events, renewals, *, commits, versions, attempts, ledger):
    """Original historical lease proof, with explicit actual parent facts."""
    if type(prepared) is not _PreparationFacts or type(owner) is not _PreparedSource or type(ledger) is not _WorkLedger:
        _invalid()
    ledger._charge(rows=len(owner.resource_ids), node_count=len(versions) * 3 + len(commits) * 2)
    resources = [prepared.resources[identity] for identity in owner.resource_ids]
    if not resources:
        _invalid()
    succeeded = _one([event for event in events if event["type"] == "succeeded"])
    first_cleanup = min((event["sequence"] for event in events
        if event["type"] in {"resource_released", "resource_uncertain", "resource_intent_cancelled"}), default=0)
    configured_versions = set()
    for commit in commits.values():
        if commit.kind == "configure":
            configured_versions.update((commit.from_revision + 1, commit.to_revision))
    ready_epochs = {state.execution_epoch for state in versions.values()
        if state.enabled and state.observed_state == "ready"}
    ordinary_owned = any(state.observed_state == "ready" or
        (version in configured_versions and state.observed_state in {"unknown", "draining"})
        for version, state in versions.items())
    last_expiry = None
    for event in renewals:
        ledger._charge(rows=1, node_count=8)
        body = event["payload"]
        fields = {"generation", "expiresAt"}
        if event["type"] == "runtime_lease_rehydrated":
            fields.add("bindingRevision")
        else:
            fields.add("healthCheckedAt")
            if event["type"] == "runtime_inflight_lease_renewed":
                fields.update(("executionEpoch", "attemptId"))
        if (set(body) != fields or _fact_uuid(body["generation"]) != owner.generation
                or not succeeded["sequence"] < event["sequence"] < first_cleanup):
            _invalid()
        expiry = _scalar(body["expiresAt"], "timestamp with time zone!", ledger)
        if event["type"] == "runtime_lease_rehydrated":
            revision = body["bindingRevision"]
            if type(revision) is not int or not 1 <= revision < 2**63:
                _invalid()
            state = versions.get(revision)
            if state is None or not state.enabled or state.observed_state != "ready":
                _invalid()
        else:
            health = _scalar(body["healthCheckedAt"], "timestamp with time zone!", ledger)
            if expiry <= health:
                _invalid()
            if event["type"] == "runtime_lease_renewed":
                if not ordinary_owned:
                    _invalid()
            else:
                epoch = body["executionEpoch"]
                if type(epoch) is not int or epoch not in ready_epochs:
                    _invalid()
                attempt = attempts.get(_fact_uuid(body["attemptId"]))
                if (attempt is None or attempt["operation_kind"] != "recoverable_store"
                        or attempt["generation"] != owner.generation or attempt["execution_epoch"] != epoch):
                    _invalid()
        last_expiry = expiry
    # All three original writers atomically update the entire owned set.
    # A later cleanup changes its state but never rewrites the lease expiry.
    if any(resource["expires_at"] != last_expiry for resource in resources):
        _invalid()


def _preparation_terminal_history(prepared, ledger, *, timeline=None):
    """Classify retained preparation terminals using their original producers."""
    ledger._charge(rows=len(prepared.operations), node_count=len(prepared.operations))
    for operation_id, operation in prepared.operations.items():
        if operation["kind"] == "runtime-apply" and operation["status"] == "succeeded":
            events = sorted(prepared.events[operation_id], key=lambda event: event["sequence"])
            _renewal_history(prepared, operation_id, events, ledger, timeline)
    return _preparation_terminal_rows(prepared, ledger)


def _preparation_terminal_rows(prepared, ledger):
    """Original preparation terminal checks after the caller proves all renewals."""
    resource_kinds = {"resource_created", "resource_registered", "resource_uncertain", "resource_released", "resource_intent_cancelled"}
    resets = {event.from_revision: event for event in prepared.record.events
        if event.evidence is not None and event.evidence.type == "preparation_reset"}
    ledger._charge(rows=len(prepared.resources), node_count=len(prepared.preparations) * 2 + len(prepared.record.events))
    committed_operations = {item.operation_id for item in prepared.preparations}
    prepared_revisions = {item.installation_revision for item in prepared.preparations}
    resource_operations = {row["operation_id"] for row in prepared.resources.values()}
    approved_revisions = {event.to_revision for event in prepared.record.events if event.to_state == "approved"}
    natural = set()
    for operation_id, operation in prepared.operations.items():
        kind = operation["kind"]
        if kind not in {"runtime-apply", "runtime-verify"}:
            continue
        key = (kind, validate_idempotency_key(operation["idempotency_key"]))
        if key in natural or _HASH.fullmatch(operation["request_hash"]) is None or operation["expected_binding_revision"] is not None:
            _invalid()
        natural.add(key)
        events = sorted(prepared.events[operation_id], key=lambda event: event["sequence"])
        ledger._charge(rows=len(events), node_count=len(events) * 4)
        if kind == "runtime-verify" and operation["status"] == "succeeded":
            # The common verified graph already checks every successful proof.
            continue
        if kind == "runtime-apply" and operation["status"] == "succeeded":
            if operation["phase"] != "succeeded" or operation["failure_code"] is not None:
                _invalid()
            proof = _one([event for event in events if event["type"] == "preparation_committed"])
            checkpoints = [event for event in events if event["type"] not in resource_kinds | {"preparation_committed"} | _PREPARATION_LEASE_EVENTS]
            path = _PATHS[kind]
            if (operation_id not in committed_operations
                    or [event["type"] for event in checkpoints] != list(path)
                    or checkpoints[-2]["sequence"] + 1 != proof["sequence"]
                    or proof["sequence"] + 1 != checkpoints[-1]["sequence"]):
                _invalid()
        else:
            phase = operation["phase"]
            path = _PATHS[kind]
            allowed = {"accepted", "validating", "preparing", "registered"} if kind == "runtime-apply" else {"accepted", "validating"}
            if operation["status"] != "failed" or phase not in allowed:
                _invalid()
            terminal = events[-1]; body = terminal["payload"]
            if kind == "runtime-apply":
                if operation["expected_installation_etag"] not in approved_revisions:
                    _invalid()
                code = operation["failure_code"]
                if code in {"PREPARATION_VALIDATION_FAILED", "PREPARATION_EXECUTION_FAILED", "PREPARATION_STOPPED", "PREPARATION_EXPIRED"}:
                    if terminal["type"] != "preparation_failed" or body != {"phase": phase, "failureCode": code}:
                        _invalid()
                elif code == "RESOURCE_CLEANUP_UNCERTAIN":
                    if (terminal["type"] != "failed_preparation_settled" or body != {"phase": phase}
                            or operation_id not in resource_operations):
                        _invalid()
                else:
                    _invalid()
                checkpoints = [event for event in events[:-1] if event["type"] not in resource_kinds]
            else:
                if (operation["failure_code"] != "PREPARATION_OWNER_LOST" or terminal["type"] != "verification_abandoned"
                        or set(body) != {"phase", "installationRevision"} or body["phase"] != phase
                        or type(body["installationRevision"]) is not int):
                    _invalid()
                revision = body["installationRevision"]
                if (revision not in resets or operation["expected_installation_etag"] != revision
                        or revision not in prepared_revisions):
                    _invalid()
                checkpoints = events[:-1]
            path = path[:path.index(phase) + 1]
            if [event["type"] for event in checkpoints] != list(path):
                _invalid()
        if checkpoints[0]["payload"] != {"kind": kind}:
            _invalid()
        for index, event in enumerate(checkpoints[1:], 1):
            if event["payload"] != {"previousPhase": path[index - 1]}:
                _invalid()


@dataclass(frozen=True, slots=True)
class _PredecessorLeaseTerminalFacts:
    protocol: _PredecessorProtocolFacts
    timeline: _PredecessorBindingTimelineGraph
    renewal_operations: tuple


def _predecessor_lease_terminals(facts, protocol, timeline, *, scope, ledger):
    """Join real old protocol/control parents; never creates or recovers a lease."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(protocol) is not _PredecessorProtocolFacts or type(timeline) is not _PredecessorBindingTimelineGraph
            or protocol.partition is not facts.predecessors
            or timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    try:
        binding = protocol.verification.binding
        target = binding["installation_id"], binding["generation"]
        matching = tuple(row for row in timeline.controls.refreshes.lifecycle.bindings.values()
            if (row["installation_id"], row["generation"]) == target)
        if not matching or any(row != binding for row in matching):
            _invalid()
        history = timeline.controls.histories[target]; versions = timeline.timelines[target].versions
        owner = protocol.verification.preparation
        if timeline.controls.pending_preparations[target][0] != owner.operation_id:
            _invalid()
        prepared = protocol.verification.preparations; renewed = []
        ledger._charge(rows=len(prepared.operations), node_count=len(prepared.operations))
        for operation_id, operation in prepared.operations.items():
            if operation["kind"] != "runtime-apply" or operation["status"] != "succeeded":
                continue
            events = sorted(prepared.events[operation_id], key=lambda event: event["sequence"])
            ledger._charge(rows=len(events), node_count=len(events))
            renewals = tuple(event for event in events if event["type"] in _PREPARATION_LEASE_EVENTS)
            if renewals:
                if operation_id != owner.operation_id:
                    _invalid()
                _renewal_proof(prepared, owner, events, renewals, commits=history.commits,
                    versions=versions, attempts=protocol.context.attempts, ledger=ledger)
                renewed.append(operation_id)
        _preparation_terminal_rows(prepared, ledger)
        return _PredecessorLeaseTerminalFacts(protocol, timeline, tuple(renewed))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor lease terminal facts") from None


_NONDISPATCH_EMPTY = frozenset({
    "public.extension_operation_dispatch_binding", "public.extension_dispatch_cutover_operation",
    "public.extension_dispatch_lifecycle_operation", "public.automation_schedule_binding", "public.automation_occurrence",
    "public.automation_occurrence_dispatch_attempt", "public.automation_occurrence_outbox", "public.extension_dispatch_claim_gate",
    "public.extension_runtime_execution_attempt", "public.extension_runtime_execution_attempt_event",
    "public.extension_dispatch_cutover_receipt", "public.extension_dispatch_lifecycle_event",
    "public.extension_dispatch_lifecycle_receipt", "public.extension_dispatch_configuration_refresh_receipt",
    "public.extension_dispatch_successor_registration_receipt", "public.extension_event_control_dispatch_receipt",
    "public.extension_dispatch_cutover_event",
    "public.extension_dispatch_cutover_approval_refresh_receipt",
    "public.extension_dispatch_registration_receipt",
    "public.extension_dispatch_withdrawal_receipt",
    "public.ecommerce_growth_runtime_command_receipt",
})
_NONDISPATCH_LINKED = frozenset({
    "public.bundle_installation", "public.bundle_composition", "public.bundle_composition_lock",
    "public.bundle_installation_revision", "public.bundle_installation_event", "public.extension_runtime_binding",
    "public.extension_runtime_operation", "public.extension_runtime_dependency_ref", "public.extension_runtime_resource_lease",
    "public.extension_runtime_event", "public.extension_runtime_outbox", "public.extension_runtime_configuration",
    "public.extension_runtime_uninstall_receipt",
})


@dataclass(frozen=True, slots=True)
class _NondispatchSource:
    kind: str
    timeline: _ControlTimeline


def _nondispatch_runtime_source(facts, *, scope, source, locked_source, source_lock, ledger):
    """Classify fixed-projection terminal sources; never authorize execution."""
    if (type(facts) is not _DecodedFacts or any(facts.predecessors.values()) or _NONDISPATCH_EMPTY & _NONDISPATCH_LINKED
            or _NONDISPATCH_EMPTY | _NONDISPATCH_LINKED != set(_RELATIONS)):
        _invalid()
    for name in _NONDISPATCH_EMPTY:
        ledger._charge(node_count=1)
        if facts.relations[name]:
            _invalid()
    timeline = _control_timeline(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    history = timeline.history; graph = history.graph
    receipt = graph.receipt.receipt
    prepared = graph.receipt.context.notifications.preparation_facts
    try:
        _preparation_terminal_history(prepared, ledger, timeline=timeline)
    except (ValueError, TypeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid terminal facts") from None
    kind = receipt["retirement_kind"]
    ledger._charge(rows=len(history.commits), node_count=len(history.commits) * 5)
    enables = [commit for commit in history.commits.values() if commit.kind == "enable"]
    if kind == "never_enabled":
        if graph.configurations.current is not None or graph.configurations.versions or history.targets:
            _invalid()
    elif kind == "unconfigured_disabled":
        ledger._charge(rows=len(prepared.operations), node_count=len(prepared.operations))
        if (graph.configurations.current is not None or graph.configurations.versions
                or any(operation["kind"] in {"enable", "configure"} for operation in prepared.operations.values())):
            _invalid()
        disable = _one([commit for commit in history.commits.values() if commit.kind == "disable"
            and commit.to_revision == timeline.before_uninstall_revision
            and commit.execution_epoch == timeline.execution_epoch])
        if receipt["unactivated_disable_operation_id"] != disable.operation_id:
            _invalid()
    elif kind in {"configured_unactivated", "enabled_undispatched"}:
        if graph.configurations.current is None:
            _invalid()
        final_disable = [commit for commit in history.commits.values() if commit.kind == "disable"
            and commit.to_revision == timeline.before_uninstall_revision and commit.execution_epoch == timeline.execution_epoch]
        disable = _one(final_disable)
        column = "unactivated_disable_operation_id" if kind == "configured_unactivated" else "runtime_disable_operation_id"
        if receipt[column] != disable.operation_id:
            _invalid()
        if kind == "configured_unactivated":
            if enables:
                _invalid()
        else:
            # Original a0v021 counts the proofs matching the CURRENT config,
            # not unrelated successful enables for an older configuration.
            matches = [commit for commit in enables if commit.config_ref == graph.configurations.current
                and commit.to_revision < timeline.before_uninstall_revision and commit.execution_epoch < timeline.execution_epoch]
            if _one(matches).operation_id != receipt["runtime_enable_operation_id"]:
                _invalid()
    else:
        _invalid()
    return _NondispatchSource(kind, timeline)


def _read_legacy_content(conn, source_lock, ledger):
    """Execute the original SQL observation against the real connection context."""
    _require_transaction(conn)
    checked = _checked_lock(source_lock, ledger)
    payload = checked.payload.model_dump(mode="json", by_alias=True)
    _model_work(payload, ledger, 4)
    rows = conn.execute(_CONTENT_SOURCE_SQL,
        (UUID(checked.composition_id), checked.revision, checked.lock_hash)).fetchall()
    row = _one(rows)
    if (not isinstance(row, (Mapping, tuple)) or len(row) != 1
            or (isinstance(row, Mapping) and set(row) != {"eligible"})
            or _values(row, ("eligible",))[0] is not True):
        _invalid()


@dataclass(frozen=True, slots=True)
class _UnboundSource:
    kind: str
    context: _UninstallReceiptFacts


def _unbound_runtime_source(conn, facts, *, scope, source, locked_source, source_lock, ledger):
    """Classify explicit approved/content histories, never infer from B absence."""
    _require_transaction(conn)
    if (type(facts) is not _DecodedFacts or any(facts.predecessors.values())
            or _NONDISPATCH_EMPTY | _NONDISPATCH_LINKED != set(_RELATIONS)):
        _invalid()
    required_empty = _NONDISPATCH_EMPTY | {"public.extension_runtime_binding", "public.extension_runtime_configuration",
        "public.extension_runtime_uninstall_receipt", "public.extension_runtime_dependency_ref"}
    for name in required_empty:
        ledger._charge(node_count=1)
        if facts.relations[name]:
            _invalid()
    context = _read_uninstall_receipt(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    prepared = context.context.notifications.preparation_facts
    if context.context.binding is not None or context.receipt is not None:
        _invalid()
    prior_state = prepared.record.events[-1].from_state
    if prior_state == "approved":
        for operation in prepared.operations.values():
            ledger._charge(rows=1, node_count=2)
            if (operation["kind"] not in {"runtime-apply", "runtime-verify"}
                    or (operation["kind"] == "runtime-verify" and operation["status"] != "failed")):
                _invalid()
        try:
            _preparation_terminal_history(prepared, ledger)
        except (ValueError, TypeError, OverflowError, AssetRegistryError):
            raise ValueError("invalid terminal facts") from None
        return _UnboundSource("approved", context)
    if prior_state != "active":
        _invalid()
    ledger._charge(rows=len(prepared.contents), node_count=len(prepared.contents))
    if (any(item.manifest.spec.runtime is not None for item in prepared.contents)
            or prepared.operations or prepared.resources
            or facts.relations["public.extension_runtime_event"] or facts.relations["public.extension_runtime_outbox"]):
        _invalid()
    _read_legacy_content(conn, source_lock, ledger)
    return _UnboundSource("content", context)


def _snapshot9(value, group_id, ledger):
    """Validate the original main-group snapshot; separate groups stay separate."""
    fields = {"operationId", "handlerKind", "installationId", "generation", "executionEpoch", "operationFence",
              "revision", "cutoverGroupId", "cutoverGroupRevision"}
    if type(value) is not list or len(value) != len(ECOMMERCE_GROWTH_OPERATIONS):
        _invalid()
    ledger._charge(rows=len(value), node_count=len(value) * 12)
    operations = []
    for row in value:
        if (type(row) is not dict or set(row) != fields or type(row["operationId"]) is not str
                or type(row["handlerKind"]) is not str or row["handlerKind"] not in {"legacy", "extension"} or type(row["operationFence"]) is not bool
                or _fact_uuid(row["cutoverGroupId"]) != group_id
                or any(type(row[name]) is not int or not 1 <= row[name] < 2**63
                    for name in ("revision", "cutoverGroupRevision"))):
            _invalid()
        if row["handlerKind"] == "legacy":
            if any(row[name] is not None for name in ("installationId", "generation", "executionEpoch")):
                _invalid()
        else:
            _fact_uuid(row["installationId"]); _fact_uuid(row["generation"])
            if type(row["executionEpoch"]) is not int or not 1 <= row["executionEpoch"] < 2**63:
                _invalid()
        operations.append(row["operationId"])
    if operations != sorted(ECOMMERCE_GROWTH_OPERATIONS):
        _invalid()
    return tuple(MappingProxyType(row) for row in value)


@dataclass(frozen=True, slots=True)
class _CutoverPrepareGraph:
    request: object
    receipt: object
    old_snapshot: tuple
    new_snapshot: tuple


def _cutover_prepare_receipt(facts, operation, *, scope, ledger):
    """Original prepare provenance only; later phases and referenced parents remain required."""
    receipts = facts.relations["public.extension_dispatch_cutover_receipt"]
    events = facts.relations["public.extension_dispatch_cutover_event"]
    ledger._charge(rows=len(receipts) + len(events), node_count=32)
    try:
        identity = operation["cutover_operation_id"]
        row = _one([r for r in receipts if r["cutover_operation_id"] == identity and r["phase"] == "prepare"])
        event = _one([e for e in events if e["cutover_operation_id"] == identity and e["sequence"] == 1])
        if (any((r["org_id"], r["project_id"]) != scope.key for r in (operation, row, event))
                or operation["kind"] != "activate" or operation["parent_cutover_operation_id"] is not None
                or operation["parent_receipt_ref"] is not None
                or operation["failure_reason"] is not None
                or type(operation["requested_by"]) is not str or not operation["requested_by"]
                or operation["requested_by"] != operation["requested_by"].strip()
                or len(operation["requested_by"]) > 240):
            _invalid()
        body = row["authority_data"]
        _model_work(body, ledger, 12)
        fields = {"schemaVersion", "tenant", "cutoverOperationId", "status", "cutoverGroupId",
            "expectedGroupRevision", "targetGroupRevision", "targetInstallationId", "targetGeneration",
            "targetExecutionEpoch", "targetRuntimeRevision", "operationIds", "oldDispatchSnapshot",
            "newDispatchSnapshot", "checkpoint", "occurrenceWatermark", "pendingTargetReceiptRefs",
            "policyRef", "approvalRef", "requestHash", "requestedBy", "createdAt"}
        registration = body.get("registrationReceiptRef")
        if registration is not None:
            fields.add("registrationReceiptRef")
        if (type(body) is not dict or set(body) != fields
                or body["schemaVersion"] != "aos.ecommerce.dispatch-cutover-prepare/v1"
                or any(type(body[name]) is not int or not 1 <= body[name] < 2**63 for name in (
                    "expectedGroupRevision", "targetGroupRevision", "targetExecutionEpoch", "targetRuntimeRevision"))):
            _invalid()
        joined = dict(operation, receipt_id=row["receipt_id"], receipt_request_hash=row["request_hash"],
            authority_data=body, content_hash=row["content_hash"], receipt_created_at=row["created_at"])
        receipt = EcommerceGrowthCutoverStore._receipt(scope, joined, replayed=True)
        request = CutoverPrepareRequest(cutoverOperationId=receipt.cutover_operation_id,
            idempotencyKey=operation["idempotency_key"], cutoverGroupId=receipt.cutover_group_id,
            expectedGroupRevision=receipt.expected_group_revision, targetInstallationId=receipt.target_installation_id,
            targetGeneration=receipt.target_generation, targetExecutionEpoch=receipt.target_execution_epoch,
            targetRuntimeRevision=receipt.target_runtime_revision, policyRef=receipt.policy_ref,
            approvalRef=receipt.approval_ref, checkpoint=receipt.checkpoint,
            occurrenceWatermark=receipt.occurrence_watermark, pendingTargetReceiptRefs=receipt.pending_target_receipt_refs,
            registrationReceiptRef=receipt.registration_receipt_ref)
        wire = request.model_dump(mode="json", by_alias=True)
        if (request.request_hash() != operation["request_hash"]
                or any(body[key] != wire[key] for key in ("policyRef", "approvalRef", "pendingTargetReceiptRefs"))
                or (registration is not None and registration != wire["registrationReceiptRef"])):
            _invalid()
        old = _snapshot9(operation["old_dispatch_snapshot"], operation["cutover_group_id"], ledger)
        new = _snapshot9(operation["new_dispatch_snapshot"], operation["cutover_group_id"], ledger)
        # Also check body JSON types: equality alone equates False/0 and True/1.
        _snapshot9(body["oldDispatchSnapshot"], operation["cutover_group_id"], ledger)
        _snapshot9(body["newDispatchSnapshot"], operation["cutover_group_id"], ledger)
        if operation["target_group_revision"] != operation["expected_group_revision"] + 1:
            _invalid()
        for before, after in zip(old, new):
            if (before["handlerKind"] != "legacy" or before["operationFence"] is not (registration is not None)
                    or before["cutoverGroupRevision"] != operation["expected_group_revision"]
                    or (registration is not None and registration["resourceType"] == "FirstDispatchRegistrationReceipt"
                        and before["revision"] != 1)
                    or dict(after) != dict(before, handlerKind="extension", installationId=str(operation["target_installation_id"]),
                        generation=str(operation["target_generation"]), executionEpoch=operation["target_execution_epoch"],
                        operationFence=False, revision=before["revision"] + 1,
                        cutoverGroupRevision=operation["target_group_revision"])):
                _invalid()
        expected_event = dict(cutoverOperationId=str(identity), cutoverGroupId=str(operation["cutover_group_id"]),
            expectedGroupRevision=operation["expected_group_revision"], targetGroupRevision=operation["target_group_revision"],
            receiptId=str(row["receipt_id"]), contentHash=row["content_hash"])
        payload = event["payload"]
        _model_work(payload, ledger, 2)
        if (type(payload) is not dict or payload != expected_event
                or any(type(payload[name]) is not int for name in ("expectedGroupRevision", "targetGroupRevision"))
                or event["event_type"] != "CUTOVER_PREPARED"
                or canonical_sha256(payload) != event["payload_hash"]
                or event["occurred_at"] != row["created_at"]):
            _invalid()
        return _CutoverPrepareGraph(request, receipt, old, new)
    except (KeyError, TypeError, ValueError, EcommerceGrowthCutoverError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _CutoverForwardGraph:
    prepared: _CutoverPrepareGraph
    receipts: Mapping
    approval_refresh: object


def _cutover_approval_receipt(facts, operation, prepared, receipts, *, scope, ledger):
    """Original optional approval replacement, without issuer/current-permission claims."""
    rows = facts.relations["public.extension_dispatch_cutover_approval_refresh_receipt"]
    ledger._charge(rows=len(rows), node_count=4)
    matches = [r for r in rows if r["cutover_operation_id"] == operation["cutover_operation_id"]]
    if not matches:
        return None
    try:
        row = _one(matches)
        body = row["authority_data"]
        _model_work(body, ledger, 16)
        if ((row["org_id"], row["project_id"]) != scope.key
                or type(row["refreshed_by"]) is not str or not row["refreshed_by"]
                or row["refreshed_by"] != row["refreshed_by"].strip() or len(row["refreshed_by"]) > 240
                or row["created_at"] < prepared.receipt.created_at
                or ("resume" in receipts and row["created_at"] > receipts["resume"].created_at)):
            _invalid()
        receipt = EcommerceGrowthCutoverStore._approval_refresh_receipt(scope, dict(row), replayed=True)
        request = CutoverApprovalRefreshRequest(cutoverOperationId=operation["cutover_operation_id"],
            idempotencyKey=row["idempotency_key"], prepareReceiptRef=receipt.prepare_receipt_ref,
            approvalRef=receipt.new_approval_ref)
        parent = dict(resourceType="CutoverPrepareReceipt", resourceId=str(prepared.receipt.receipt_id),
            revision=1, contentHash=prepared.receipt.content_hash)
        old = prepared.receipt.approval_ref.model_dump(mode="json", by_alias=True)
        new = receipt.new_approval_ref.model_dump(mode="json", by_alias=True)
        expected = dict(schemaVersion="aos.ecommerce.dispatch-cutover-approval-refresh/v1",
            tenant=dict(orgId=scope.org_id, projectId=scope.project_id), receiptId=str(row["receipt_id"]),
            cutoverOperationId=str(operation["cutover_operation_id"]), status="approval_refreshed",
            prepareReceiptRef=parent, oldApprovalRef=old, newApprovalRef=new,
            requestHash=request.request_hash(), refreshedBy=row["refreshed_by"], createdAt=row["created_at"].isoformat())
        if (receipt.new_approval_ref == prepared.receipt.approval_ref or request.request_hash() != row["request_hash"]
                or canonical_sha256(body) != canonical_sha256(expected)
                or any(canonical_sha256(row[name]) != canonical_sha256(value) for name, value in (
                    ("prepare_receipt_ref", parent), ("old_approval_ref", old), ("new_approval_ref", new)))):
            _invalid()
        return receipt
    except (KeyError, TypeError, ValueError, EcommerceGrowthCutoverError):
        _invalid()


def _cutover_execution_snapshot(body, ledger):
    """Validate original permanent snapshot shapes; live row provenance is separate."""
    shapes = {
        "claimedOccurrences": {"occurrenceId": "uuid!", "claimOwner": "text!", "claimUntil": "timestamp with time zone!"},
        "claimedAttempts": {"attemptId": "uuid!", "occurrenceId": "uuid!", "targetIdempotencyKey": "text!",
            "claimOwner": "text!", "claimUntil": "timestamp with time zone!"},
        "unknownAttempts": {"attemptId": "uuid!", "occurrenceId": "uuid!", "targetIdempotencyKey": "text!",
            "resolvedAt": "timestamp with time zone!"},
        "runningRuntimeAttempts": {"attemptId": "uuid!", "operationKey": "text!", "idempotencyKey": "text!",
            "acceptedAt": "timestamp with time zone!", "leaseUntil": "timestamp with time zone!"},
    }
    watermark = _scalar(body["occurrenceWatermark"], "timestamp with time zone?", ledger)
    if watermark is not None and watermark.isoformat() != body["occurrenceWatermark"]:
        _invalid()
    result = {"occurrenceWatermark": body["occurrenceWatermark"]}
    for name, fields in shapes.items():
        rows = body[name]
        if type(rows) is not list:
            _invalid()
        ledger._charge(rows=len(rows), node_count=len(rows))
        identities = []
        for row in rows:
            if type(row) is not dict or set(row) != set(fields):
                _invalid()
            for key, descriptor in fields.items():
                parsed = _scalar(row[key], descriptor, ledger)
                if descriptor == "timestamp with time zone!" and parsed.isoformat() != row[key]:
                    _invalid()
            identities.append(row["occurrenceId" if name == "claimedOccurrences" else "attemptId"])
        if identities != sorted(set(identities)):
            _invalid()
        result[name] = rows
    return result


def _cutover_forward_receipts(facts, operation, *, scope, ledger):
    """Verify each stored forward prefix; not a complete cutover/failure graph."""
    prepared = _cutover_prepare_receipt(facts, operation, scope=scope, ledger=ledger)
    phases = ("pause", "commit", "validate", "resume")
    types = ("CUTOVER_CLAIMS_PAUSED", "CUTOVER_COMMITTED", "CUTOVER_VALIDATED", "CUTOVER_RESUMED")
    all_rows = facts.relations["public.extension_dispatch_cutover_receipt"]
    all_events = facts.relations["public.extension_dispatch_cutover_event"]
    ledger._charge(rows=len(all_rows) + len(all_events), node_count=32)
    identity = operation["cutover_operation_id"]
    rows = [r for r in all_rows if r["cutover_operation_id"] == identity and r["phase"] in phases]
    events = [e for e in all_events if e["cutover_operation_id"] == identity and 2 <= e["sequence"] <= 5]
    count = len(rows)
    if count > len(phases) or len(events) != count or {r["phase"] for r in rows} != set(phases[:count]):
        _invalid()
    receipts = {}
    previous_time = prepared.receipt.created_at
    try:
        for offset, phase in enumerate(phases[:count], 2):
            row = _one([r for r in rows if r["phase"] == phase])
            event = _one([e for e in events if e["sequence"] == offset])
            if (any((r["org_id"], r["project_id"]) != scope.key for r in (row, event))
                    or event["event_type"] != types[offset - 2] or row["created_at"] < previous_time):
                _invalid()
            body = row["authority_data"]
            _model_work(body, ledger, 16)
            if (type(body) is not dict or type(body.get("requestedBy")) is not str
                    or not body["requestedBy"] or body["requestedBy"] != body["requestedBy"].strip()
                    or len(body["requestedBy"]) > 240 or type(body.get("claimPaused")) is not bool):
                _invalid()
            snapshot = _cutover_execution_snapshot(body, ledger)
            _snapshot9(body["dispatchSnapshot"], operation["cutover_group_id"], ledger)
            if phase in {"commit", "validate"} and (prepared.receipt.pending_target_receipt_refs
                    or any(snapshot[n] for n in ("claimedOccurrences", "claimedAttempts", "runningRuntimeAttempts"))):
                _invalid()
            joined = dict(operation)
            joined.update(row)
            joined.update(event_payload=event["payload"], payload_hash=event["payload_hash"], occurred_at=event["occurred_at"])
            if phase in {"pause", "commit"}:
                parent = prepared.receipt
                parent_ref = dict(resourceType="CutoverPrepareReceipt", resourceId=str(parent.receipt_id), revision=1, contentHash=parent.content_hash)
                request = CutoverCommitRequest(cutoverOperationId=identity,
                    idempotencyKey=body["commitIdempotencyKey"], prepareReceiptRef=body["prepareReceiptRef"])
                if (request.prepare_receipt_ref.model_dump(mode="json", by_alias=True) != parent_ref
                        or (phase == "commit" and row["request_hash"] != receipts["pause"].request_hash)):
                    _invalid()
                expected = EcommerceGrowthCutoverStore._phase_authority(scope, request, prepared.receipt,
                    phase=phase, status="draining" if phase == "pause" else "committed",
                    dispatch_snapshot=list(prepared.receipt.old_dispatch_snapshot if phase == "pause" else prepared.receipt.new_dispatch_snapshot),
                    facts=snapshot, actor=body["requestedBy"], created_at=row["created_at"])
                receipt = EcommerceGrowthCutoverStore._phase_receipt(scope, joined, replayed=True)
            else:
                if type(body.get("targetRuntimeRevision")) is not int:
                    _invalid()
                parent = receipts["commit"]
                parent_ref = dict(resourceType="CutoverCommitReceipt", resourceId=str(parent.receipt_id), revision=1, contentHash=parent.content_hash)
                request = CutoverFinalizeRequest(cutoverOperationId=identity,
                    idempotencyKey=body["finalizeIdempotencyKey"], commitReceiptRef=body["commitReceiptRef"])
                if request.commit_receipt_ref.model_dump(mode="json", by_alias=True) != parent_ref:
                    _invalid()
                expected = EcommerceGrowthCutoverStore._finalize_authority(scope, request, prepared.receipt,
                    phase=phase, status="validated" if phase == "validate" else "resumed",
                    runtime_revision=operation["target_runtime_revision"] + (1 if phase == "validate" else 2),
                    claim_paused=phase != "resume", facts=snapshot, actor=body["requestedBy"], created_at=row["created_at"])
                receipt = EcommerceGrowthCutoverStore._finalize_receipt(scope, joined, replayed=True)
            if (request.request_hash() != row["request_hash"]
                    or canonical_sha256(body) != canonical_sha256(expected)):
                _invalid()
            receipts[phase] = receipt
            previous_time = row["created_at"]
        approval = _cutover_approval_receipt(facts, operation, prepared, receipts, scope=scope, ledger=ledger)
        return _CutoverForwardGraph(prepared, MappingProxyType(receipts), approval)
    except (KeyError, TypeError, ValueError, EcommerceGrowthCutoverError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _CutoverRollbackGraph:
    parent: _CutoverForwardGraph
    request: object
    receipts: Mapping


def _cutover_rollback_receipts(facts, operation, *, scope, ledger):
    """Original independent rollback history, without current dispatch or B admission."""
    operations = facts.relations["public.extension_dispatch_cutover_operation"]
    all_rows = facts.relations["public.extension_dispatch_cutover_receipt"]
    all_events = facts.relations["public.extension_dispatch_cutover_event"]
    ledger._charge(rows=len(operations) + len(all_rows) + len(all_events), node_count=32)
    try:
        if (operation["kind"] != "rollback" or (operation["org_id"], operation["project_id"]) != scope.key
                or type(operation["requested_by"]) is not str or not operation["requested_by"]
                or operation["requested_by"] != operation["requested_by"].strip() or len(operation["requested_by"]) > 240):
            _invalid()
        parent_row = _one([p for p in operations if p["cutover_operation_id"] == operation["parent_cutover_operation_id"]])
        parent = _cutover_forward_receipts(facts, parent_row, scope=scope, ledger=ledger)
        if ("commit" not in parent.receipts or "resume" in parent.receipts
                or parent_row["status"] != ("validated" if "validate" in parent.receipts else "committed")):
            _invalid()
        prepare = parent.prepared.receipt
        commit = parent.receipts["commit"]
        commit_ref = dict(resourceType="CutoverCommitReceipt", resourceId=str(commit.receipt_id), revision=1, contentHash=commit.content_hash)
        basis = dict(rollbackOperationId=str(operation["cutover_operation_id"]), idempotencyKey=operation["idempotency_key"],
            activationOperationId=str(parent_row["cutover_operation_id"]), commitReceiptRef=operation["parent_receipt_ref"],
            approvalRef=operation["approval_ref"], failureReason=operation["failure_reason"])
        _model_work(basis, ledger, 6)
        request = CutoverRollbackRequest.model_validate(basis)
        if (request.request_hash() != operation["request_hash"]
                or canonical_sha256(operation["parent_receipt_ref"]) != canonical_sha256(commit_ref)
                or canonical_sha256(basis) != canonical_sha256(request.model_dump(mode="json", by_alias=True))
                or any(operation[n] != parent_row[n] for n in ("cutover_group_id", "target_installation_id", "target_generation",
                    "target_execution_epoch", "target_runtime_revision", "occurrence_watermark"))
                or operation["expected_group_revision"] != parent_row["target_group_revision"]
                or operation["target_group_revision"] != parent_row["target_group_revision"] + 1
                or operation["pending_target_receipt_refs"] != []):
            _invalid()
        for name in ("operation_ids", "checkpoint", "policy_ref"):
            _model_work(operation[name], ledger, 3)
            _model_work(parent_row[name], ledger, 3)
            if canonical_sha256(operation[name]) != canonical_sha256(parent_row[name]):
                _invalid()
        old = _snapshot9(operation["old_dispatch_snapshot"], operation["cutover_group_id"], ledger)
        fenced = _snapshot9(operation["new_dispatch_snapshot"], operation["cutover_group_id"], ledger)
        if list(map(dict, old)) != list(map(dict, parent.prepared.new_snapshot)):
            _invalid()
        for before, after in zip(old, fenced):
            if dict(after) != dict(before, operationFence=True, revision=before["revision"] + 1,
                    cutoverGroupRevision=operation["target_group_revision"]):
                _invalid()
        restored = [dict(item, revision=item["revision"] + 3, cutoverGroupRevision=item["cutoverGroupRevision"] + 3)
            for item in parent.prepared.old_snapshot]
        _snapshot9(restored, operation["cutover_group_id"], ledger)
        identity = operation["cutover_operation_id"]
        rows = [r for r in all_rows if r["cutover_operation_id"] == identity]
        events = [e for e in all_events if e["cutover_operation_id"] == identity]
        phases = ("fence",) if operation["status"] == "draining" else ("fence", "drain", "rollback")
        if (operation["status"] not in {"draining", "rolled_back"} or len(rows) != len(phases)
                or {r["phase"] for r in rows} != set(phases) or len(events) != len(phases)):
            _invalid()
        receipts = {}; snapshots = {}; times = {}
        parent_times = [r.created_at for r in parent.receipts.values()]
        if parent.approval_refresh is not None:
            parent_times.append(parent.approval_refresh.created_at)
        previous_time = max(parent_times)
        for sequence, phase in enumerate(phases, 1):
            row = _one([r for r in rows if r["phase"] == phase])
            event = _one([e for e in events if e["sequence"] == sequence])
            if (any((r["org_id"], r["project_id"]) != scope.key for r in (row, event))
                    or row["created_at"] < previous_time or (phase == "fence" and row["created_at"] != operation["created_at"])
                    or event["event_type"] != {"fence": "CUTOVER_FENCED", "drain": "CUTOVER_DRAINED", "rollback": "CUTOVER_ROLLED_BACK"}[phase]
                    or row["request_hash"] != operation["request_hash"]):
                _invalid()
            body = row["authority_data"]
            _model_work(body, ledger, 16)
            snapshot = _cutover_execution_snapshot(body, ledger)
            _snapshot9(body["dispatchSnapshot"], operation["cutover_group_id"], ledger)
            if phase != "fence" and any(snapshot[n] for n in ("claimedOccurrences", "claimedAttempts", "runningRuntimeAttempts")):
                _invalid()
            drain_row = _one([r for r in rows if r["phase"] == "drain"]) if len(phases) == 3 else None
            drain_ref = (CutoverExactRef(resourceType="CutoverDrainReceipt", resourceId=str(drain_row["receipt_id"]),
                revision=1, contentHash=drain_row["content_hash"]) if phase == "rollback" else None)
            expected = EcommerceGrowthCutoverStore._rollback_authority(scope, request, prepare, phase=phase,
                status="rolled_back" if phase == "rollback" else "draining",
                dispatch_snapshot=restored if phase == "rollback" else list(map(dict, fenced)),
                facts=snapshot, actor=operation["requested_by"], created_at=row["created_at"], drain_receipt_ref=drain_ref)
            joined = dict(operation)
            joined.update(row)
            joined.update(parent_old_dispatch_snapshot=parent_row["old_dispatch_snapshot"],
                event_payload=event["payload"], payload_hash=event["payload_hash"], occurred_at=event["occurred_at"],
                drain_receipt_id=None if drain_row is None else drain_row["receipt_id"],
                drain_content_hash=None if drain_row is None else drain_row["content_hash"])
            receipt = EcommerceGrowthCutoverStore._rollback_receipt(scope, joined, replayed=True)
            if canonical_sha256(body) != canonical_sha256(expected):
                _invalid()
            if phase == "rollback" and (row["created_at"] != times["drain"]
                    or canonical_sha256(snapshot) != canonical_sha256(snapshots["drain"])):
                _invalid()
            receipts[phase] = receipt; snapshots[phase] = snapshot; times[phase] = row["created_at"]
            previous_time = row["created_at"]
        return _CutoverRollbackGraph(parent, request, MappingProxyType(receipts))
    except (KeyError, TypeError, ValueError, EcommerceGrowthCutoverError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _CutoverHistoryGraph:
    activations: Mapping
    rollbacks: Mapping
    rollback_by_parent: Mapping


_CUTOVER_FAMILIES = (
    "public.extension_dispatch_cutover_operation", "public.extension_dispatch_cutover_receipt",
    "public.extension_dispatch_cutover_event", "public.extension_dispatch_cutover_approval_refresh_receipt",
)


@dataclass(frozen=True, slots=True)
class _CutoverFactView:
    relations: Mapping


def _cutover_history(facts, *, scope, source, ledger):
    """Current terminal source wrapper; old installations use their actual UUID below."""
    if type(facts) is not _DecodedFacts or type(scope) is not TenantScope or type(source) is not ReinstallSourceRef:
        _invalid()
    return _cutover_history_for_installation(facts, scope=scope,
        installation_id=_fact_uuid(source.installation_id), ledger=ledger)


def _cutover_history_for_installation(facts, *, scope, installation_id, ledger):
    """One original C history kernel; no assumption about installation terminal state."""
    if (type(facts) not in (_DecodedFacts, _CutoverFactView) or type(scope) is not TenantScope
            or type(installation_id) is not UUID or type(ledger) is not _WorkLedger):
        _invalid()
    if type(facts) is _CutoverFactView and set(facts.relations) != set(_CUTOVER_FAMILIES):
        _invalid()
    target = installation_id
    operations = facts.relations["public.extension_dispatch_cutover_operation"]
    events = facts.relations["public.extension_dispatch_cutover_event"]
    rows = facts.relations["public.extension_dispatch_cutover_receipt"]
    approvals = facts.relations["public.extension_dispatch_cutover_approval_refresh_receipt"]
    ledger._charge(rows=len(operations) + len(events) + len(rows) + len(approvals),
        node_count=4 * (len(operations) + len(events) + len(rows) + len(approvals)))
    by_id = {}; operation_keys = set(); children = {}
    for operation in operations:
        if ((operation["org_id"], operation["project_id"]) != scope.key
                or operation["target_installation_id"] != target
                or operation["kind"] not in {"activate", "rollback"}
                or operation["idempotency_key"] in operation_keys):
            _invalid()
        by_id[operation["cutover_operation_id"]] = operation
        operation_keys.add(operation["idempotency_key"])
    # Wire PK validation is not a substitute for each original UNIQUE/FK.
    event_ids = set(); phase_keys = set(); approval_ops = set(); approval_keys = set()
    op_rows = {identity: [] for identity in by_id}
    op_events = {identity: [] for identity in by_id}
    for family, records in (("event", events), ("receipt", rows), ("approval", approvals)):
        for row in records:
            identity = row["cutover_operation_id"]
            if (identity not in by_id or (row["org_id"], row["project_id"]) != scope.key):
                _invalid()
            if family == "event":
                if row["event_id"] in event_ids:
                    _invalid()
                event_ids.add(row["event_id"]); op_events[identity].append(row)
            elif family == "receipt":
                key = (identity, row["phase"])
                if key in phase_keys:
                    _invalid()
                phase_keys.add(key); op_rows[identity].append(row)
            else:
                if (by_id[identity]["kind"] != "activate" or identity in approval_ops
                        or row["idempotency_key"] in approval_keys):
                    _invalid()
                approval_ops.add(identity); approval_keys.add(row["idempotency_key"])
    for operation in operations:
        if operation["kind"] == "rollback":
            parent = operation["parent_cutover_operation_id"]
            if parent not in by_id or by_id[parent]["kind"] != "activate" or parent in children:
                _invalid()
            children[parent] = operation["cutover_operation_id"]
    states = {"prepared": (), "draining": ("pause",), "committed": ("pause", "commit"),
        "validated": ("pause", "commit", "validate"), "resumed": ("pause", "commit", "validate", "resume")}
    activations = {}; rollbacks = {}
    for identity, operation in by_id.items():
        if operation["kind"] != "activate":
            continue
        # Reserved/unknown states remain in the input, but cannot qualify here.
        if operation["status"] not in states:
            _invalid()
        graph = _cutover_forward_receipts(facts, operation, scope=scope, ledger=ledger)
        expected = states[operation["status"]]
        if (tuple(graph.receipts) != expected
                or {r["phase"] for r in op_rows[identity]} != {"prepare", *expected}
                or len(op_rows[identity]) != len(expected) + 1
                or {e["sequence"] for e in op_events[identity]} != set(range(1, len(expected) + 2))
                or len(op_events[identity]) != len(expected) + 1):
            _invalid()
        activations[identity] = graph
    for identity, operation in by_id.items():
        if operation["kind"] == "rollback":
            rollbacks[identity] = _cutover_rollback_receipts(facts, operation, scope=scope, ledger=ledger)
    if len(activations) + len(rollbacks) != len(operations):
        _invalid()
    return _CutoverHistoryGraph(MappingProxyType(activations), MappingProxyType(rollbacks), MappingProxyType(children))


@dataclass(frozen=True, slots=True)
class _PredecessorCutoverGraph:
    histories: Mapping
    operation_installations: Mapping
    partition: Mapping


def _predecessor_cutover_history(facts, *, scope, ledger):
    """Resolve all native old C roots; old L/B/drain obligations remain separate."""
    _check_predecessor_scope(facts, scope, ledger)
    partition = facts.predecessors
    ledger._charge(rows=sum(len(partition[name]) for name in _CUTOVER_FAMILIES), node_count=16)
    installations = {}; keys = set(); groups = {}
    for row in partition[_CUTOVER_FAMILIES[0]]:
        identity = row["cutover_operation_id"]; installation = row["target_installation_id"]
        if identity in installations or row["idempotency_key"] in keys:
            _invalid()
        keys.add(row["idempotency_key"]); installations[identity] = installation
        if installation not in groups:
            ledger._charge(node_count=8)
            groups[installation] = {name: [] for name in _CUTOVER_FAMILIES}
        groups[installation][_CUTOVER_FAMILIES[0]].append(row)
    event_ids = set(); approval_keys = set()
    for name in _CUTOVER_FAMILIES[1:]:
        for row in partition[name]:
            ledger._charge(rows=1, node_count=8)
            installation = installations.get(row["cutover_operation_id"])
            if installation is None:
                _invalid()
            if name == "public.extension_dispatch_cutover_event":
                if row["event_id"] in event_ids:
                    _invalid()
                event_ids.add(row["event_id"])
            elif name == "public.extension_dispatch_cutover_approval_refresh_receipt":
                if row["idempotency_key"] in approval_keys:
                    _invalid()
                approval_keys.add(row["idempotency_key"])
            groups[installation][name].append(row)
    histories = {}
    for installation, rows in groups.items():
        ledger._charge(node_count=8)
        view = _CutoverFactView(MappingProxyType({name: tuple(records) for name, records in rows.items()}))
        histories[installation] = _cutover_history_for_installation(view, scope=scope, installation_id=installation, ledger=ledger)
    return _PredecessorCutoverGraph(MappingProxyType(histories), MappingProxyType(installations), partition)


@dataclass(frozen=True, slots=True)
class _RefreshReceiptStep:
    row: Mapping
    request: DispatchConfigurationRefreshRequest
    decoded: Mapping


@dataclass(frozen=True, slots=True)
class _RefreshReceiptChain:
    root: _CutoverForwardGraph
    steps: tuple
    authority_ref: Mapping
    configuration: ConfigurationRef | None
    runtime_revision: int
    execution_epoch: int
    group_revision: int
    dispatch_snapshot: tuple


def _refresh_receipt_chain(rows, root, *, scope, ledger):
    """Original immutable receipt chain; actual control and installation proof is separate."""
    if (type(root) is not _CutoverForwardGraph or type(scope) is not TenantScope
            or type(ledger) is not _WorkLedger or type(rows) not in (tuple, list)
            or "resume" not in root.receipts):
        _invalid()
    try:
        prepare = root.prepared.receipt; resume = root.receipts["resume"]
        authority = dict(resourceType="CutoverResumeReceipt", resourceId=str(resume.receipt_id),
            revision=1, contentHash=resume.content_hash)
        runtime = resume.target_runtime_revision; epoch = prepare.target_execution_epoch
        group = prepare.target_group_revision; configuration = None; previous_time = resume.created_at
        snapshot = list(map(dict, root.prepared.new_snapshot)); steps = []; ids = set(); keys = set()
        ledger._charge(rows=len(rows), node_count=8 * len(rows))
        for revision, row in enumerate(sorted(rows, key=lambda r: r["revision"]), 1):
            if ((row["org_id"], row["project_id"]) != scope.key
                    or row["revision"] != revision or row["activation_operation_id"] != prepare.cutover_operation_id
                    or row["activation_resume_receipt_id"] != resume.receipt_id
                    or row["installation_id"] != prepare.target_installation_id
                    or row["generation"] != prepare.target_generation or row["cutover_group_id"] != prepare.cutover_group_id
                    or row["created_at"] < previous_time or row["receipt_id"] in ids
                    or row["idempotency_key"] in keys):
                _invalid()
            _model_work(row["request"], ledger, 12); _model_work(row["body"], ledger, 12)
            decoded = _decode_dispatch_refresh_receipt(dict(row))
            request = DispatchConfigurationRefreshRequest.model_validate_json(json.dumps(decoded["request"], allow_nan=False))
            wire = request.wire()
            if (canonical_sha256(row["request"]) != row["request_hash"] or canonical_sha256(row["body"]) != row["content_hash"]
                    or canonical_sha256(wire["sourceAuthorityRef"]) != canonical_sha256(authority)
                    or request.source_runtime_revision != runtime or request.source_execution_epoch != epoch
                    or request.expected_group_revision != group
                    or (configuration is not None and request.source_configuration_ref != configuration)):
                _invalid()
            snapshot = [dict(item, executionEpoch=request.target_execution_epoch,
                revision=item["revision"] + 1, cutoverGroupRevision=group + 1) for item in snapshot]
            _snapshot9(snapshot, prepare.cutover_group_id, ledger)
            steps.append(_RefreshReceiptStep(row, request, MappingProxyType(decoded)))
            ids.add(row["receipt_id"]); keys.add(row["idempotency_key"])
            authority = decoded["ref"]; configuration = request.target_configuration_ref
            runtime = request.target_runtime_revision; epoch = request.target_execution_epoch
            group += 1; previous_time = row["created_at"]
        return _RefreshReceiptChain(root, tuple(steps), MappingProxyType(authority), configuration,
            runtime, epoch, group, tuple(MappingProxyType(item) for item in snapshot))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _PrimaryRefreshGraph:
    authority_ref: Mapping
    configuration: ConfigurationRef
    runtime_revision: int
    execution_epoch: int
    group_revision: int
    dispatch_snapshot: tuple
    receipt_ids: tuple
    remaining_receipt_ids: tuple


def _installed_revision_ref(installation_id, installation_revision, installation_rows, ledger):
    """Original current-refresh persisted installation reference construction."""
    ledger._charge(rows=len(installation_rows), node_count=8)
    installed = _one([r for r in installation_rows if r["revision"] == installation_revision])
    return dict(installationId=installation_id, revision=installed["revision"],
        lockHash=installed["lock_hash"], overlayRevision=installed["overlay_revision"])


def _primary_refresh_history(facts, cutovers, controls, *, activation_id, scope, source, ledger):
    """Continue one verified resumed root; other groups remain explicitly unconsumed."""
    if (type(cutovers) is not _CutoverHistoryGraph or type(controls) is not _ControlHistory
            or type(activation_id) is not UUID or type(scope) is not TenantScope):
        _invalid()
    try:
        root = cutovers.activations.get(activation_id)
        if root is None or "resume" not in root.receipts:
            _invalid()
        prepare = root.prepared.receipt; resume = root.receipts["resume"]
        binding = controls.graph.receipt.context.binding
        if (prepare.target_installation_id != UUID(source.installation_id)
                or prepare.target_generation != binding["generation"]):
            _invalid()
        enabled = [c for c in controls.commits.values() if c.kind == "enable"
            and c.to_revision == prepare.target_runtime_revision and c.execution_epoch == prepare.target_execution_epoch]
        ledger._charge(rows=len(controls.commits), node_count=12)
        initial = _one(enabled)
        configuration = initial.config_ref
        if configuration is None:
            _invalid()
        versions = controls.graph.configurations.versions
        if versions.get((UUID(configuration.configurationId), configuration.revision), (None,))[0] != configuration:
            _invalid()
        runtime = resume.target_runtime_revision; epoch = prepare.target_execution_epoch
        group = prepare.target_group_revision
        authority = dict(resourceType="CutoverResumeReceipt", resourceId=str(resume.receipt_id), revision=1, contentHash=resume.content_hash)
        snapshot = list(map(dict, root.prepared.new_snapshot))
        installation_ref = _installed_revision_ref(source.installation_id, binding["installation_revision"],
            facts.relations["public.bundle_installation_revision"], ledger)
        all_rows = facts.relations["public.extension_dispatch_configuration_refresh_receipt"]
        ledger._charge(rows=len(all_rows), node_count=8 * len(all_rows))
        receipt_ids = set(); natural = set(); selected = []; remaining = []
        for row in all_rows:
            key = (row["cutover_group_id"], row["idempotency_key"])
            if ((row["org_id"], row["project_id"]) != scope.key or row["installation_id"] != binding["installation_id"]
                    or row["receipt_id"] in receipt_ids or key in natural):
                _invalid()
            receipt_ids.add(row["receipt_id"]); natural.add(key)
            if row["cutover_group_id"] == prepare.cutover_group_id:
                selected.append(row)
            else:
                remaining.append(row["receipt_id"])
        chain = _refresh_receipt_chain(selected, root, scope=scope, ledger=ledger)
        steps = {step.row["receipt_id"]: step for step in chain.steps}
        operations = controls.graph.receipt.context.notifications.preparation_facts.operations
        used = []; previous_time = resume.created_at
        for revision, row in enumerate(sorted(selected, key=lambda r: r["revision"]), 1):
            if (row["revision"] != revision or row["activation_operation_id"] != activation_id
                    or row["activation_resume_receipt_id"] != resume.receipt_id
                    or row["generation"] != prepare.target_generation or row["created_at"] < previous_time):
                _invalid()
            step = steps[row["receipt_id"]]; decoded = step.decoded; request = step.request
            wire = request.wire()
            if (canonical_sha256(row["request"]) != row["request_hash"] or canonical_sha256(row["body"]) != row["content_hash"]
                    or canonical_sha256(wire["sourceAuthorityRef"]) != canonical_sha256(authority)
                    or wire["installationRef"] != installation_ref
                    or request.source_runtime_revision != runtime or request.source_execution_epoch != epoch
                    or request.source_configuration_ref != configuration or request.expected_group_revision != group):
                _invalid()
            target = request.target_configuration_ref
            if versions.get((UUID(target.configurationId), target.revision), (None,))[0] != target:
                _invalid()
            configure_id = UUID(request.configure_operation_id); enable_id = UUID(request.enable_operation_id)
            configure = controls.commits.get(configure_id); enable = controls.commits.get(enable_id)
            if (configure is None or enable is None or configure.kind != "configure" or enable.kind != "enable"
                    or configure.from_revision != runtime or configure.to_revision != runtime + 2
                    or enable.from_revision != configure.to_revision or enable.to_revision != request.target_runtime_revision
                    or configure.execution_epoch != epoch + 1 or enable.execution_epoch != epoch + 2
                    or enable.execution_epoch != request.target_execution_epoch
                    or configure.config_ref != target or enable.config_ref != target
                    or operations[configure_id]["revision"] != request.configure_operation_revision
                    or operations[enable_id]["revision"] != request.enable_operation_revision
                    or operations[configure_id]["requested_by"] != row["actor"]
                    or operations[enable_id]["requested_by"] != row["actor"]):
                _invalid()
            snapshot = [dict(item, executionEpoch=request.target_execution_epoch,
                revision=item["revision"] + 1, cutoverGroupRevision=group + 1) for item in snapshot]
            _snapshot9(snapshot, prepare.cutover_group_id, ledger)
            authority = decoded["ref"]; configuration = target
            runtime = request.target_runtime_revision; epoch = request.target_execution_epoch; group += 1
            previous_time = row["created_at"]; used.append(row["receipt_id"])
        return _PrimaryRefreshGraph(MappingProxyType(authority), configuration, runtime, epoch, group,
            tuple(MappingProxyType(item) for item in snapshot), tuple(used), tuple(sorted(remaining)))
    except (KeyError, TypeError, ValueError, AttributeError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _LifecycleReceiptPair:
    fence: object
    detach: object


def _lifecycle_receipt_pair(receipts, events, *, scope, runtime, activation, lifecycle, fenced, detached, ledger):
    """One original L receipt kernel, independent of any installation terminal record."""
    if type(scope) is not TenantScope or type(ledger) is not _WorkLedger:
        _invalid()
    try:
        ledger._charge(rows=len(receipts) + len(events) + 3, node_count=24)
        for row in (runtime, activation, lifecycle, *receipts, *events):
            if (row["org_id"], row["project_id"]) != scope.key:
                _invalid()
        group_id = lifecycle["cutover_group_id"]
        expected_operations = sorted(ECOMMERCE_GROWTH_OPERATIONS)
        if (runtime["operation_id"] != lifecycle["runtime_operation_id"]
                or activation["cutover_operation_id"] != lifecycle["activation_operation_id"]
                or runtime["installation_id"] != activation["target_installation_id"]
                or activation["cutover_group_id"] != group_id or lifecycle["status"] != "detached"
                or lifecycle["requested_by"] != runtime["requested_by"]
                or activation["operation_ids"] != expected_operations or lifecycle["operation_ids"] != expected_operations):
            _invalid()
        request_basis = dict(runtimeOperationId=str(runtime["operation_id"]), runtimeRequestHash=runtime["request_hash"],
            activationOperationId=str(activation["cutover_operation_id"]), activationRequestHash=activation["request_hash"],
            operationIds=activation["operation_ids"])
        _model_work(request_basis, ledger, 2)
        if canonical_sha256(request_basis) != lifecycle["request_hash"]:
            _invalid()
        if len(receipts) != 2 or len(events) != 2:
            _invalid()
        by_phase = {}; by_sequence = {}
        for row in receipts:
            if row["runtime_operation_id"] != runtime["operation_id"] or row["phase"] in by_phase or row["request_hash"] != lifecycle["request_hash"]:
                _invalid()
            by_phase[row["phase"]] = row
        for row in events:
            if row["runtime_operation_id"] != runtime["operation_id"] or row["sequence"] in by_sequence:
                _invalid()
            by_sequence[row["sequence"]] = row
        if set(by_phase) != {"fence", "detach"} or set(by_sequence) != {1, 2}:
            _invalid()
        results = []
        refresh_refs = []
        for sequence, phase, snapshot, event_type in ((1, "fence", fenced, "DISPATCH_DISABLE_FENCED"),
                (2, "detach", detached, "DISPATCH_DISABLED_DETACHED")):
            row = by_phase[phase]; event = by_sequence[sequence]; body = row["authority_data"]
            _model_work(body, ledger, 8); _model_work(event["payload"], ledger, 4)
            if event["event_type"] != event_type or event["occurred_at"] != row["created_at"]:
                _invalid()
            _snapshot9(body.get("dispatchSnapshot"), group_id, ledger)
            fence_ref = body.get("fenceReceiptRef")
            if phase == "detach" and (type(fence_ref) is not dict or type(fence_ref.get("revision")) is not int):
                _invalid()
            unknown = body.get("unknownAttempts")
            if type(unknown) is not list or (phase == "detach" and unknown):
                _invalid()
            for attempt in unknown:
                ledger._charge(rows=1, node_count=5)
                if type(attempt) is not dict or set(attempt) != {"attemptId", "occurrenceId", "targetIdempotencyKey", "resolvedAt"}:
                    _invalid()
                _fact_uuid(attempt["attemptId"]); occurrence = _fact_uuid(attempt["occurrenceId"])
                if attempt["targetIdempotencyKey"] != "automation-occurrence:" + str(occurrence):
                    _invalid()
                _scalar(attempt["resolvedAt"], "timestamp with time zone!", ledger)
            refresh = body.get("configurationRefreshRef")
            if refresh is not None:
                if (type(refresh) is not dict or set(refresh) != {"resourceType", "resourceId", "revision", "contentHash"}
                        or refresh["resourceType"] != "DispatchConfigurationRefreshReceipt"
                        or type(refresh["revision"]) is not int or not 1 <= refresh["revision"] < 2**63
                        or type(refresh["contentHash"]) is not str or _HASH.fullmatch(refresh["contentHash"]) is None):
                    _invalid()
                _fact_uuid(refresh["resourceId"])
            refresh_refs.append(refresh)
            expected_body = EcommerceGrowthDisableDependent._authority(scope, runtime, activation, phase=phase,
                dispatch_snapshot=list(map(dict, snapshot)), request_hash=lifecycle["request_hash"], unknown_attempts=unknown,
                fence_receipt=None if phase == "fence" else by_phase["fence"], configuration_refresh_ref=refresh)
            if body != expected_body:
                _invalid()
            joined = dict(row, activation_operation_id=activation["cutover_operation_id"], operation_ids=lifecycle["operation_ids"],
                status=lifecycle["status"], event_payload=event["payload"], payload_hash=event["payload_hash"])
            results.append(EcommerceGrowthDisableDependent._receipt(scope, joined, replayed=False))
        if (refresh_refs[0] != refresh_refs[1] or by_phase["fence"]["created_at"] != lifecycle["created_at"]
                or not lifecycle["created_at"] <= lifecycle["updated_at"] <= by_phase["detach"]["created_at"]):
            _invalid()
        return _LifecycleReceiptPair(results[0], results[1])
    except (ValueError, TypeError, KeyError, OverflowError, EcommerceGrowthLifecycleError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _PredecessorLifecycleGraph:
    cutovers: _PredecessorCutoverGraph
    pairs: Mapping
    by_detach: Mapping
    lifecycles: Mapping
    bindings: Mapping
    pending_control_operations: tuple
    pending_refresh_refs: Mapping
    pending_cutover_operations: tuple


def _predecessor_lifecycle_history(facts, cutovers, *, scope, ledger):
    """Actual old L/B/drain observations, without inventing historical control or refresh proof."""
    _check_predecessor_scope(facts, scope, ledger)
    if type(cutovers) is not _PredecessorCutoverGraph or cutovers.partition is not facts.predecessors:
        _invalid()
    p = facts.predecessors
    names = ("public.extension_runtime_operation", "public.extension_dispatch_lifecycle_operation",
        "public.extension_dispatch_lifecycle_receipt", "public.extension_dispatch_lifecycle_event",
        "public.extension_runtime_binding", "public.extension_runtime_resource_lease",
        "public.automation_occurrence", "public.automation_occurrence_dispatch_attempt")
    ledger._charge(rows=sum(len(p[n]) for n in names), node_count=32)
    operations = {r["operation_id"]: r for r in p["public.extension_runtime_operation"]}
    lifecycle_rows = {r["runtime_operation_id"]: r for r in p["public.extension_dispatch_lifecycle_operation"]}
    occurrences = {r["occurrence_id"]: r for r in p["public.automation_occurrence"]}
    receipts = {identity: [] for identity in lifecycle_rows}; events = {identity: [] for identity in lifecycle_rows}
    for name, grouped in (("public.extension_dispatch_lifecycle_receipt", receipts), ("public.extension_dispatch_lifecycle_event", events)):
        for row in p[name]:
            identity = row["runtime_operation_id"]
            if identity not in grouped:
                _invalid()
            grouped[identity].append(row)
    for resource in p["public.extension_runtime_resource_lease"]:
        if resource["operation_id"] not in operations:
            _invalid()
    for attempt in p["public.automation_occurrence_dispatch_attempt"]:
        if attempt["occurrence_id"] not in occurrences:
            _invalid()
    pairs = {}; by_detach = {}; bindings = {}; pending_refresh = {}; used_roots = set()
    try:
        for identity, life in lifecycle_rows.items():
            ledger._charge(rows=1, node_count=24)
            installation = cutovers.operation_installations.get(life["activation_operation_id"])
            history = cutovers.histories.get(installation)
            root = None if history is None else history.activations.get(life["activation_operation_id"])
            runtime = operations.get(identity)
            if (root is None or "resume" not in root.receipts or runtime is None
                    or runtime["installation_id"] != installation or runtime["kind"] != "disable"
                    or runtime["status"] != "succeeded" or runtime["phase"] != "succeeded"
                    or life["status"] != "detached" or life["fenced_group_revision"] < 1
                    or life["cutover_group_id"] != root.prepared.receipt.cutover_group_id):
                _invalid()
            prepared = root.prepared.receipt
            ledger._charge(rows=len(p["public.extension_runtime_binding"]), node_count=8)
            binding = _one([r for r in p["public.extension_runtime_binding"]
                if r["installation_id"] == installation and r["generation"] == prepared.target_generation])
            if (binding["enabled"] is not False or binding["operation_fence"] is not True
                    or binding["desired_state"] != "disabled" or binding["observed_state"] != "unknown"
                    or binding["revision"] <= root.receipts["resume"].target_runtime_revision
                    or binding["execution_epoch"] <= prepared.target_execution_epoch
                    or life["created_at"] < root.receipts["resume"].created_at):
                _invalid()
            group = life["cutover_group_id"]
            extension = _snapshot9(life["extension_snapshot"], group, ledger)
            fenced = _snapshot9(life["fenced_snapshot"], group, ledger)
            legacy = _snapshot9(life["legacy_snapshot"], group, ledger)
            if list(map(dict, legacy)) != list(map(dict, root.prepared.old_snapshot)):
                _invalid()
            epochs = set()
            for before, held in zip(extension, fenced):
                if (before["handlerKind"] != "extension" or before["installationId"] != str(installation)
                        or before["generation"] != str(prepared.target_generation) or before["operationFence"] is not False
                        or before["cutoverGroupRevision"] + 1 != life["fenced_group_revision"]
                        or dict(held) != dict(before, operationFence=True, revision=before["revision"] + 1,
                            cutoverGroupRevision=life["fenced_group_revision"])):
                    _invalid()
                epochs.add(before["executionEpoch"])
            if len(epochs) != 1 or not prepared.target_execution_epoch <= next(iter(epochs)) < binding["execution_epoch"]:
                _invalid()
            detached = tuple(dict(old, revision=held["revision"] + 1,
                cutoverGroupRevision=life["fenced_group_revision"] + 1) for old, held in zip(legacy, fenced))
            activation_rows = p["public.extension_dispatch_cutover_operation"]
            ledger._charge(rows=len(activation_rows), node_count=8)
            activation = _one([r for r in activation_rows if r["cutover_operation_id"] == life["activation_operation_id"]])
            pair = _lifecycle_receipt_pair(receipts[identity], events[identity], scope=scope, runtime=runtime,
                activation=activation, lifecycle=life, fenced=fenced, detached=detached, ledger=ledger)
            refresh = pair.detach.configuration_refresh_ref
            if refresh is None:
                if list(map(dict, extension)) != list(map(dict, root.prepared.new_snapshot)):
                    _invalid()
            else:
                pending_refresh[identity] = refresh
            work_names = ("public.extension_dispatch_claim_gate", "public.extension_runtime_execution_attempt",
                "public.automation_occurrence", "public.automation_occurrence_dispatch_attempt", "public.extension_runtime_resource_lease")
            ledger._charge(rows=sum(len(p[n]) for n in work_names), node_count=16)
            if (any(r["cutover_group_id"] == group for r in p["public.extension_dispatch_claim_gate"])
                    or any(r["installation_id"] == installation and r["generation"] == prepared.target_generation
                        and r["state"] == "running" for r in p["public.extension_runtime_execution_attempt"])
                    or any(r["installation_id"] == installation and r["generation"] == prepared.target_generation
                        and r["status"] == "claimed" for r in occurrences.values())
                    or any(occurrences[r["occurrence_id"]]["installation_id"] == installation
                        and occurrences[r["occurrence_id"]]["generation"] == prepared.target_generation
                        and r["status"] in {"claimed", "unknown"} for r in p["public.automation_occurrence_dispatch_attempt"])
                    or any(operations[r["operation_id"]]["installation_id"] == installation
                        and r["generation"] == prepared.target_generation
                        and (r["cleanup_state"] != "released" or r["observed_release"] is not True)
                        for r in p["public.extension_runtime_resource_lease"])):
                _invalid()
            if pair.detach.receipt_id in by_detach:
                _invalid()
            pairs[identity] = pair; by_detach[pair.detach.receipt_id] = identity; bindings[identity] = binding
            used_roots.add(life["activation_operation_id"])
        return _PredecessorLifecycleGraph(cutovers, MappingProxyType(pairs), MappingProxyType(by_detach),
            MappingProxyType(lifecycle_rows), MappingProxyType(bindings), tuple(sorted(pairs)), MappingProxyType(pending_refresh),
            tuple(sorted(set(cutovers.operation_installations) - used_roots)))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, EcommerceGrowthLifecycleError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _ConfigurationFactView:
    relations: Mapping


@dataclass(frozen=True, slots=True)
class _PredecessorRefreshGraph:
    lifecycle: _PredecessorLifecycleGraph
    chains: Mapping
    detached: Mapping
    remaining_receipt_ids: tuple
    pending_control_operations: Mapping
    pending_installation_refs: Mapping


def _predecessor_refresh_history(facts, lifecycle, *, scope, ledger):
    """Link actual old refresh/configuration rows, retaining unproved control causes."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(lifecycle) is not _PredecessorLifecycleGraph
            or lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    p = facts.predecessors; chains = {}; groups = {}; detached = {}; control_refs = {}; install_refs = {}
    roots = {}
    for history in lifecycle.cutovers.histories.values():
        ledger._charge(rows=len(history.activations), node_count=4 * len(history.activations))
        roots.update(history.activations)
    try:
        for row in p["public.extension_dispatch_configuration_refresh_receipt"]:
            ledger._charge(rows=1, node_count=8)
            identity = row["activation_operation_id"]
            if identity not in roots or "resume" not in roots[identity].receipts:
                _invalid()
            groups.setdefault(identity, []).append(row)
        for identity, root in roots.items():
            if "resume" not in root.receipts:
                continue
            chains[identity] = _refresh_receipt_chain(groups.get(identity, []), root, scope=scope, ledger=ledger)
        for identity, pair in lifecycle.pairs.items():
            life = lifecycle.lifecycles[identity]; binding = lifecycle.bindings[identity]
            chain = chains.get(life["activation_operation_id"])
            if chain is None:
                _invalid()
            reference = pair.detach.configuration_refresh_ref
            if chain.steps:
                if (reference is None
                        or canonical_sha256(reference.model_dump(mode="json", by_alias=True, exclude_none=True)) != canonical_sha256(dict(chain.authority_ref))):
                    _invalid()
                ledger._charge(rows=len(p["public.extension_runtime_configuration"]), node_count=8)
                config_rows = tuple(r for r in p["public.extension_runtime_configuration"]
                    if r["installation_id"] == binding["installation_id"] and r["generation"] == binding["generation"])
                view = _ConfigurationFactView(MappingProxyType({"public.extension_runtime_configuration": config_rows}))
                configurations = _configuration_history(view, scope=scope, installation_id=str(binding["installation_id"]),
                    generation=binding["generation"], binding_ref=binding["config_ref"], ledger=ledger)
                pending = []
                for step in chain.steps:
                    for config in (step.request.source_configuration_ref, step.request.target_configuration_ref):
                        if configurations.versions.get((UUID(config.configurationId), config.revision), (None,))[0] != config:
                            _invalid()
                    pending.extend((UUID(step.request.configure_operation_id), UUID(step.request.enable_operation_id)))
                control_refs[identity] = tuple(pending)
                install_refs[identity] = tuple(step.request.installation_ref for step in chain.steps)
                ledger._charge(rows=len(p["public.extension_dispatch_lifecycle_receipt"]), node_count=4)
                actual = _one([r for r in p["public.extension_dispatch_lifecycle_receipt"]
                    if r["receipt_id"] == pair.fence.receipt_id])
                if actual["created_at"] < chain.steps[-1].row["created_at"]:
                    _invalid()
            elif reference is not None:
                _invalid()
            _model_work(life["extension_snapshot"], ledger, 4)
            if canonical_sha256(life["extension_snapshot"]) != canonical_sha256(list(map(dict, chain.dispatch_snapshot))):
                _invalid()
            detached[identity] = life["activation_operation_id"]
        used_roots = set(detached.values())
        remaining = tuple(sorted(row["receipt_id"] for root_id, rows in groups.items() if root_id not in used_roots for row in rows))
        return _PredecessorRefreshGraph(lifecycle, MappingProxyType(chains), MappingProxyType(detached), remaining,
            MappingProxyType(control_refs), MappingProxyType(install_refs))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _PredecessorControlGraph:
    refreshes: _PredecessorRefreshGraph
    histories: Mapping
    linked_refresh_operations: Mapping
    linked_disables: Mapping
    pending_preparations: Mapping
    pending_timeline: tuple
    remaining_operations: tuple


def _predecessor_control_history(facts, refreshes, *, scope, ledger):
    _check_predecessor_scope(facts, scope, ledger)
    if (type(refreshes) is not _PredecessorRefreshGraph
            or refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    p = facts.predecessors
    operations = {r["operation_id"]: r for r in p["public.extension_runtime_operation"]}
    ledger._charge(rows=len(operations), node_count=4 * len(operations))
    events = _runtime_event_rows(operations, p["public.extension_runtime_event"], scope=scope, ledger=ledger)
    if len({r["event_id"] for r in p["public.extension_runtime_event"]}) != len(p["public.extension_runtime_event"]):
        _invalid()
    histories = {}; pending = {}; linked = {}; disables = {}; used = set()
    lifecycle = refreshes.lifecycle
    try:
        for identity, binding in lifecycle.bindings.items():
            target = (binding["installation_id"], binding["generation"])
            if target not in histories:
                selected = {}; selected_events = {}
                for op_id, operation in operations.items():
                    ledger._charge(rows=1, node_count=8)
                    if operation["installation_id"] != target[0]:
                        continue
                    group = events[op_id]
                    if operation["kind"] in {"configure", "enable", "disable"}:
                        first = group.get(1)
                        key = "bindingTarget" if operation["kind"] == "disable" else "configurationTarget"
                        route = None if first is None else first["payload"].get(key)
                        if type(route) is not dict or "generation" not in route:
                            _invalid()
                        if _fact_uuid(route["generation"]) != target[1]:
                            continue
                        if operation["status"] == "succeeded" and operation["phase"] != "succeeded":
                            _invalid()
                    selected[op_id] = operation; selected_events[op_id] = tuple(group.values())
                preparation_rows = []
                for op_id, group in selected_events.items():
                    for event in group:
                        ledger._charge(rows=1, node_count=4)
                        body = event["payload"]
                        if (event["type"] == "preparation_committed" and body.get("installationId") == str(target[0])
                                and body.get("generation") == str(target[1])):
                            operation = selected[op_id]
                            if (operation["kind"] != "runtime-apply" or operation["phase"] != "succeeded"
                                    or operation["status"] not in {"succeeded", "failed"}
                                    or type(body.get("installationRevision")) is not int
                                    or not 1 <= body["installationRevision"] <= binding["installation_revision"]
                                    or type(body.get("expectedRevision")) is not int
                                    or body["expectedRevision"] < 1 or body["expectedRevision"] + 2 != event["sequence"]):
                                _invalid()
                            preparation_rows.append((op_id, event))
                preparation_id, preparation_event = _one(preparation_rows)
                ledger._charge(rows=len(p["public.extension_runtime_configuration"]), node_count=8)
                config_rows = tuple(r for r in p["public.extension_runtime_configuration"]
                    if (r["installation_id"], r["generation"]) == target)
                view = _ConfigurationFactView(MappingProxyType({"public.extension_runtime_configuration": config_rows}))
                configurations = _configuration_history(view, scope=scope, installation_id=str(target[0]),
                    generation=target[1], binding_ref=binding["config_ref"], ledger=ledger)
                history = _control_commit_history(selected, selected_events, scope=scope,
                    installation_id=target[0], generation=target[1], installation_revision=binding["installation_revision"],
                    binding_revision=binding["revision"], configurations=configurations,
                    preparation_operation_id=preparation_id, ledger=ledger)
                histories[target] = history; pending[target] = (preparation_id, preparation_event)
            history = histories[target]
            chain = refreshes.chains[lifecycle.lifecycles[identity]["activation_operation_id"]]
            prepare = chain.root.prepared.receipt
            initial = _one([c for c in history.commits.values() if c.kind == "enable"
                and c.to_revision == prepare.target_runtime_revision and c.execution_epoch == prepare.target_execution_epoch])
            if chain.steps and initial.config_ref != chain.steps[0].request.source_configuration_ref:
                _invalid()
            references = []
            for step in chain.steps:
                request = step.request; configure_id = UUID(request.configure_operation_id); enable_id = UUID(request.enable_operation_id)
                configure = history.commits.get(configure_id); enable = history.commits.get(enable_id)
                if (configure is None or enable is None or configure.kind != "configure" or enable.kind != "enable"
                        or configure.from_revision != request.source_runtime_revision
                        or configure.to_revision != request.source_runtime_revision + 2
                        or enable.from_revision != configure.to_revision or enable.to_revision != request.target_runtime_revision
                        or configure.execution_epoch != request.source_execution_epoch + 1
                        or enable.execution_epoch != request.source_execution_epoch + 2
                        or enable.execution_epoch != request.target_execution_epoch
                        or configure.config_ref != request.target_configuration_ref or enable.config_ref != request.target_configuration_ref
                        or operations[configure_id]["revision"] != request.configure_operation_revision
                        or operations[enable_id]["revision"] != request.enable_operation_revision
                        or operations[configure_id]["requested_by"] != step.row["actor"]
                        or operations[enable_id]["requested_by"] != step.row["actor"]):
                    _invalid()
                references.extend((configure_id, enable_id))
            disable = history.commits.get(identity)
            if (disable is None or disable.kind != "disable" or disable.to_revision != binding["revision"]
                    or disable.execution_epoch != binding["execution_epoch"] or disable.from_revision < chain.runtime_revision
                    or (chain.steps and disable.from_revision != chain.runtime_revision)):
                _invalid()
            linked[identity] = tuple(references); disables[identity] = disable
            used.update(history.targets)
        return _PredecessorControlGraph(refreshes, MappingProxyType(histories), MappingProxyType(linked),
            MappingProxyType(disables), MappingProxyType(pending), tuple(sorted(lifecycle.pairs)), tuple(sorted(set(operations) - used)))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _PredecessorBindingTimelineGraph:
    controls: _PredecessorControlGraph
    timelines: Mapping
    pending_remaining_operations: tuple
    pending_preparations: Mapping


def _predecessor_binding_timeline(facts, controls, *, scope, ledger):
    _check_predecessor_scope(facts, scope, ledger)
    if (type(controls) is not _PredecessorControlGraph
            or controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    lifecycle = controls.refreshes.lifecycle; timelines = {}
    try:
        for identity, binding in lifecycle.bindings.items():
            target = (binding["installation_id"], binding["generation"])
            if target in timelines:
                continue
            history = controls.histories[target]
            cutovers = lifecycle.cutovers.histories[target[0]]
            steps = list(history.commits.values())
            steps.extend(_cutover_binding_steps(cutovers, target[1], ledger))
            _model_work(binding["config_ref"], ledger, 4)
            configuration = ConfigurationRef.model_validate_json(json.dumps(binding["config_ref"], allow_nan=False))
            timeline = _binding_step_timeline(steps, expected_revision=binding["revision"],
                execution_epoch=binding["execution_epoch"], configuration=configuration, ledger=ledger)
            for operation_id in history.stale:
                ledger._charge(rows=len(facts.predecessors["public.extension_runtime_event"]), node_count=8)
                event = max((r for r in facts.predecessors["public.extension_runtime_event"]
                    if r["operation_id"] == operation_id), key=lambda row: row["sequence"])
                if (history.targets[operation_id].bindingRevision not in timeline.versions
                        or event["payload"]["currentBindingRevision"] not in timeline.versions):
                    _invalid()
            timelines[target] = timeline
        return _PredecessorBindingTimelineGraph(controls, MappingProxyType(timelines),
            controls.remaining_operations, controls.pending_preparations)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _PredecessorRuntimeClosure:
    timeline: _PredecessorBindingTimelineGraph
    terminals: Mapping
    pending_locks: tuple
    pending_preparations: Mapping
    remaining_operations: tuple


def _predecessor_runtime_closure(facts, timeline, *, scope, predecessor_locks, ledger):
    """Consume only jointly proven old runtime obligations; other ancestry stays pending."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(timeline) is not _PredecessorBindingTimelineGraph
            or timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors
            or (predecessor_locks is not None and type(predecessor_locks) not in (dict, MappingProxyType))):
        _invalid()
    targets = tuple(sorted(timeline.timelines))
    if (set(targets) != set(timeline.pending_preparations) or set(targets) != set(timeline.controls.histories)
            or (predecessor_locks is not None and len(predecessor_locks) > 2048)):
        _invalid()
    locks = {} if predecessor_locks is None else dict(predecessor_locks)
    installations = {target[0] for target in targets}
    if predecessor_locks is None:
        for installation_id in sorted(installations):
            lock = _predecessor_stored_lock(facts, scope=scope, installation_id=installation_id, ledger=ledger)
            if lock is not None:
                locks[installation_id] = lock
    ledger._charge(rows=len(locks) + len(targets), node_count=4 * (len(locks) + len(targets)))
    if any(type(key) is not UUID or key not in installations or type(lock) is not StoredCompositionLock
           for key, lock in locks.items()):
        _invalid()
    pending = dict(timeline.pending_preparations); remaining = set(timeline.pending_remaining_operations)
    terminals = {}; missing = []
    try:
        for installation_id, generation in targets:
            target = installation_id, generation
            if installation_id not in locks:
                missing.append(target)
                continue
            verification = _predecessor_runtime_verification(facts, scope=scope,
                installation_id=installation_id, generation=generation, source_lock=locks[installation_id], ledger=ledger)
            protocol = _predecessor_runtime_protocol(facts, verification, scope=scope, ledger=ledger)
            terminal = _predecessor_lease_terminals(facts, protocol, timeline, scope=scope, ledger=ledger)
            terminals[target] = terminal
            pending.pop(target)
            operations = verification.preparations.operations
            ledger._charge(rows=len(remaining), node_count=2 * len(remaining))
            consumed = {identity for identity in remaining if identity in operations
                and operations[identity]["kind"] in {"runtime-apply", "runtime-verify"}}
            remaining.difference_update(consumed)
        return _PredecessorRuntimeClosure(timeline, MappingProxyType(terminals), tuple(missing),
            MappingProxyType(pending), tuple(sorted(remaining)))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor runtime closure facts") from None


@dataclass(frozen=True, slots=True)
class _LifecycleReceiptGraph:
    history: _ControlHistory
    activation: object
    lifecycle: object
    fence: object
    detach: object
    primary_dispatch: tuple


def _detached_lifecycle_receipts(facts, *, scope, source, locked_source, source_lock, ledger):
    """Verify original lifecycle pairs, not the complete detached branch.

    Activation phases, refresh parents and all remaining obligations must still
    be verified before this slice can contribute to a public admission result.
    """
    history = _control_history(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    graph = history.graph
    terminal = graph.receipt.receipt
    binding = graph.receipt.context.binding
    try:
        if terminal["retirement_kind"] != "detached":
            _invalid()
        lifecycle = _one(facts.relations["public.extension_dispatch_lifecycle_operation"])
        if (lifecycle["runtime_operation_id"] != terminal["disable_operation_id"]
                or lifecycle["activation_operation_id"] != terminal["activation_operation_id"]
                or lifecycle["status"] != "detached" or lifecycle["fenced_group_revision"] < 1
                or lifecycle["cutover_group_id"] != _fact_uuid(graph.receipt.authority["cutoverGroupId"])):
            _invalid()
        commit = history.commits.get(lifecycle["runtime_operation_id"])
        if (commit is None or commit.kind != "disable" or commit.to_revision != binding["revision"] - 1
                or commit.execution_epoch != binding["execution_epoch"]):
            _invalid()
        prepared = graph.receipt.context.notifications.preparation_facts
        runtime = prepared.operations[lifecycle["runtime_operation_id"]]
        activation = _one([row for row in facts.relations["public.extension_dispatch_cutover_operation"]
            if row["cutover_operation_id"] == lifecycle["activation_operation_id"]])
        ledger._charge(rows=len(facts.relations["public.extension_dispatch_cutover_operation"]), node_count=12)
        group_id = lifecycle["cutover_group_id"]
        expected_operations = sorted(ECOMMERCE_GROWTH_OPERATIONS)
        if (activation["kind"] != "activate" or activation["status"] != "resumed"
                or str(activation["target_installation_id"]) != source.installation_id
                or activation["target_generation"] != binding["generation"]
                or activation["cutover_group_id"] != group_id
                or not 1 <= activation["target_execution_epoch"] < binding["execution_epoch"]
                or activation["target_runtime_revision"] < 1
                or _HASH.fullmatch(activation["request_hash"]) is None
                or activation["operation_ids"] != expected_operations or lifecycle["operation_ids"] != expected_operations
                or lifecycle["requested_by"] != runtime["requested_by"]):
            _invalid()
        extension = _snapshot9(lifecycle["extension_snapshot"], group_id, ledger)
        fenced = _snapshot9(lifecycle["fenced_snapshot"], group_id, ledger)
        legacy = _snapshot9(lifecycle["legacy_snapshot"], group_id, ledger)
        if list(map(dict, legacy)) != activation["old_dispatch_snapshot"]:
            _invalid()
        epochs = set()
        for before, after, restored in zip(extension, fenced, legacy):
            if (before["handlerKind"] != "extension" or before["installationId"] != source.installation_id
                    or before["generation"] != str(binding["generation"]) or before["operationFence"] is not False
                    or restored["handlerKind"] != "legacy"
                    or before["cutoverGroupRevision"] + 1 != lifecycle["fenced_group_revision"]
                    or dict(after) != dict(before, operationFence=True, revision=before["revision"] + 1,
                        cutoverGroupRevision=lifecycle["fenced_group_revision"])):
                _invalid()
            epochs.add(before["executionEpoch"])
        if len(epochs) != 1 or not activation["target_execution_epoch"] <= next(iter(epochs)) < binding["execution_epoch"]:
            _invalid()
        ledger._charge(rows=len(facts.relations["public.extension_operation_dispatch_binding"]), node_count=12)
        current_rows = sorted((row for row in facts.relations["public.extension_operation_dispatch_binding"]
            if row["cutover_group_id"] == group_id), key=lambda row: row["operation_id"])
        current = _snapshot9([_growth_snapshot(dict(row)) for row in current_rows], group_id, ledger)
        expected_detached = [dict(old, revision=held["revision"] + 1,
            cutoverGroupRevision=lifecycle["fenced_group_revision"] + 1) for old, held in zip(legacy, fenced)]
        if list(map(dict, current)) != expected_detached:
            _invalid()
        ledger._charge(rows=len(facts.relations["public.extension_dispatch_claim_gate"]), node_count=1)
        if any(row["cutover_group_id"] == group_id for row in facts.relations["public.extension_dispatch_claim_gate"]):
            _invalid()
        pair = _lifecycle_receipt_pair(facts.relations["public.extension_dispatch_lifecycle_receipt"],
            facts.relations["public.extension_dispatch_lifecycle_event"], scope=scope, runtime=runtime,
            activation=activation, lifecycle=lifecycle, fenced=fenced, detached=current, ledger=ledger)
        return _LifecycleReceiptGraph(history, activation, lifecycle, pair.fence, pair.detach, current)
    except (ValueError, TypeError, KeyError, OverflowError, EcommerceGrowthLifecycleError):
        raise ValueError("invalid terminal facts") from None


@dataclass(frozen=True, slots=True)
class _DetachedRefreshGraph:
    lifecycle: _LifecycleReceiptGraph
    cutovers: _CutoverHistoryGraph
    refresh: _PrimaryRefreshGraph


def _detached_refresh_history(facts, *, scope, source, locked_source, source_lock, ledger):
    """Join proven C/refresh/L references, without claiming the complete B timeline."""
    lifecycle = _detached_lifecycle_receipts(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    cutovers = _cutover_history(facts, scope=scope, source=source, ledger=ledger)
    activation_id = lifecycle.activation["cutover_operation_id"]
    refresh = _primary_refresh_history(facts, cutovers, lifecycle.history,
        activation_id=activation_id, scope=scope, source=source, ledger=ledger)
    expected_snapshot = list(map(dict, refresh.dispatch_snapshot))
    actual_snapshot = lifecycle.lifecycle["extension_snapshot"]
    _model_work(expected_snapshot, ledger, 3); _model_work(actual_snapshot, ledger, 3)
    if canonical_sha256(actual_snapshot) != canonical_sha256(expected_snapshot):
        _invalid()
    expected_ref = dict(refresh.authority_ref) if refresh.receipt_ids else None
    for receipt in (lifecycle.fence, lifecycle.detach):
        reference = receipt.configuration_refresh_ref
        if expected_ref is None:
            if reference is not None:
                _invalid()
        else:
            if reference is None:
                _invalid()
            actual_ref = reference.model_dump(mode="json", by_alias=True, exclude_none=True)
            _model_work(actual_ref, ledger, 3)
            if canonical_sha256(actual_ref) != canonical_sha256(expected_ref):
                _invalid()
    if refresh.receipt_ids:
        rows = facts.relations["public.extension_dispatch_configuration_refresh_receipt"]
        ledger._charge(rows=len(rows), node_count=2)
        authority_time = _one([r for r in rows if r["receipt_id"] == refresh.receipt_ids[-1]])["created_at"]
    else:
        authority_time = cutovers.activations[activation_id].receipts["resume"].created_at
    disable = lifecycle.history.commits[lifecycle.lifecycle["runtime_operation_id"]]
    if (lifecycle.lifecycle["created_at"] < authority_time or disable.from_revision < refresh.runtime_revision
            or disable.execution_epoch <= refresh.execution_epoch
            or (refresh.receipt_ids and disable.from_revision != refresh.runtime_revision)):
        _invalid()
    return _DetachedRefreshGraph(lifecycle, cutovers, refresh)


@dataclass(frozen=True, slots=True)
class _DetachedControlGraph:
    joined: _DetachedRefreshGraph
    timeline: _ControlTimeline


def _detached_control_timeline(facts, *, scope, source, locked_source, source_lock, ledger):
    joined = _detached_refresh_history(facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    history = joined.lifecycle.history
    timeline = _derive_control_timeline(history, ledger, detached=joined)
    prepared = history.graph.receipt.context.notifications.preparation_facts
    _preparation_terminal_history(prepared, ledger, timeline=timeline)
    return _DetachedControlGraph(joined, timeline)


@dataclass(frozen=True, slots=True)
class _RegistrationHistory:
    origins: Mapping
    unconsumed: tuple
    pending_predecessors: Mapping
    pending_control_roots: tuple


def _registration_history(facts, cutovers, controls, *, scope, source, ledger):
    """Stored origins and control pins only; unresolved retirement/old-L edges stay explicit."""
    if type(cutovers) is not _CutoverHistoryGraph or type(controls) is not _ControlHistory or type(scope) is not TenantScope:
        _invalid()
    return _registration_history_rows(facts.relations, cutovers, scope=scope,
        installation_id=source.installation_id, binding=controls.graph.receipt.context.binding,
        commits=controls.commits, configurations=controls.graph.configurations, ledger=ledger)


def _registration_installation_pin(request, *, installation_id, installation_revision, revisions, ledger):
    """Original persisted installationRef comparison, shared with unused withdrawn origins."""
    ledger._charge(rows=len(revisions), node_count=8)
    installed = _one([r for r in revisions if r["revision"] == installation_revision])
    expected = dict(installationId=installation_id, revision=installed["revision"],
        lockHash=installed["lock_hash"], overlayRevision=installed["overlay_revision"])
    wire = request.installationRef.model_dump(mode="json", by_alias=True)
    _model_work(wire, ledger, 3)
    if canonical_sha256(wire) != canonical_sha256(expected):
        _invalid()
    return request.installationRef


def _registration_history_rows(relations, cutovers, *, scope, installation_id, binding, commits, configurations, ledger):
    """Original stored origins and actual control/configuration/installation pins."""
    if (type(cutovers) is not _CutoverHistoryGraph or type(scope) is not TenantScope
            or type(installation_id) is not str or type(configurations) is not _ConfigurationHistory
            or type(ledger) is not _WorkLedger):
        _invalid()
    records = {}; pending = {}; used = set(); origins = {}; pending_controls = []
    try:
        for kind, family, decoder in (
            ("FirstDispatchRegistrationReceipt", "public.extension_dispatch_registration_receipt", decode_registration_receipt),
            ("SuccessorDispatchRegistrationReceipt", "public.extension_dispatch_successor_registration_receipt", decode_successor_receipt),
        ):
            keys = set(); groups = set()
            for row in relations[family]:
                ledger._charge(rows=1, node_count=16)
                if ((row["org_id"], row["project_id"]) != scope.key or row["installation_id"] != UUID(installation_id)
                        or row["idempotency_key"] in keys
                        or (kind == "FirstDispatchRegistrationReceipt" and row["group_id"] in groups)):
                    _invalid()
                keys.add(row["idempotency_key"]); groups.add(row["group_id"])
                payload = row["payload"]
                _model_work(payload, ledger, 16)
                decoded = decoder(dict(row), scope=scope)
                _snapshot9(payload["dispatchSnapshot"], row["group_id"], ledger)
                if canonical_sha256(payload["request"]) != row["request_hash"]:
                    _invalid()
                created = _scalar(payload["createdAt"], "timestamp with time zone!", ledger)
                if created > row["created_at"]:
                    _invalid()
                records[kind, row["receipt_id"]] = row
                if kind == "SuccessorDispatchRegistrationReceipt":
                    request = SuccessorDispatchRegistrationRequest.model_validate(decoded["request"])
                    pending[row["receipt_id"]] = request.predecessorDetachReceiptRef
        ledger._charge(rows=len(cutovers.activations), node_count=len(cutovers.activations) * 8)
        for identity, graph in cutovers.activations.items():
            prepare = graph.prepared.receipt
            ref = prepare.registration_receipt_ref
            if ref is None:
                continue
            key = (ref.resourceType, UUID(ref.resourceId))
            row = records.get(key)
            if row is None or row["created_at"] > prepare.created_at:
                _invalid()
            _model_work(row["payload"], ledger, 12)
            request = verify_registration_origin(row=dict(row), scope=scope, receipt_ref=ref,
                dispatch_snapshot=list(map(dict, graph.prepared.old_snapshot)), installation_id=installation_id,
                generation=str(prepare.target_generation), execution_epoch=prepare.target_execution_epoch,
                binding_revision=prepare.target_runtime_revision)
            origins[identity] = request; used.add(key)
            if prepare.target_generation != binding["generation"]:
                pending_controls.append(identity)
                continue
            enabled = [c for c in commits.values() if c.kind == "enable"
                and c.to_revision == prepare.target_runtime_revision and c.execution_epoch == prepare.target_execution_epoch]
            ledger._charge(rows=len(commits), node_count=8)
            proof = _one(enabled)
            if proof.config_ref != request.configRef:
                _invalid()
            actual = configurations.versions.get((UUID(request.configRef.configurationId), request.configRef.revision))
            if actual is None or actual[0] != request.configRef:
                _invalid()
            _registration_installation_pin(request, installation_id=installation_id,
                installation_revision=binding["installation_revision"], revisions=relations["public.bundle_installation_revision"], ledger=ledger)
        return _RegistrationHistory(MappingProxyType(origins), tuple(sorted(set(records) - used)),
            MappingProxyType(pending), tuple(sorted(pending_controls)))
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _PredecessorRegistrationHistory:
    runtime: _PredecessorRuntimeClosure
    histories: Mapping
    pending_runtime_targets: tuple
    remaining_origin_refs: Mapping
    pending_predecessors: Mapping


def _predecessor_registration_history(facts, runtime, *, scope, ledger):
    """Prove old C origins using actual old runtime parents, without resolving old L by assumption."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(runtime) is not _PredecessorRuntimeClosure
            or runtime.timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    p = facts.predecessors; cutovers = runtime.timeline.controls.refreshes.lifecycle.cutovers
    remaining = {}; histories = {}; pending = {}
    try:
        for history in cutovers.histories.values():
            ledger._charge(rows=len(history.activations), node_count=len(history.activations) * 4)
            for identity, graph in history.activations.items():
                ref = graph.prepared.receipt.registration_receipt_ref
                if ref is not None:
                    remaining[identity] = ref
        for target, terminal in runtime.terminals.items():
            installation_id, generation = target; verification = terminal.protocol.verification
            families = ("public.bundle_installation", "public.bundle_installation_revision",
                "public.extension_dispatch_registration_receipt", "public.extension_dispatch_successor_registration_receipt")
            ledger._charge(rows=sum(len(p[name]) for name in families), node_count=12)
            head = _one(tuple(row for row in p[families[0]] if row["installation_id"] == installation_id))
            relations = MappingProxyType({
                families[1]: tuple(row for row in p[families[1]] if row["installation_pk"] == head["installation_pk"]),
                families[2]: tuple(row for row in p[families[2]] if row["installation_id"] == installation_id),
                families[3]: tuple(row for row in p[families[3]] if row["installation_id"] == installation_id),
            })
            history = _registration_history_rows(relations, cutovers.histories[installation_id], scope=scope,
                installation_id=str(installation_id), binding=verification.binding,
                commits=runtime.timeline.controls.histories[target].commits,
                configurations=verification.configurations, ledger=ledger)
            histories[target] = history
            for identity in history.origins:
                if identity not in history.pending_control_roots:
                    remaining.pop(identity, None)
            for receipt_id, ref in history.pending_predecessors.items():
                pending[installation_id, generation, receipt_id] = ref
        return _PredecessorRegistrationHistory(runtime, MappingProxyType(histories),
            tuple(sorted(runtime.pending_preparations)), MappingProxyType(remaining), MappingProxyType(pending))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor registration origin facts") from None


@dataclass(frozen=True, slots=True)
class _RuntimeCommandHistory:
    records: Mapping
    pending_dispatch_sources: Mapping
    pending_target_refs: Mapping


def _runtime_command_history(facts, *, scope, ledger):
    """Original persisted record shapes; actual dispatch/target parents remain unresolved."""
    if type(facts) is not _DecodedFacts or type(scope) is not TenantScope or type(ledger) is not _WorkLedger:
        _invalid()
    records = {}; dispatches = {}; targets = {}
    try:
        for row in facts.relations["public.ecommerce_growth_runtime_command_receipt"]:
            ledger._charge(rows=1, node_count=24)
            key = (row["operation_id"], row["idempotency_key"])
            if ((row["org_id"], row["project_id"]) != scope.key or row["operation_id"] not in _COMMAND_OPERATIONS
                    or key in records or not 1 <= len(row["idempotency_key"]) <= 200
                    or not row["idempotency_key"].strip()
                    or row["idempotency_key"] != row["idempotency_key"].strip(" ")
                    or not 1 <= len(row["actor"]) <= 240 or row["actor"] != row["actor"].strip(" ")
                    or not _HASH.fullmatch(row["request_hash"])):
                _invalid()
            for field in ("dispatch_revision", "execution_epoch", "cutover_group_revision", "runtime_revision"):
                if type(row[field]) is not int or row[field] < 1:
                    _invalid()
            _model_work(row["target_receipt_ref"], ledger, 6)
            _model_work(row["response"], ledger, 6)
            target = _command_exact_ref(row["target_receipt_ref"])
            response = _command_response(row["response"], target)
            if "requestHash" in response and response["requestHash"] != row["request_hash"]:
                _invalid()
            records[key] = row
            dispatches[key] = (row["installation_id"], row["generation"], row["cutover_group_id"],
                row["dispatch_revision"], row["execution_epoch"], row["cutover_group_revision"], row["runtime_revision"])
            targets[key] = MappingProxyType(target)
        return _RuntimeCommandHistory(MappingProxyType(records), MappingProxyType(dispatches), MappingProxyType(targets))
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _WithdrawalHistory:
    receipts: Mapping
    withdrawn_origins: tuple
    pending_dependency_origins: tuple
    pending_installation_etags: Mapping
    observed_current_dependencies: Mapping


def _withdrawal_history(facts, cutovers, *, scope, source, ledger):
    """Resolve immutable withdrawal parents; dependency/CAS admission remains explicit."""
    if (type(facts) is not _DecodedFacts or type(cutovers) is not _CutoverHistoryGraph
            or type(scope) is not TenantScope or type(source) is not ReinstallSourceRef
            or type(ledger) is not _WorkLedger):
        _invalid()
    return _withdrawal_history_rows(facts.relations, scope=scope, installation_id=source.installation_id,
        current_revision=source.terminal_revision, ledger=ledger)


def _withdrawal_history_rows(relations, *, scope, installation_id, current_revision, ledger):
    """Original immutable withdrawal provenance; pristine dependencies/CAS remain pending."""
    if (type(scope) is not TenantScope or type(installation_id) is not str
            or type(current_revision) is not int or not 1 <= current_revision < 2**63
            or type(ledger) is not _WorkLedger):
        _invalid()
    parents = {}; groups = set(); receipts = {}; origins = set(); keys = set(); etags = {}; observed = {}
    dependencies = {}
    rows = relations["public.extension_dispatch_registration_receipt"]
    ledger._charge(rows=len(rows), node_count=len(rows) * 4)
    for row in rows:
        if row["receipt_id"] in parents:
            _invalid()
        parents[row["receipt_id"]] = row
    # Include legacy cutovers with no registrationRef: group occupancy is still history.
    operations = relations["public.extension_dispatch_cutover_operation"]
    ledger._charge(rows=len(operations), node_count=len(operations) * 2)
    for operation in operations:
        groups.add(operation["cutover_group_id"])
    for kind, family in (("schedule", "public.automation_schedule_binding"),
                         ("command", "public.ecommerce_growth_runtime_command_receipt")):
        for row in relations[family]:
            ledger._charge(rows=1, node_count=6)
            if (row["org_id"], row["project_id"]) != scope.key:
                _invalid()
            key = ((kind, row["operation_id"], row["policy_id"], row["policy_revision"]) if kind == "schedule"
                else (kind, row["operation_id"], row["idempotency_key"]))
            dependencies.setdefault(row["operation_id"], []).append(key)
    try:
        for row in relations["public.extension_dispatch_withdrawal_receipt"]:
            ledger._charge(rows=1, node_count=16)
            parent = parents.get(row["registration_receipt_id"])
            if (parent is None or (row["org_id"], row["project_id"]) != scope.key
                    or parent["installation_id"] != UUID(installation_id)
                    or parent["group_id"] in groups or row["idempotency_key"] in keys
                    or row["registration_receipt_id"] in origins or row["receipt_id"] in receipts):
                _invalid()
            _model_work(parent["payload"], ledger, 16)
            _model_work(row["payload"], ledger, 16)
            body = decode_withdrawal_receipt(dict(row), registration_row=dict(parent), scope=scope)
            _snapshot9(body["oldDispatchSnapshot"], parent["group_id"], ledger)
            request = RegistrationWithdrawalRequest.model_validate(body["request"])
            created = _scalar(body["createdAt"], "timestamp with time zone!", ledger)
            parent_created = _scalar(parent["payload"]["createdAt"], "timestamp with time zone!", ledger)
            if (canonical_sha256(body["request"]) != row["request_hash"]
                    or parent_created > parent["created_at"] or parent["created_at"] > created
                    or created > row["created_at"]
                    or not parent["payload"]["request"]["installationRef"]["revision"]
                        <= request.expectedInstallationEtag <= current_revision):
                _invalid()
            keys.add(row["idempotency_key"]); origins.add(row["registration_receipt_id"])
            receipts[row["receipt_id"]] = row
            etags[row["receipt_id"]] = request.expectedInstallationEtag
            matches = []
            for item in body["oldDispatchSnapshot"]:
                values = dependencies.get(item["operationId"], ())
                ledger._charge(rows=len(values), node_count=4 * len(values))
                matches.extend(values)
            observed[row["registration_receipt_id"]] = tuple(sorted(matches))
        pending = tuple(sorted(origins))
        return _WithdrawalHistory(MappingProxyType(receipts), pending, pending, MappingProxyType(etags), MappingProxyType(observed))
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        _invalid()


@dataclass(frozen=True, slots=True)
class _PredecessorWithdrawalHistory:
    registrations: _PredecessorRegistrationHistory
    histories: Mapping
    pending_runtime_targets: tuple
    remaining_receipt_ids: tuple


def _predecessor_withdrawal_history(facts, registrations, *, scope, ledger):
    """Read actual old withdrawal parents and all projected operation dependencies."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(registrations) is not _PredecessorRegistrationHistory
            or registrations.runtime.timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    p = facts.predecessors; runtime = registrations.runtime; histories = {}
    ledger._charge(rows=len(p["public.extension_dispatch_withdrawal_receipt"]), node_count=4)
    remaining = {row["receipt_id"] for row in p["public.extension_dispatch_withdrawal_receipt"]}
    try:
        if set(registrations.histories) != set(runtime.terminals):
            _invalid()
        for target, terminal in runtime.terminals.items():
            installation_id, generation = target
            record = terminal.protocol.verification.preparations.record
            names = ("public.extension_dispatch_registration_receipt", "public.extension_dispatch_withdrawal_receipt")
            ledger._charge(rows=sum(len(p[name]) for name in names), node_count=8)
            parents = tuple(row for row in p[names[0]] if row["installation_id"] == installation_id)
            parent_ids = {row["receipt_id"] for row in parents}
            rows = tuple(row for row in p[names[1]] if row["registration_receipt_id"] in parent_ids
                or (type(row["payload"]) is dict and row["payload"].get("installationId") == str(installation_id)))
            relations = MappingProxyType({names[0]: parents, names[1]: rows,
                "public.extension_dispatch_cutover_operation": p["public.extension_dispatch_cutover_operation"],
                "public.automation_schedule_binding": p["public.automation_schedule_binding"],
                "public.ecommerce_growth_runtime_command_receipt": p["public.ecommerce_growth_runtime_command_receipt"],
            })
            history = _withdrawal_history_rows(relations, scope=scope, installation_id=str(installation_id),
                current_revision=record.current_revision, ledger=ledger)
            histories[target] = history
            remaining.difference_update(history.receipts)
        return _PredecessorWithdrawalHistory(registrations, MappingProxyType(histories),
            registrations.pending_runtime_targets, tuple(sorted(remaining)))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid predecessor withdrawal origin facts") from None


@dataclass(frozen=True, slots=True)
class _WithdrawalInstallationPins:
    withdrawals: _WithdrawalHistory
    matched: Mapping
    pending_installation_etags: Mapping
    pending_dependency_origins: tuple


def _withdrawal_installation_pins(relations, withdrawals, *, scope, installation_id, installation_pk, revisions, ledger):
    """Compare immutable origin refs to actual saved rows; historical CAS remains pending."""
    if (type(withdrawals) is not _WithdrawalHistory or type(scope) is not TenantScope
            or type(installation_id) is not str or type(installation_pk) is not UUID
            or type(ledger) is not _WorkLedger):
        _invalid()
    names = ("public.extension_dispatch_registration_receipt", "public.extension_dispatch_withdrawal_receipt")
    ledger._charge(rows=sum(len(relations[name]) for name in names) + len(revisions), node_count=8)
    parents = {row["receipt_id"]: row for row in relations[names[0]]}
    receipts = {row["receipt_id"]: row for row in relations[names[1]]}
    for row in revisions:
        if (row["org_id"], row["project_id"]) != scope.key or row["installation_pk"] != installation_pk:
            _invalid()
    matched = {}
    try:
        for receipt_id, row in withdrawals.receipts.items():
            ledger._charge(rows=1, node_count=16)
            if receipts.get(receipt_id) is not row:
                _invalid()
            parent = parents[row["registration_receipt_id"]]
            _model_work(parent["payload"], ledger, 12)
            origin = decode_registration_receipt(dict(parent), scope=scope)
            if origin["installationId"] != installation_id:
                _invalid()
            request = FirstDispatchRegistrationRequest.model_validate(origin["request"])
            matched[receipt_id] = _registration_installation_pin(request,
                installation_id=installation_id, installation_revision=request.installationRef.revision,
                revisions=revisions, ledger=ledger)
        return _WithdrawalInstallationPins(withdrawals, MappingProxyType(matched),
            withdrawals.pending_installation_etags, withdrawals.pending_dependency_origins)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid withdrawal installation origin facts") from None


@dataclass(frozen=True, slots=True)
class _PredecessorWithdrawalInstallationPins:
    withdrawals: _PredecessorWithdrawalHistory
    histories: Mapping
    remaining_receipt_ids: tuple


def _predecessor_withdrawal_installations(facts, withdrawals, *, scope, ledger):
    _check_predecessor_scope(facts, scope, ledger)
    if (type(withdrawals) is not _PredecessorWithdrawalHistory
            or withdrawals.registrations.runtime.timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    runtime = withdrawals.registrations.runtime; p = facts.predecessors; histories = {}
    if set(withdrawals.histories) != set(runtime.terminals):
        _invalid()
    try:
        for target, history in withdrawals.histories.items():
            installation_id, generation = target
            record = runtime.terminals[target].protocol.verification.preparations.record
            ledger._charge(rows=len(p["public.bundle_installation"]) + len(p["public.bundle_installation_revision"]), node_count=8)
            head = _one([row for row in p["public.bundle_installation"] if row["installation_id"] == installation_id])
            if record.installation_id != str(installation_id):
                _invalid()
            revisions = tuple(row for row in p["public.bundle_installation_revision"] if row["installation_pk"] == head["installation_pk"])
            histories[target] = _withdrawal_installation_pins(p, history, scope=scope,
                installation_id=record.installation_id, installation_pk=head["installation_pk"], revisions=revisions, ledger=ledger)
        return _PredecessorWithdrawalInstallationPins(withdrawals, MappingProxyType(histories), withdrawals.remaining_receipt_ids)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid predecessor withdrawal installation pins") from None


@dataclass(frozen=True, slots=True)
class _SuccessorHandoverGraph:
    registrations: _RegistrationHistory
    predecessors: _PredecessorLifecycleGraph
    matched: Mapping
    pending_refs: Mapping
    unused_detach_receipts: tuple
    pending_old_registration_refs: Mapping


def _successor_detach_match(row, expected_ref, predecessors, rows, *, scope, installation_id, ledger):
    """Original successor/detach row proof shared by current and ancestor callers."""
    if ((row["org_id"], row["project_id"]) != scope.key or str(row["installation_id"]) != installation_id):
        _invalid()
    _model_work(row["payload"], ledger, 12)
    body = decode_successor_receipt(dict(row), scope=scope)
    request = SuccessorDispatchRegistrationRequest.model_validate(body["request"])
    ref = request.predecessorDetachReceiptRef
    if (expected_ref != ref
            or canonical_sha256(body["request"]) != row["request_hash"]):
        _invalid()
    _snapshot9(body["dispatchSnapshot"], row["group_id"], ledger)
    created = _scalar(body["createdAt"], "timestamp with time zone!", ledger)
    if created > row["created_at"]:
        _invalid()
    detach_id = UUID(ref.resourceId)
    parent_id = predecessors.by_detach.get(detach_id)
    if parent_id is None:
        return None
    pair = predecessors.pairs[parent_id]; life = predecessors.lifecycles[parent_id]
    binding = predecessors.bindings[parent_id]
    ledger._charge(rows=len(rows), node_count=8)
    actual = _one([r for r in rows if r["receipt_id"] == detach_id and r["phase"] == "detach"])
    expected_snapshot = list(map(dict, pair.detach.dispatch_snapshot))
    _model_work(expected_snapshot, ledger, 2)
    if (pair.detach.content_hash != ref.contentHash or actual["content_hash"] != ref.contentHash
            or str(binding["installation_id"]) == installation_id
            or life["cutover_group_id"] != row["group_id"]
            or request.expectedGroupRevision != life["fenced_group_revision"] + 1
            or canonical_sha256(body["dispatchSnapshot"]) != canonical_sha256(expected_snapshot)
            or created < actual["created_at"]):
        _invalid()
    return parent_id


def _successor_predecessor_history(facts, registrations, predecessors, *, scope, source, ledger):
    """Join actual detach references; this leaf never discharges old authority obligations."""
    if (type(facts) is not _DecodedFacts or type(registrations) is not _RegistrationHistory
            or type(predecessors) is not _PredecessorLifecycleGraph or type(scope) is not TenantScope
            or type(source) is not ReinstallSourceRef or type(ledger) is not _WorkLedger
            or predecessors.cutovers.partition is not facts.predecessors):
        _invalid()
    matched = {}; pending = {}; used = set(); old_origins = {}
    for history in predecessors.cutovers.histories.values():
        ledger._charge(rows=len(history.activations), node_count=4 * len(history.activations))
        for identity, root in history.activations.items():
            ref = root.prepared.receipt.registration_receipt_ref
            if ref is not None:
                old_origins[identity] = ref
    try:
        for row in facts.relations["public.extension_dispatch_successor_registration_receipt"]:
            ledger._charge(rows=1, node_count=16)
            parent_id = _successor_detach_match(row, registrations.pending_predecessors.get(row["receipt_id"]),
                predecessors, facts.predecessors["public.extension_dispatch_lifecycle_receipt"],
                scope=scope, installation_id=source.installation_id, ledger=ledger)
            ref = registrations.pending_predecessors[row["receipt_id"]]
            detach_id = UUID(ref.resourceId)
            if parent_id is None:
                pending[row["receipt_id"]] = ref
                continue
            matched[row["receipt_id"]] = parent_id; used.add(detach_id)
        return _SuccessorHandoverGraph(registrations, predecessors, MappingProxyType(matched), MappingProxyType(pending),
            tuple(sorted(set(predecessors.by_detach) - used)), MappingProxyType(old_origins))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid terminal facts") from None


def _ancestor_dependency_order(dependencies, ledger):
    """Bounded parent-first order; cycle detection never relies on timestamps or recursion."""
    if type(ledger) is not _WorkLedger or not isinstance(dependencies, Mapping):
        _invalid()
    counts = {}; children = {}
    for target, parents in dependencies.items():
        ledger._charge(rows=1, node_count=4)
        counts.setdefault(target, 0); children.setdefault(target, set())
        for parent in parents:
            ledger._charge(rows=1, node_count=6)
            counts.setdefault(parent, 0); children.setdefault(parent, set())
            if target not in children[parent]:
                children[parent].add(target); counts[target] += 1
    ordered = sorted(target for target, count in counts.items() if count == 0)
    offset = 0
    while offset < len(ordered):
        target = ordered[offset]; offset += 1
        ledger._charge(rows=1, node_count=3)
        for child in sorted(children[target]):
            ledger._charge(rows=1, node_count=3)
            counts[child] -= 1
            if counts[child] == 0:
                ordered.append(child)
    if len(ordered) != len(counts):
        _invalid()
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class _PredecessorSuccessorGraph:
    registrations: _PredecessorRegistrationHistory
    lifecycle: _PredecessorLifecycleGraph
    matched: Mapping
    pending_refs: Mapping
    ancestry_resolved_targets: tuple
    remaining_receipt_ids: tuple


def _predecessor_successor_history(facts, registrations, lifecycle, *, scope, ledger):
    """Resolve only ancestor links proved by the same original runtime and receipt parents."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(registrations) is not _PredecessorRegistrationHistory
            or type(lifecycle) is not _PredecessorLifecycleGraph
            or registrations.runtime.timeline.controls.refreshes.lifecycle is not lifecycle
            or lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    pending = dict(registrations.pending_predecessors); matched = {}; used = set()
    dependencies = {target: set() for target in registrations.histories}
    p = facts.predecessors
    rows = p["public.extension_dispatch_successor_registration_receipt"]
    ledger._charge(rows=len(rows) + len(dependencies), node_count=4 * len(dependencies))
    actual = {row["receipt_id"]: row for row in rows}
    try:
        for key, ref in registrations.pending_predecessors.items():
            installation, generation, receipt_id = key; target = (installation, generation)
            ledger._charge(rows=1, node_count=12)
            history = registrations.histories[target]; row = actual[receipt_id]
            if (row["installation_id"] != installation or row["generation"] != generation
                    or history.pending_predecessors.get(receipt_id) != ref):
                _invalid()
            parent_id = _successor_detach_match(row, ref, lifecycle,
                p["public.extension_dispatch_lifecycle_receipt"], scope=scope,
                installation_id=str(installation), ledger=ledger)
            used.add(receipt_id)
            if parent_id is not None:
                binding = lifecycle.bindings[parent_id]
                parent = (binding["installation_id"], binding["generation"])
                dependencies[target].add(parent); matched[key] = parent
        resolved = set()
        for target in _ancestor_dependency_order(dependencies, ledger):
            history = registrations.histories.get(target)
            if history is None or history.pending_control_roots:
                continue
            ledger._charge(rows=len(history.pending_predecessors), node_count=4)
            keys = [(target[0], target[1], receipt_id) for receipt_id in history.pending_predecessors]
            if all(key in matched and matched[key] in resolved for key in keys):
                resolved.add(target)
                for key in keys:
                    pending.pop(key, None)
        return _PredecessorSuccessorGraph(registrations, lifecycle, MappingProxyType(matched),
            MappingProxyType(pending), tuple(sorted(resolved)), tuple(sorted(set(actual) - used)))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid predecessor successor facts") from None


def _registry_identity_index(facts, ledger):
    if type(facts) is not _DecodedFacts or type(ledger) is not _WorkLedger:
        _invalid()
    bundles = {}; names = set(); versions = {}; version_ids = set(); artifacts = {}
    for row in facts.registry["public.asset_bundle"]:
        ledger._charge(rows=1, node_count=6)
        name = row["publisher"], row["bundle_id"]
        if row["bundle_pk"] in bundles or name in names:
            _invalid()
        bundles[row["bundle_pk"]] = row; names.add(name)
    for row in facts.registry["public.asset_bundle_version"]:
        ledger._charge(rows=1, node_count=8)
        parent = bundles.get(row["bundle_pk"])
        if parent is None:
            _invalid()
        coordinate = parent["publisher"], parent["bundle_id"], row["version"]
        if coordinate in versions or row["version_pk"] in version_ids:
            _invalid()
        versions[coordinate] = row; version_ids.add(row["version_pk"])
    for row in facts.registry["public.asset_bundle_artifact"]:
        ledger._charge(rows=1, node_count=5)
        key = row["version_pk"], row["relative_path"]
        if row["version_pk"] not in version_ids or key in artifacts:
            _invalid()
        artifacts[key] = row
    return bundles, versions, artifacts


@dataclass(frozen=True, slots=True)
class _RegistrySelectionCoverage:
    control: _DetachedControlGraph
    predecessor_runtime: _PredecessorRuntimeClosure
    registry: Mapping
    targets: Mapping
    remaining: Mapping


def _registry_selection_coverage(facts, control, predecessor_runtime, *, scope, ledger):
    _check_predecessor_scope(facts, scope, ledger)
    if (type(control) is not _DetachedControlGraph or type(predecessor_runtime) is not _PredecessorRuntimeClosure
            or predecessor_runtime.timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    current = control.timeline.history.graph.receipt.context
    binding = current.binding; prepared = current.notifications.preparation_facts
    rows = facts.relations["public.extension_runtime_operation"]
    ledger._charge(rows=len(rows) + len(prepared.operations), node_count=4 * len(rows))
    actual_operations = {row["operation_id"]: row for row in rows}
    if (set(actual_operations) != set(prepared.operations)
            or any(actual_operations[identity] is not row for identity, row in prepared.operations.items())):
        _invalid()
    if prepared.record.installation_id != str(binding["installation_id"]):
        _invalid()
    selections = {(binding["installation_id"], binding["generation"]): prepared.contents}
    for target, terminal in predecessor_runtime.terminals.items():
        ledger._charge(rows=1, node_count=6)
        verification = terminal.protocol.verification
        if verification.partition is not facts.predecessors:
            _invalid()
        contents = verification.preparations.contents
        if target in selections and selections[target] != contents:
            _invalid()
        selections[target] = contents
    bundles, versions, artifacts = _registry_identity_index(facts, ledger)
    used_bundles = set(); used_versions = set(); targets = {}
    try:
        for target, contents in selections.items():
            selected = []
            for content in contents:
                ledger._charge(rows=1, node_count=8)
                if type(content) is not _SelectedContent:
                    _invalid()
                node = content.selected; coordinate = node.publisher, node.id, node.version
                actual = versions[coordinate]
                if actual["content_hash"] != node.content_hash:
                    _invalid()
                used_bundles.add(actual["bundle_pk"]); used_versions.add(actual["version_pk"])
                selected.append(actual["version_pk"])
            targets[target] = tuple(sorted(selected))
        remaining = {
            "public.asset_bundle": tuple(sorted((identity,) for identity in set(bundles) - used_bundles)),
            "public.asset_bundle_version": tuple(sorted((row["version_pk"],) for row in versions.values() if row["version_pk"] not in used_versions)),
            "public.asset_bundle_artifact": tuple(sorted(key for key in artifacts if key[0] not in used_versions)),
        }
        return _RegistrySelectionCoverage(control, predecessor_runtime, facts.registry,
            MappingProxyType(targets), MappingProxyType(remaining))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid registry selection coverage") from None


@dataclass(frozen=True, slots=True)
class _PredecessorProofCoverage:
    runtime: _PredecessorRuntimeClosure
    covered_pairs: Mapping
    remaining_disable_operations: tuple
    remaining_timeline_operations: tuple
    remaining_refresh_control_operations: Mapping
    remaining_installation_refs: Mapping
    remaining_cutover_operations: tuple
    remaining_runtime_operations: tuple


def _predecessor_proof_coverage(facts, runtime, *, scope, ledger):
    """Join only actual completed old proof parents; retain every unresolved obligation."""
    _check_predecessor_scope(facts, scope, ledger)
    if (type(runtime) is not _PredecessorRuntimeClosure
            or runtime.timeline.controls.refreshes.lifecycle.cutovers.partition is not facts.predecessors):
        _invalid()
    timeline = runtime.timeline; controls = timeline.controls; refreshes = controls.refreshes
    lifecycle = refreshes.lifecycle; p = facts.predecessors
    remaining_disable = set(lifecycle.pending_control_operations)
    remaining_timeline = set(controls.pending_timeline)
    remaining_refresh = dict(refreshes.pending_control_operations)
    remaining_installed = dict(refreshes.pending_installation_refs)
    covered = {}
    try:
        for identity, binding in lifecycle.bindings.items():
            ledger._charge(rows=1, node_count=16)
            target = binding["installation_id"], binding["generation"]
            terminal = runtime.terminals.get(target)
            if terminal is None:
                continue
            verification = terminal.protocol.verification
            if (terminal.timeline is not timeline or verification.partition is not facts.predecessors
                    or verification.binding != binding or target not in timeline.timelines):
                _invalid()
            history = controls.histories[target]
            if controls.linked_disables.get(identity) is not history.commits.get(identity):
                _invalid()
            if identity not in controls.linked_disables:
                _invalid()
            root = lifecycle.lifecycles[identity]["activation_operation_id"]
            chain = refreshes.chains[root]
            if refreshes.detached.get(identity) != root:
                _invalid()
            references = tuple(operation for step in chain.steps for operation in
                (UUID(step.request.configure_operation_id), UUID(step.request.enable_operation_id)))
            if (controls.linked_refresh_operations.get(identity) != references
                    or remaining_refresh.get(identity, ()) != references
                    or remaining_installed.get(identity, ()) != tuple(step.request.installation_ref for step in chain.steps)):
                _invalid()
            ledger._charge(rows=len(p["public.bundle_installation"]) + len(p["public.bundle_installation_revision"]), node_count=8)
            head = _one([row for row in p["public.bundle_installation"] if row["installation_id"] == target[0]])
            rows = tuple(row for row in p["public.bundle_installation_revision"] if row["installation_pk"] == head["installation_pk"])
            expected = _installed_revision_ref(str(target[0]), binding["installation_revision"], rows, ledger)
            for step in chain.steps:
                ledger._charge(rows=1, node_count=6)
                if step.request.wire()["installationRef"] != expected:
                    _invalid()
            covered[identity] = target
            remaining_disable.discard(identity); remaining_timeline.discard(identity)
            remaining_refresh.pop(identity, None); remaining_installed.pop(identity, None)
        return _PredecessorProofCoverage(runtime, MappingProxyType(covered), tuple(sorted(remaining_disable)),
            tuple(sorted(remaining_timeline)), MappingProxyType(remaining_refresh), MappingProxyType(remaining_installed),
            lifecycle.pending_cutover_operations, runtime.remaining_operations)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("invalid predecessor joint proof") from None


@dataclass(frozen=True, slots=True)
class _DetachedRegistrationGraph:
    control: _DetachedControlGraph
    registrations: _RegistrationHistory
    withdrawals: _WithdrawalHistory
    commands: _RuntimeCommandHistory
    pending_predecessor_input: Mapping
    predecessor_cutovers: _PredecessorCutoverGraph
    predecessor_lifecycles: _PredecessorLifecycleGraph
    successor_handover: _SuccessorHandoverGraph
    predecessor_refreshes: _PredecessorRefreshGraph
    predecessor_controls: _PredecessorControlGraph
    predecessor_timeline: _PredecessorBindingTimelineGraph

    predecessor_runtime: _PredecessorRuntimeClosure

    predecessor_registrations: _PredecessorRegistrationHistory

    predecessor_withdrawals: _PredecessorWithdrawalHistory

    predecessor_successors: _PredecessorSuccessorGraph

    withdrawal_installations: _WithdrawalInstallationPins

    predecessor_withdrawal_installations: _PredecessorWithdrawalInstallationPins

    registry_coverage: _RegistrySelectionCoverage

    predecessor_proofs: _PredecessorProofCoverage


def _detached_registration_history(facts, *, scope, source, locked_source, source_lock, ledger, predecessor_locks=None):
    _check_predecessor_scope(facts, scope, ledger)
    _registry_identity_index(facts, ledger)
    selected_registry = _registry_selection_view(facts, _checked_lock(source_lock, ledger), ledger)
    current_facts = _DecodedFacts(facts.relations, selected_registry.registry, facts.predecessors)
    control = _detached_control_timeline(current_facts, scope=scope, source=source,
        locked_source=locked_source, source_lock=source_lock, ledger=ledger)
    registrations = _registration_history(facts, control.joined.cutovers, control.timeline.history,
        scope=scope, source=source, ledger=ledger)
    commands = _runtime_command_history(facts, scope=scope, ledger=ledger)
    withdrawals = _withdrawal_history(facts, control.joined.cutovers, scope=scope, source=source, ledger=ledger)
    predecessor_cutovers = _predecessor_cutover_history(facts, scope=scope, ledger=ledger)
    predecessor_lifecycles = _predecessor_lifecycle_history(facts, predecessor_cutovers, scope=scope, ledger=ledger)
    successor_handover = _successor_predecessor_history(facts, registrations, predecessor_lifecycles, scope=scope, source=source, ledger=ledger)
    predecessor_refreshes = _predecessor_refresh_history(facts, predecessor_lifecycles, scope=scope, ledger=ledger)
    predecessor_controls = _predecessor_control_history(facts, predecessor_refreshes, scope=scope, ledger=ledger)
    predecessor_timeline = _predecessor_binding_timeline(facts, predecessor_controls, scope=scope, ledger=ledger)
    predecessor_runtime = _predecessor_runtime_closure(facts, predecessor_timeline, scope=scope,
        predecessor_locks=predecessor_locks, ledger=ledger)
    predecessor_registrations = _predecessor_registration_history(facts, predecessor_runtime, scope=scope, ledger=ledger)
    predecessor_withdrawals = _predecessor_withdrawal_history(facts, predecessor_registrations, scope=scope, ledger=ledger)
    predecessor_successors = _predecessor_successor_history(facts, predecessor_registrations, predecessor_lifecycles, scope=scope, ledger=ledger)
    withdrawal_installations = _withdrawal_installation_pins(facts.relations, withdrawals, scope=scope,
        installation_id=source.installation_id, installation_pk=locked_source.installation_pk,
        revisions=facts.relations["public.bundle_installation_revision"], ledger=ledger)
    predecessor_withdrawal_installations = _predecessor_withdrawal_installations(facts, predecessor_withdrawals, scope=scope, ledger=ledger)
    registry_coverage = _registry_selection_coverage(facts, control, predecessor_runtime, scope=scope, ledger=ledger)
    predecessor_proofs = _predecessor_proof_coverage(facts, predecessor_runtime, scope=scope, ledger=ledger)
    return _DetachedRegistrationGraph(control, registrations, withdrawals, commands, facts.predecessors, predecessor_cutovers, predecessor_lifecycles, successor_handover, predecessor_refreshes, predecessor_controls, predecessor_timeline, predecessor_runtime, predecessor_registrations, predecessor_withdrawals, predecessor_successors, withdrawal_installations, predecessor_withdrawal_installations, registry_coverage, predecessor_proofs)


def _check_predecessor_scope(facts, scope, ledger):
    if type(facts) is not _DecodedFacts or type(scope) is not TenantScope or type(ledger) is not _WorkLedger:
        _invalid()
    for family, rows in facts.predecessors.items():
        schema = _PREDECESSOR_RELATIONS[family]
        current = facts.relations.get(family, ())
        ledger._charge(rows=len(current), node_count=2 * len(current))
        index = {tuple(r[k] for k in schema.key): r for r in current}
        for row in rows:
            ledger._charge(rows=1, node_count=2 + len(schema.key))
            if (row["org_id"], row["project_id"]) != scope.key:
                _invalid()
            shared = index.get(tuple(row[k] for k in schema.key))
            if shared is not None:
                for column, descriptor in _RELATIONS[family].columns:
                    # Only fields actually projected on both sides can be compared.
                    # Old-only context still requires ancestor history verification.
                    ledger._charge(node_count=2)
                    if descriptor.startswith("jsonb"):
                        _model_work(row[column], ledger, 2); _model_work(shared[column], ledger, 2)
                        if canonical_sha256(row[column]) != canonical_sha256(shared[column]):
                            _invalid()
                    elif row[column] != shared[column]:
                        _invalid()


    # The a0v166 activation-scoped PK does not relax the original global
    # receipt identity or per-group idempotency uniqueness across partitions.
    family = "public.extension_dispatch_configuration_refresh_receipt"
    receipts = {}; commands = {}
    for rows in (facts.relations[family], facts.predecessors[family]):
        for row in rows:
            ledger._charge(rows=1, node_count=10)
            identity = tuple(row[k] for k in _RELATIONS[family].key)
            receipt = (row["org_id"], row["project_id"], row["receipt_id"])
            command = (row["org_id"], row["project_id"], row["cutover_group_id"], row["idempotency_key"])
            if ((receipt in receipts and receipts[receipt] != identity)
                    or (command in commands and commands[command] != identity)):
                _invalid()
            receipts[receipt] = identity; commands[command] = identity


def _source_selection(facts, scope, source_lock, ledger):
    if (type(facts) is not _DecodedFacts or type(scope) is not TenantScope or
            type(source_lock) is not StoredCompositionLock or type(ledger) is not _WorkLedger):
        _invalid()
    scope = TenantScope(scope.org_id, scope.project_id)
    _check_predecessor_scope(facts, scope, ledger)
    checked = _checked_lock(source_lock, ledger)
    for rows in facts.relations.values():
        for row in rows:
            ledger._charge(rows=1, node_count=2)
            if (row["org_id"], row["project_id"]) != scope.key:
                _invalid()
    composition = _one(facts.relations["public.bundle_composition"])
    locked = _one(facts.relations["public.bundle_composition_lock"])
    return _check_composition_lock_rows(composition, locked, scope=scope, checked=checked, ledger=ledger)


def _check_composition_lock_rows(composition, locked, *, scope, checked, ledger):
    if ((composition["org_id"], composition["project_id"]) != scope.key
            or (locked["org_id"], locked["project_id"]) != scope.key):
        _invalid()
    if (composition["composition_pk"] != locked["composition_pk"] or
            str(composition["composition_id"]) != checked.composition_id or locked["revision"] != checked.revision or
            composition["registry_snapshot_hash"] != checked.payload.registry_snapshot_hash):
        _invalid()
    for name in ("lock_hash", "permission_diff_hash", "migration_plan_hash", "contribution_diff_hash"):
        ledger._charge(node_count=1)
        if locked[name] != getattr(checked, name):
            _invalid()
    _model_work(locked["lock_payload"], ledger, 4)
    payload = CompositionLockPayload.model_validate_json(json.dumps(locked["lock_payload"], ensure_ascii=False, allow_nan=False))
    if payload != checked.payload:
        _invalid()
    for name in ("permission_diff", "migration_plan", "contribution_diff"):
        expected = getattr(payload, name).model_dump(mode="json", by_alias=True, exclude_none=False)
        _model_work(expected, ledger, 2)
        if locked[name + "_json"] != expected:
            _invalid()
    raw_snapshot = composition["registry_snapshot_json"]
    _model_work(raw_snapshot, ledger, 16)
    snapshot = _snapshot_from_json(raw_snapshot)
    if snapshot.snapshot_hash != composition["registry_snapshot_hash"]:
        _invalid()
    index = {}
    for candidate in snapshot.candidates:
        ledger._charge(rows=1, node_count=3)
        key = candidate.publisher, candidate.id, candidate.version
        if key in index:
            _invalid()
        index[key] = candidate
    for selected in checked.payload.resolved:
        ledger._charge(rows=1, node_count=3)
        candidate = index.get((selected.publisher, selected.id, selected.version))
        if candidate is None:
            _invalid()
        _model_work(candidate.model_dump(mode="json", by_alias=True, exclude_none=False), ledger, 4)
        if _to_resolved_bundle(candidate, selection_reason=selected.selection_reason) != selected:
            _invalid()
    return checked, index


@dataclass(frozen=True, slots=True)
class _SelectedContent:
    selected: object
    manifest: BundleManifest
    description: RegistrationDescription | None
    claims_hash: str | None
    registration_fingerprint: str | None


def _registry_content(facts, checked, candidate_index, ledger):
    selected = {(node.publisher, node.id, node.version): node for node in checked.payload.resolved}
    bundles = {}
    coordinates = set()
    for row in facts.registry["public.asset_bundle"]:
        ledger._charge(rows=1, node_count=3)
        coordinate = row["publisher"], row["bundle_id"]
        if coordinate in coordinates or row["bundle_pk"] in bundles:
            _invalid()
        coordinates.add(coordinate)
        bundles[row["bundle_pk"]] = row
    versions = {}
    used_bundles = set()
    by_version_pk = {}
    for row in facts.registry["public.asset_bundle_version"]:
        ledger._charge(rows=1, node_count=4)
        parent = bundles.get(row["bundle_pk"])
        if parent is None:
            _invalid()
        coordinate = parent["publisher"], parent["bundle_id"], row["version"]
        if coordinate not in selected or coordinate in versions or row["version_pk"] in by_version_pk:
            _invalid()
        if row["content_hash"] != selected[coordinate].content_hash:
            _invalid()
        versions[coordinate] = row
        by_version_pk[row["version_pk"]] = coordinate
        used_bundles.add(row["bundle_pk"])
    if set(versions) != set(selected) or used_bundles != set(bundles):
        _invalid()
    artifacts = {pk: [] for pk in by_version_pk}
    artifact_keys = set()
    for row in facts.registry["public.asset_bundle_artifact"]:
        ledger._charge(rows=1, node_count=5)
        key = row["version_pk"], row["relative_path"]
        if row["version_pk"] not in artifacts or key in artifact_keys:
            _invalid()
        artifact_keys.add(key)
        item = {"relativePath": row["relative_path"], "digest": row["digest"],
                "size": row["size"], "mediaType": row["media_type"]}
        _model_work(item, ledger, 4)
        parsed = _parse_artifacts([item])[0]
        # Original field validators, without inventing an artifact_ref or changing order.
        if len(parsed["relativePath"]) > 1024 or len(parsed["mediaType"]) > 255:
            _invalid()
        if (BundleArtifact._safe_relative_path(parsed["relativePath"]) != parsed["relativePath"] or
                BundleArtifact._normalized_media_type(parsed["mediaType"]) != parsed["mediaType"]):
            _invalid()
        artifacts[row["version_pk"]].append(parsed)
    result = []
    for node in checked.payload.resolved:
        coordinate = node.publisher, node.id, node.version
        row = versions[coordinate]
        parent = bundles[row["bundle_pk"]]
        persisted = row["manifest_json"]
        _model_work(persisted, ledger, 4)
        manifest = BundleManifest.model_validate(persisted)
        if ((manifest.metadata.publisher, manifest.metadata.id, manifest.metadata.version) != coordinate or
                manifest.kind != parent["kind"] or manifest.kind != node.kind or
                manifest != candidate_index[coordinate].manifest):
            _invalid()
        original_artifacts = artifacts[row["version_pk"]]
        _model_work({"manifest": manifest.model_dump(mode="json", by_alias=True, exclude_none=False),
                     "artifacts": original_artifacts}, ledger, 16)
        verify_content_descriptor(manifest=manifest, artifacts=original_artifacts,
                                  content_hash=node.content_hash, persisted_manifest=persisted)
        description = None
        claims_hash = None
        fingerprint = None
        if manifest.spec.runtime is not None and manifest.spec.runtime.backend is not None:
            description = RegistrationDescription(contributions=manifest.spec.contributions)
            body = description.model_dump(mode="json", by_alias=True)
            _model_work(body, ledger, 8)
            claims_hash = _digest(body)
            fingerprint = registration_fingerprint(description)
        result.append(_SelectedContent(node, manifest, description, claims_hash, fingerprint))
    return tuple(result)


def _verify_source_packages(facts, scope, source_lock, ledger):
    """Associate stored selection and content only; never authenticates history."""
    try:
        checked, candidates = _source_selection(facts, scope, source_lock, ledger)
        return _registry_content(facts, checked, candidates, ledger)
    except (ValueError, TypeError, OverflowError, AssetRegistryError):
        raise ValueError("invalid terminal source package facts") from None


# Original predicate, with only its two fixed catalog joins schema-qualified.
_CONTENT_SOURCE_PREDICATE = legacy_content_predicate('composition_lock')
for _before, _after in (
    ('JOIN asset_bundle boundary_bundle', 'JOIN public.asset_bundle boundary_bundle'),
    ('JOIN asset_bundle_version boundary_version', 'JOIN public.asset_bundle_version boundary_version'),
):
    if _CONTENT_SOURCE_PREDICATE.count(_before) != 1:
        raise RuntimeError('original content predicate dependency changed')
    _CONTENT_SOURCE_PREDICATE = _CONTENT_SOURCE_PREDICATE.replace(_before, _after)
_CONTENT_SOURCE_SQL = f"""SELECT {_CONTENT_SOURCE_PREDICATE} AS eligible
FROM public.bundle_composition_lock AS composition_lock
JOIN public.bundle_composition AS composition
  ON composition.org_id=composition_lock.org_id
 AND composition.project_id=composition_lock.project_id
 AND composition.composition_pk=composition_lock.composition_pk
WHERE composition.org_id=pg_catalog.current_setting('aos.org_id',true)
  AND composition.project_id=pg_catalog.current_setting('aos.project_id',true)
  AND composition.composition_id=%s AND composition_lock.revision=%s
  AND composition_lock.lock_hash=%s"""
_SOURCE_FACTS_SQL = 'SELECT public.reinstall_terminal_source_facts_v1(%s, %s, %s, %s) AS facts'


def _require_detached_port_obligations(graph, facts, ledger):
    """Unresolved history stays a refusal; this candidate does not grant missing provenance."""
    old = graph.predecessor_runtime
    remaining = (
        graph.control.joined.refresh.remaining_receipt_ids,
        graph.registrations.unconsumed, graph.registrations.pending_control_roots,
        graph.withdrawals.pending_dependency_origins, graph.withdrawals.pending_installation_etags,
        graph.commands.pending_dispatch_sources, graph.commands.pending_target_refs,
        graph.successor_handover.pending_refs, graph.predecessor_refreshes.remaining_receipt_ids,
        old.pending_locks, old.pending_preparations, old.remaining_operations,
        graph.predecessor_registrations.pending_runtime_targets, graph.predecessor_registrations.remaining_origin_refs,
        graph.predecessor_successors.pending_refs, graph.predecessor_successors.remaining_receipt_ids,
        graph.predecessor_withdrawals.pending_runtime_targets, graph.predecessor_withdrawals.remaining_receipt_ids,
        graph.predecessor_withdrawal_installations.remaining_receipt_ids,
        graph.predecessor_proofs.remaining_disable_operations, graph.predecessor_proofs.remaining_timeline_operations,
        graph.predecessor_proofs.remaining_refresh_control_operations, graph.predecessor_proofs.remaining_installation_refs,
        graph.predecessor_proofs.remaining_cutover_operations, graph.predecessor_proofs.remaining_runtime_operations,
    )
    ledger._charge(rows=sum(len(value) for value in remaining), node_count=len(remaining))
    if any(remaining) or any(graph.registry_coverage.remaining.values()):
        _invalid()
    if set(graph.registrations.pending_predecessors) != set(graph.successor_handover.matched):
        _invalid()
    used_by_old = {UUID(ref.resourceId) for key, ref in graph.predecessor_registrations.pending_predecessors.items()
        if key in graph.predecessor_successors.matched and key not in graph.predecessor_successors.pending_refs}
    if set(graph.successor_handover.unused_detach_receipts) - used_by_old:
        _invalid()
    for history in graph.predecessor_registrations.histories.values():
        ledger._charge(rows=len(history.unconsumed) + len(history.pending_control_roots), node_count=2)
        if history.unconsumed or history.pending_control_roots:
            _invalid()
    for history in graph.predecessor_withdrawals.histories.values():
        if history.pending_dependency_origins or history.pending_installation_etags:
            _invalid()
    # These histories need their own full provenance joins before this Port can admit them.
    unresolved = ('public.automation_schedule_binding', 'public.automation_occurrence',
        'public.automation_occurrence_dispatch_attempt', 'public.automation_occurrence_outbox',
        'public.extension_event_control_dispatch_receipt', 'public.ecommerce_growth_runtime_command_receipt')
    for name in unresolved:
        if facts.relations[name] or (name in facts.predecessors and facts.predecessors[name]):
            _invalid()
    targets = set(old.terminals)
    heads = facts.predecessors['public.bundle_installation']
    bindings = facts.predecessors['public.extension_runtime_binding']
    ledger._charge(rows=len(heads) + len(bindings), node_count=4)
    if ({row['installation_id'] for row in heads} != {target[0] for target in targets}
            or {(row['installation_id'], row['generation']) for row in bindings} != targets):
        _invalid()


class PostgresTerminalSourceReader:
    """Unwired concrete Port candidate; SQL/native and complex-history qualification remain pending.

    No connector, callback, default identity, transaction ownership or application wiring.
    Refused unresolved histories remain missing capabilities, not completed acceptance.
    """
    __slots__ = ('_appender',)

    def __init__(self, *, appender: PostgresReinstallOriginAppender):
        if type(appender) is not PostgresReinstallOriginAppender:
            raise TypeError('exact original origin appender required')
        self._appender = appender

    def check_current(self, conn, *, org_id: str, project_id: str, actor: str,
            markings: Collection[str], source: ReinstallSourceRef, locked_source: LockedInstallation,
            source_lock: StoredCompositionLock, target: CreateInstallationRequest,
            target_lock: StoredCompositionLock) -> bool:
        _require_transaction(conn)
        if (type(source) is not ReinstallSourceRef or type(locked_source) is not LockedInstallation
                or type(locked_source.record) is not InstallationRecord
                or type(locked_source.installation_pk) is not UUID
                or type(target) is not CreateInstallationRequest
                or type(actor) is not str or not 1 <= len(actor) <= 240
                or actor != actor.strip() or not actor.isprintable()
                or isinstance(markings, (str, bytes)) or not isinstance(markings, Collection)):
            _invalid()
        supplied = tuple(markings)
        if len(supplied) > 500 or any(type(value) is not str or not value or value != value.strip()
                or not value.isprintable() for value in supplied):
            _invalid()
        scope = TenantScope(org_id, project_id); ledger = _WorkLedger()
        try:
            source = ReinstallSourceRef.model_validate(source.model_dump(mode='python', by_alias=True))
            target = CreateInstallationRequest.model_validate(target.model_dump(mode='python', by_alias=True))
            checked_source = _checked_lock(source_lock, ledger); checked_target = _checked_lock(target_lock, ledger)
            record = InstallationRecord.model_validate(locked_source.record.model_dump(mode='python', by_alias=True))
        except (ValueError, TypeError, OverflowError):
            raise ValueError('invalid terminal source inputs') from None
        if ((locked_source.org_id, locked_source.project_id) != scope.key
                or record.installation_id != source.installation_id or record.state != 'uninstalled'
                or type(source.terminal_revision) is not int or not 1 <= source.terminal_revision < 2**63
                or record.current_revision != source.terminal_revision or record.etag_version != source.terminal_revision
                or record.current.lock_hash != source.lock_hash or checked_source.lock_hash != source.lock_hash
                or target.composition_id != checked_target.composition_id or target.lock_revision != checked_target.revision):
            _invalid()
        _read_current_permissions(conn, scope=scope, actor=actor, source_lock=checked_source,
            target_lock=checked_target, ledger=ledger)
        row = conn.execute(_SOURCE_FACTS_SQL, (*scope.key, UUID(source.installation_id), source.terminal_revision)).fetchone()
        if (not isinstance(row, (Mapping, tuple)) or len(row) != 1
                or (isinstance(row, Mapping) and set(row) != {'facts'})):
            _invalid()
        facts = _decode_packet(_values(row, ('facts',))[0], ledger)
        if not facts.relations['public.extension_runtime_binding']:
            _unbound_runtime_source(conn, facts, scope=scope, source=source,
                locked_source=locked_source, source_lock=checked_source, ledger=ledger)
        else:
            receipt = _one(facts.relations['public.extension_runtime_uninstall_receipt'])
            if receipt['retirement_kind'] == 'detached':
                graph = _detached_registration_history(facts, scope=scope, source=source,
                    locked_source=locked_source, source_lock=checked_source, ledger=ledger)
                _require_detached_port_obligations(graph, facts, ledger)
            else:
                _nondispatch_runtime_source(facts, scope=scope, source=source,
                    locked_source=locked_source, source_lock=checked_source, ledger=ledger)
        return True

    def append_origin(self, conn, *, org_id: str, project_id: str, actor: str,
            source: ReinstallSourceRef, locked_source: LockedInstallation,
            target_record: InstallationRecord) -> None:
        _require_transaction(conn)
        result = self._appender.append_origin(conn, org_id=org_id, project_id=project_id,
            actor=actor, source=source, locked_source=locked_source, target_record=target_record)
        if result is not None:
            raise ValueError('original origin append must return synchronous None')
