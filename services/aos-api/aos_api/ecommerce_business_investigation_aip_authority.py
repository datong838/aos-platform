"""Deterministic BI stage, responsibility and Skill-selection authorities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg

from aos_api.aip_contracts import AipContractModel, ResourceRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractConflict,
    ProductionContractNotFound, _require_bi_installation_binding,
    _require_bi_rebind_binding,
)
from aos_api.asset_registry.composition_store import load_stored_lock
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION, CONFIGURE_RUNTIME_OPERATION,
    require_control_role, require_target_markings,
)
from aos_api.asset_registry.errors import AssetRegistryError, LockIntegrityCorruptError
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.auth import Principal
from aos_api.aip_production_contracts import (
    AssigneeKind,
    AssigneeRef,
    BriefLifecycle,
    ContractReadiness,
    CreateResponsibilityPlanRequest,
    CreateStageTemplateRequest,
    ExactRevisionRef,
    ResponsibilityPlanRevision,
    ReviseResponsibilityPlanRequest,
    ResponsibilitySlot,
    StageApplicability,
    StageApplicabilityKind,
    StageDefinition,
    StageTemplateRevision,
)
from aos_api.aip_responsibility_template_authority import (
    ActiveBIBusinessResolver, ApprovedBIPreparationResolver,
    published_template_ref,
)
from aos_api.aip_business_investigation_responsibility_template import BI_ROLE_BLUEPRINTS
from aos_api.aip_stage_template_authority import (
    published_investigation_profile_source_ref,
    resolve_stage_template_source,
)
from aos_api.db import connect as db_connect, connect_read_only
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.openfga import marking_key, openfga_api_url, user_key
from aos_api.tenant_scope import TenantScope


INVESTIGATION_SKILL_SELECTION: tuple[ExactRevisionRef, ...] = (
    ExactRevisionRef(
        resourceType="SkillTemplateRevision",
        resourceId="ecommerce.skill.D01",
        revision=2,
        contentHash="d204a147231dbdeb04c96e0ee93989aaf73088ba4ac5e72261efa063135a4b6d",
    ),
    ExactRevisionRef(
        resourceType="SkillTemplateRevision",
        resourceId="ecommerce.skill.D02",
        revision=2,
        contentHash="342ff31d2c01365fbdcc4d27520e9ee711f96ccfc0851b5c94992fc7a0440952",
    ),
    ExactRevisionRef(
        resourceType="SkillTemplateRevision",
        resourceId="ecommerce.skill.D03",
        revision=4,
        contentHash="3b60ef1e7147b761d1582d8dd0c62934e24d28a8ad8306caf12b1db02306a704",
    ),
)

_ROLE_BLUEPRINTS = BI_ROLE_BLUEPRINTS


def selected_skill_refs() -> dict[str, ExactRevisionRef]:
    """Historical BI-W10 references; not a current runtime selection."""
    return {ref.resource_id: ref for ref in INVESTIGATION_SKILL_SELECTION}


INVESTIGATION_SKILL_IDS = tuple(ref.resource_id for ref in INVESTIGATION_SKILL_SELECTION)


class InvestigationSkillSelectionBlocked(ValueError):
    def __init__(self, code: str, skill_id: str) -> None:
        self.code = code
        super().__init__(f"exact active SkillBinding unavailable: {skill_id} ({code})")


def selected_bound_skill_ref(skill_id: str, bindings: list[Mapping[str, Any]]) -> ExactRevisionRef:
    """Select the explicit unique active binding, never the latest template."""
    if skill_id not in INVESTIGATION_SKILL_IDS:
        raise ValueError('unsupported investigation skill')
    candidates = [row for row in bindings if row['skill_id'] == skill_id and row['status'] == 'active']
    if len(candidates) != 1:
        code = 'AIP_SKILL_BINDING_MISSING' if not candidates else 'AIP_SKILL_BINDING_AMBIGUOUS'
        raise InvestigationSkillSelectionBlocked(code, skill_id)
    row = candidates[0]
    try:
        return ExactRevisionRef(resourceType='SkillTemplateRevision', resourceId=skill_id,
            revision=row['skill_revision'], contentHash=row['bound_skill_hash'])
    except (KeyError, ValueError):
        raise InvestigationSkillSelectionBlocked('AIP_SKILL_SELECTION_REF_MISSING_OR_DRIFTED', skill_id) from None


def _schema(resource_id: str) -> ResourceRef:
    return ResourceRef(
        resourceType="JsonSchema",
        resourceId=resource_id,
        revision="1",
        authority="aos.ecommerce.business-investigation",
    )


def build_stage_template_request() -> CreateStageTemplateRequest:
    common = {
        "applicability": StageApplicability(kind=StageApplicabilityKind.ALWAYS),
        "gate_refs": [],
        "checkpoint_policy": {"mode": "receipt-first", "unknown": "pause"},
        "retry_policy": {"automatic": False},
        "compensation_policy": {"externalEffect": "none"},
    }
    stages = [
        StageDefinition(
            stageId="portrait",
            title="经营画像",
            dependsOn=[],
            requiredSlotIds=[
                "investigation-owner",
                "data-steward",
                "content-research",
                "customer-research",
                "channel-research",
            ],
            inputSchemaRef=_schema("business-investigation.portrait.input"),
            outputSchemaRef=_schema("business-investigation.portrait.output"),
            **common,
        ),
        StageDefinition(
            stageId="diagnosis",
            title="问题与机会诊断",
            dependsOn=["portrait"],
            requiredSlotIds=[
                "investigation-owner",
                "data-steward",
                "customer-research",
                "channel-research",
                "business-reviewer",
            ],
            inputSchemaRef=_schema("business-investigation.diagnosis.input"),
            outputSchemaRef=_schema("business-investigation.diagnosis.output"),
            **common,
        ),
        StageDefinition(
            stageId="solution-design",
            title="方案设计",
            dependsOn=["diagnosis"],
            requiredSlotIds=[
                "investigation-owner",
                "content-research",
                "channel-research",
                "business-reviewer",
            ],
            inputSchemaRef=_schema("business-investigation.solution-design.input"),
            outputSchemaRef=_schema("business-investigation.solution-design.output"),
            **common,
        ),
    ]
    return CreateStageTemplateRequest(
        profile="ecommerce.business-investigation",
        sourceBundleRef=published_investigation_profile_source_ref(),
        stages=stages,
    )


def build_responsibility_plan_request(
    instance_versions: Mapping[str, int],
    *,
    template_ref: ExactRevisionRef | None = None,
) -> CreateResponsibilityPlanRequest:
    missing = sorted(
        instance_id
        for _, _, instance_id, _, _ in _ROLE_BLUEPRINTS
        if instance_id not in instance_versions
    )
    if missing:
        raise ValueError("active digital coworker versions missing: " + ",".join(missing))
    slots = [
        ResponsibilitySlot(
            slotId=slot_id,
            responsibilityType=responsibility_type,
            requiredCapabilityIds=list(capabilities),
            inputSchemaRef=_schema(f"business-investigation.{slot_id}.input"),
            outputSchemaRef=_schema(f"business-investigation.{slot_id}.output"),
            gateRefs=[],
            returnStage=return_stage,
            assignee=AssigneeRef(
                kind=AssigneeKind.AGENT_INSTANCE,
                resourceId=instance_id,
                version=instance_versions[instance_id],
            ),
        )
        for slot_id, responsibility_type, instance_id, capabilities, return_stage in _ROLE_BLUEPRINTS
    ]
    return CreateResponsibilityPlanRequest(
        profile="ecommerce.business-investigation.readonly",
        templateRef=(template_ref or published_template_ref(
            "ecommerce.business-investigation.readonly")),
        slots=slots,
    )


@dataclass(frozen=True)
class InvestigationAuthorityMaterialization:
    stage_template: StageTemplateRevision
    responsibility_plan: ResponsibilityPlanRevision


class BusinessInvestigationAuthorityMaterializer:
    """Idempotently materialize governed metadata; never fabricate readiness."""

    def __init__(
        self,
        *,
        store: AipProductionContractStore | None = None,
        connect_factory: Callable[[TenantScope], Any] = db_connect,
        preparation_resolver: ApprovedBIPreparationResolver | None = None,
    ) -> None:
        self._connect = connect_factory
        self._preparation_resolver = preparation_resolver or ApprovedBIPreparationResolver()
        self._store = store or AipProductionContractStore(
            connect_factory=connect_factory,
            responsibility_template_resolver=self._preparation_resolver.resolve,
            stage_template_source_resolver=resolve_stage_template_source,
        )

    def ensure(
        self,
        scope: TenantScope,
        *,
        actor: str,
    ) -> InvestigationAuthorityMaterialization:
        versions = self._active_instance_versions(scope)
        selection = self._preparation_resolver.select(scope)
        if selection is None:
            raise ValueError("signed installed BI responsibility template unavailable")
        plan_request = build_responsibility_plan_request(
            versions, template_ref=selection.template_ref)
        if not self._preparation_resolver.resolve(scope, plan_request.template_ref):
            raise ValueError("signed installed BI responsibility template unavailable")
        if isinstance(self._store, AipProductionContractStore):
            store_resolver = self._store._responsibility_template_resolver
            if store_resolver is None or not store_resolver(scope, plan_request.template_ref):
                raise ValueError("Plan store rejects signed BI preparation template")
        stage = self._store.create_stage_template(
            scope,
            actor,
            "bi-w10-02-investigation-stage-v1-create",
            build_stage_template_request(),
        )
        # A create Receipt replays the original draft revision while the head may
        # already have advanced to a frozen revision.  Always decide from the
        # current head so recovery is idempotent and never changes freeze input.
        stage = self._store.get_stage_template(scope, stage.template_id)
        if stage.lifecycle is BriefLifecycle.DRAFT:
            stage = self._store.freeze_stage_template(
                scope,
                actor,
                stage.template_id,
                stage.version,
                "bi-w10-02-investigation-stage-v1-freeze",
            )
        plan = self._store.create_responsibility_plan(
            scope,
            actor,
            "bi-w10-02-investigation-responsibility-v1-create",
            plan_request,
        )
        plan = self._store.get_responsibility_plan(scope, plan.plan_id)
        if (
            plan.lifecycle is BriefLifecycle.DRAFT
            and plan.readiness is ContractReadiness.READY
        ):
            plan = self._store.freeze_responsibility_plan(
                scope,
                actor,
                plan.plan_id,
                plan.version,
                "bi-w10-02-investigation-responsibility-v1-freeze",
            )
        return InvestigationAuthorityMaterialization(stage, plan)

    def finalize_responsibility_plan(
        self,
        scope: TenantScope,
        plan_id: str,
        *,
        actor: str,
    ) -> ResponsibilityPlanRevision:
        """Freeze the current plan only when canonical dependencies are READY."""
        plan = self._store.get_responsibility_plan(scope, plan_id)
        if (
            plan.lifecycle is BriefLifecycle.DRAFT
            and plan.readiness is ContractReadiness.READY
        ):
            return self._store.freeze_responsibility_plan(
                scope,
                actor,
                plan.plan_id,
                plan.version,
                f"bi-w10-02-investigation-responsibility-freeze:{plan.plan_id}:v{plan.version}",
            )
        return plan

    def _active_instance_versions(self, scope: TenantScope) -> dict[str, int]:
        instance_ids = [item[2] for item in _ROLE_BLUEPRINTS]
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT instance_id,version FROM aip_agent_instance
                   WHERE org_id=%s AND project_id=%s AND status='active'
                     AND instance_id=ANY(%s) ORDER BY instance_id""",
                (*scope.key, instance_ids),
            ).fetchall()
        return {str(row["instance_id"]): int(row["version"]) for row in rows}


class SignedBIPlanPreparationService:
    """Prepare one draft Plan under the approved installation's current authority."""

    def __init__(
        self,
        *,
        connect_factory: Callable[[TenantScope], Any] = db_connect,
        preparation_resolver: ApprovedBIPreparationResolver | None = None,
    ) -> None:
        self._connect = connect_factory
        self._resolver = preparation_resolver or ApprovedBIPreparationResolver()
        self._installation_store = PostgresInstallationStore()
        self._permission = CurrentControlPermission(operation=CONFIGURE_RUNTIME_OPERATION)
        self._plan_store = AipProductionContractStore(
            connect_factory=connect_factory,
            responsibility_template_resolver=self._resolver.resolve,
        )

    def prepare(
        self, scope: TenantScope, *, installation_id: str,
        expected_etag_version: int, principal: Principal,
        idempotency_key: str,
    ) -> ResponsibilityPlanRevision:
        if (type(scope) is not TenantScope or type(principal) is not Principal
                or principal.token_kind != "oidc"
                or (principal.org_id, principal.project_id) != scope.key
                or not principal.subject or principal.subject != principal.subject.strip()):
            raise PermissionError("formal authenticated actor required")
        installation_id = str(UUID(installation_id))
        if (type(expected_etag_version) is not int or expected_etag_version < 1
                or type(idempotency_key) is not str
                or not 1 <= len(idempotency_key) <= 120
                or idempotency_key != idempotency_key.strip()):
            raise ValueError("exact BI preparation target and idempotency key required")
        with self._connect(scope) as conn:
            apply_asset_transaction_scope(
                conn, org_id=scope.org_id, project_id=scope.project_id)
            locked = self._installation_store.lock_for_bi_plan_in_transaction(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=installation_id,
                expected_etag_version=expected_etag_version,
            )
            self._permission(conn=conn, locked=locked, actor=principal.subject)
            if locked.record.state != "approved" or locked.record.active_revision is not None:
                raise ValueError("signed BI preparation requires approved inactive installation")
            selection = self._resolver.select(scope)
            if selection is None or selection.installation_id != installation_id:
                raise ValueError("exact signed approved BI installation unavailable")
            instance_ids = [item[2] for item in _ROLE_BLUEPRINTS]
            bi_issuer = (isinstance(conn, psycopg.Connection) and conn.execute(
                'SELECT current_user AS role').fetchone()['role'] == 'aos_bi_plan_issuer')
            if bi_issuer:
                rows = conn.execute(
                    """SELECT instance_id,version FROM public.aos_bi_plan_agents_lock_a0v_136(
                        %s,%s,%s)""", (*scope.key, instance_ids)).fetchall()
            else:
                rows = conn.execute(
                    """SELECT instance_id,version FROM aip_agent_instance
                        WHERE org_id=%s AND project_id=%s AND status='active'
                          AND instance_id=ANY(%s) ORDER BY instance_id FOR SHARE""",
                    (*scope.key, instance_ids),
                ).fetchall()
            versions = {str(row["instance_id"]): int(row["version"]) for row in rows}
            if (len(rows) != len(instance_ids) or len(versions) != len(instance_ids)
                    or any(version < 1 for version in versions.values())):
                raise ValueError("six current digital coworker instances required")
            request = build_responsibility_plan_request(
                versions, template_ref=selection.template_ref)
            result = self._plan_store.create_responsibility_plan_in_transaction(
                conn, scope, principal.subject, idempotency_key, request,
                operation="bi_responsibility_plan.prepare",
                request_context={
                    "installationId": installation_id,
                    "installationETag": expected_etag_version,
                    "templateRef": selection.template_ref.model_dump(mode="json", by_alias=True),
                    "actor": principal.subject,
                },
            )
            conn.commit()
            return result


class SignedBIPlanActiveRebindService:
    """Rebind an original approved BI draft to its signed active installation."""

    def __init__(
        self, *, connect_factory: Callable[[TenantScope], Any] = db_connect,
        active_resolver: ActiveBIBusinessResolver | None = None,
    ) -> None:
        self._connect = connect_factory
        self._resolver = active_resolver or ActiveBIBusinessResolver()
        self._installation_store = PostgresInstallationStore()
        self._permission = CurrentControlPermission(operation=CONFIGURE_RUNTIME_OPERATION)
        self._plan_store = AipProductionContractStore(
            connect_factory=connect_factory,
            responsibility_template_resolver=self._resolver.resolve,
        )

    def rebind(
        self, scope: TenantScope, *, installation_id: str, plan_id: str,
        prepare_key: str, expected_etag_version: int,
        expected_plan_version: int, principal: Principal, idempotency_key: str,
    ) -> ResponsibilityPlanRevision:
        if (type(scope) is not TenantScope or type(principal) is not Principal
                or principal.token_kind != "oidc"
                or (principal.org_id, principal.project_id) != scope.key
                or not principal.subject or principal.subject != principal.subject.strip()):
            raise PermissionError("formal authenticated actor required")
        installation_id = str(UUID(installation_id))
        if (type(plan_id) is not str or not plan_id
                or type(expected_etag_version) is not int or expected_etag_version < 1
                or type(expected_plan_version) is not int or expected_plan_version < 1
                or any(type(key) is not str or not 1 <= len(key) <= 120
                       or key != key.strip() for key in (prepare_key, idempotency_key))):
            raise ValueError("exact BI rebind target, versions and idempotency keys required")
        with self._connect(scope) as conn:
            apply_asset_transaction_scope(
                conn, org_id=scope.org_id, project_id=scope.project_id)
            locked = self._installation_store.lock_for_bi_plan_in_transaction(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=installation_id,
                expected_etag_version=expected_etag_version,
            )
            self._permission(conn=conn, locked=locked, actor=principal.subject)
            if (locked.record.state != "active"
                    or locked.record.active_revision != locked.record.current_revision):
                raise ProductionContractConflict("signed BI rebind requires current active installation")
            # Hold the growth release rows while the signed resolver reads its
            # Registry snapshot, so a concurrent revocation cannot overtake
            # this Plan write before commit.
            release_rows = conn.execute(
                """SELECT version.version_pk FROM asset_bundle_version AS version
                   JOIN asset_bundle AS bundle ON bundle.bundle_pk=version.bundle_pk
                   WHERE bundle.publisher='aos'
                     AND bundle.bundle_id='solution.ecommerce.growth'
                     AND version.version IN ('1.12.0','1.13.0')
                   ORDER BY version.version_pk FOR SHARE OF version"""
            ).fetchall()
            if not release_rows:
                raise ProductionContractConflict("current signed BI release unavailable")
            selection = self._resolver.select(scope)
            if (selection is None or selection.installation_id != installation_id
                    or selection.template_ref.revision != locked.record.current_revision):
                raise ProductionContractConflict("exact signed active BI installation unavailable")
            row = conn.execute(
                """SELECT receipt_id,result_ref FROM aip_production_contract_receipt
                   WHERE org_id=%s AND project_id=%s
                     AND operation='bi_responsibility_plan.prepare'
                     AND idempotency_key=%s AND created_by=%s""",
                (*scope.key, prepare_key, principal.subject),
            ).fetchone()
            if row is None:
                raise ProductionContractNotFound("original BI preparation receipt not found")
            result_ref = self._plan_store._load(row["result_ref"])
            if not isinstance(result_ref, dict):
                raise ProductionContractConflict("original BI preparation receipt invalid")
            binding = _require_bi_installation_binding(
                result_ref.get("installationBinding"), principal.subject)
            try:
                original_ref = ExactRevisionRef.model_validate({
                    name: result_ref.get(name) for name in
                    ("resourceType", "resourceId", "revision", "contentHash")})
                original_template = ExactRevisionRef.model_validate(binding["templateRef"])
            except (TypeError, ValueError) as exc:
                raise ProductionContractConflict("original BI preparation reference invalid") from exc
            if (original_ref.resource_type != "ResponsibilityPlanRevision"
                    or original_ref.resource_id != plan_id
                    or binding["installationId"] != installation_id
                    or binding["installationETag"] >= expected_etag_version
                    or original_template.resource_type != "ResponsibilityTemplateRevision"
                    or original_template.resource_id != selection.template_ref.resource_id
                    or original_template.content_hash != selection.template_ref.content_hash
                    or original_template.revision >= selection.template_ref.revision):
                raise ProductionContractConflict("original BI Plan and active installation differ")
            original = self._plan_store.get_responsibility_plan(
                scope, plan_id, original_ref.revision, conn=conn)
            if (original.content_hash != original_ref.content_hash
                    or original.created_by != principal.subject
                    or original.template_ref != original_template
                    or original.lifecycle is not BriefLifecycle.DRAFT):
                raise ProductionContractConflict("original BI Plan revision drifted")
            head = self._plan_store._head(
                conn, scope, "aip_responsibility_plan_head", "plan_id", plan_id)
            if head is None:
                raise ProductionContractNotFound("original BI Plan not found")
            replay = self._plan_store._replay(
                conn, scope, "bi_responsibility_plan.rebind", idempotency_key,
                self._rebind_request_hash(
                    original, selection.template_ref, expected_plan_version,
                    installation_id, expected_etag_version, row["receipt_id"],
                    principal.subject, plan_id),
            )
            if replay is None and (int(head["current_revision"]) != original_ref.revision
                                   or int(head["version"]) != expected_plan_version):
                raise ProductionContractConflict("original BI Plan head changed")
            body = self._rebind_body(
                original, selection.template_ref, expected_plan_version)
            context = self._rebind_context(
                installation_id, expected_etag_version, row["receipt_id"],
                original.template_ref, selection.template_ref, principal.subject)
            result = self._plan_store.revise_responsibility_plan_in_transaction(
                conn, scope, principal.subject, plan_id, idempotency_key, body,
                operation="bi_responsibility_plan.rebind", request_context=context,
            )
            current_selection = self._resolver.select(scope)
            if (current_selection is None
                    or current_selection.installation_id != installation_id
                    or current_selection.template_ref != selection.template_ref):
                raise ProductionContractConflict("signed active BI source changed before commit")
            conn.commit()
            return result

    @staticmethod
    def _rebind_body(original: ResponsibilityPlanRevision,
                     active_ref: ExactRevisionRef, expected_version: int,
                     ) -> ReviseResponsibilityPlanRequest:
        fields = CreateResponsibilityPlanRequest.model_fields
        body = {name: getattr(original, name) for name in fields}
        return ReviseResponsibilityPlanRequest.model_validate({
            **body, "template_ref": active_ref, "expected_version": expected_version,
        })

    @staticmethod
    def _rebind_context(installation_id: str, etag: int, receipt_id: str,
                        approved_ref: ExactRevisionRef, active_ref: ExactRevisionRef,
                        actor: str) -> dict[str, Any]:
        return {
            "installationId": installation_id, "installationETag": etag,
            "prepareReceiptId": receipt_id,
            "approvedTemplateRef": approved_ref.model_dump(mode="json", by_alias=True),
            "activeTemplateRef": active_ref.model_dump(mode="json", by_alias=True),
            "actor": actor,
        }

    @classmethod
    def _rebind_request_hash(cls, original: ResponsibilityPlanRevision,
                             active_ref: ExactRevisionRef, expected_version: int,
                             installation_id: str, etag: int, receipt_id: str,
                             actor: str, plan_id: str) -> str:
        from aos_api.aip_production_contract_store import canonical_hash
        body = cls._rebind_body(original, active_ref, expected_version)
        return canonical_hash({
            "planId": plan_id, "body": body.model_dump(mode="json", by_alias=True),
            "context": cls._rebind_context(
                installation_id, etag, receipt_id, original.template_ref,
                active_ref, actor),
        })


class SignedBIPlanActiveFreezeService(SignedBIPlanActiveRebindService):
    """Freeze only the draft made by the exact signed active rebind Receipt."""

    def freeze(
        self, scope: TenantScope, *, installation_id: str, plan_id: str,
        rebind_key: str, expected_etag_version: int,
        expected_plan_version: int, principal: Principal, idempotency_key: str,
    ) -> ResponsibilityPlanRevision:
        if (type(scope) is not TenantScope or type(principal) is not Principal
                or principal.token_kind != "oidc"
                or (principal.org_id, principal.project_id) != scope.key
                or not principal.subject or principal.subject != principal.subject.strip()):
            raise PermissionError("formal authenticated actor required")
        installation_id = str(UUID(installation_id))
        if (type(plan_id) is not str or not plan_id
                or type(expected_etag_version) is not int or expected_etag_version < 1
                or type(expected_plan_version) is not int or expected_plan_version < 1
                or any(type(key) is not str or not 1 <= len(key) <= 120
                       or key != key.strip() for key in (rebind_key, idempotency_key))):
            raise ValueError("exact BI freeze target, versions and idempotency keys required")
        with self._connect(scope) as conn:
            apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
            locked = self._installation_store.lock_for_bi_plan_in_transaction(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=installation_id,
                expected_etag_version=expected_etag_version,
            )
            self._permission(conn=conn, locked=locked, actor=principal.subject)
            if (locked.record.state != "active"
                    or locked.record.active_revision != locked.record.current_revision):
                raise ProductionContractConflict("signed BI freeze requires current active installation")
            release_rows = conn.execute(
                """SELECT version.version_pk FROM asset_bundle_version AS version
                   JOIN asset_bundle AS bundle ON bundle.bundle_pk=version.bundle_pk
                   WHERE bundle.publisher='aos'
                     AND bundle.bundle_id='solution.ecommerce.growth'
                     AND version.version IN ('1.12.0','1.13.0')
                   ORDER BY version.version_pk FOR SHARE OF version"""
            ).fetchall()
            if not release_rows:
                raise ProductionContractConflict("current signed BI release unavailable")
            selection = self._resolver.select(scope)
            if (selection is None or selection.installation_id != installation_id
                    or selection.template_ref.revision != locked.record.current_revision):
                raise ProductionContractConflict("exact signed active BI installation unavailable")
            receipt = conn.execute(
                """SELECT receipt_id,result_ref FROM aip_production_contract_receipt
                   WHERE org_id=%s AND project_id=%s
                     AND operation='bi_responsibility_plan.rebind'
                     AND idempotency_key=%s AND created_by=%s""",
                (*scope.key, rebind_key, principal.subject),
            ).fetchone()
            if receipt is None:
                raise ProductionContractNotFound("BI rebind receipt not found")
            result_ref = self._plan_store._load(receipt["result_ref"])
            if not isinstance(result_ref, dict):
                raise ProductionContractConflict("BI rebind receipt invalid")
            binding = _require_bi_rebind_binding(
                result_ref.get("rebindBinding"), principal.subject, selection.template_ref)
            try:
                draft_ref = ExactRevisionRef.model_validate({
                    name: result_ref.get(name) for name in
                    ("resourceType", "resourceId", "revision", "contentHash")})
            except (TypeError, ValueError) as exc:
                raise ProductionContractConflict("BI rebind Plan reference invalid") from exc
            if (draft_ref.resource_type != "ResponsibilityPlanRevision"
                    or draft_ref.resource_id != plan_id
                    or binding["installationId"] != installation_id
                    or binding["installationETag"] != expected_etag_version):
                raise ProductionContractConflict("BI rebind Receipt differs from active installation")
            original_receipt = conn.execute(
                """SELECT result_ref FROM aip_production_contract_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s
                     AND operation='bi_responsibility_plan.prepare' AND created_by=%s""",
                (*scope.key, binding["prepareReceiptId"], principal.subject),
            ).fetchone()
            if original_receipt is None:
                raise ProductionContractConflict("original BI preparation receipt missing")
            original_result = self._plan_store._load(original_receipt["result_ref"])
            if not isinstance(original_result, dict):
                raise ProductionContractConflict("original BI preparation receipt invalid")
            original_binding = _require_bi_installation_binding(
                original_result.get("installationBinding"), principal.subject)
            if (original_result.get("resourceId") != plan_id
                    or original_binding["installationId"] != installation_id
                    or original_binding["templateRef"] != binding["approvedTemplateRef"]):
                raise ProductionContractConflict("original BI preparation differs from rebind")
            draft = self._plan_store.get_responsibility_plan(
                scope, plan_id, draft_ref.revision, conn=conn)
            if (draft.content_hash != draft_ref.content_hash
                    or draft.created_by != principal.subject
                    or draft.template_ref != selection.template_ref
                    or draft.lifecycle is not BriefLifecycle.DRAFT):
                raise ProductionContractConflict("BI rebind draft drifted")
            context = {
                "installationId": installation_id,
                "installationETag": expected_etag_version,
                "rebindReceiptId": receipt["receipt_id"],
                "draftPlanRef": draft_ref.model_dump(mode="json", by_alias=True),
                "actor": principal.subject,
            }
            frozen = self._plan_store.freeze_responsibility_plan_in_transaction(
                conn, scope, principal.subject, plan_id, expected_plan_version,
                idempotency_key, operation="bi_responsibility_plan.freeze",
                request_context=context,
            )
            if frozen.lifecycle is not BriefLifecycle.FROZEN:
                raise ProductionContractConflict("BI Plan freeze result invalid")
            from aos_api.aip_runtime_configuration_sources import read_current_responsibility_plan_ref
            from aos_api.extension_runtime.configuration_contracts import ConfigurationSourceRef
            read_current_responsibility_plan_ref(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                purpose="role", ref=ConfigurationSourceRef(
                    authority="aip.responsibility_plan_revision", id=plan_id,
                    revision=frozen.revision, hash="sha256:" + frozen.content_hash,
                ),
            )
            current_selection = self._resolver.select(scope)
            if (current_selection is None
                    or current_selection.installation_id != installation_id
                    or current_selection.template_ref != selection.template_ref):
                raise ProductionContractConflict("signed active BI source changed before commit")
            conn.commit()
            return frozen


class SignedBIPlanAdmissionSnapshot(AipContractModel):
    """Informational snapshot; the write transaction always revalidates."""

    installation_id: str
    installation_revision: int
    installation_etag: int
    template_ref: ExactRevisionRef | None
    active_instance_versions: dict[str, int]
    blockers: list[str]
    candidate_ready: bool
    write_revalidation_required: bool = True


class SignedBIPlanAdmissionReader:
    """Read exact BI preparation gaps without granting configuration authority."""

    def __init__(
        self, *,
        connect_factory: Callable[[TenantScope], Any] = connect_read_only,
        preparation_resolver: ApprovedBIPreparationResolver | None = None,
    ) -> None:
        self._connect = connect_factory
        self._resolver = preparation_resolver or ApprovedBIPreparationResolver()

    def read(
        self, scope: TenantScope, *, installation_id: str,
        principal: Principal,
    ) -> SignedBIPlanAdmissionSnapshot:
        if (type(scope) is not TenantScope or type(principal) is not Principal
                or principal.token_kind != "oidc"
                or (principal.org_id, principal.project_id) != scope.key
                or not principal.subject or principal.subject != principal.subject.strip()):
            raise PermissionError("formal authenticated actor required")
        installation_id = str(UUID(installation_id))
        if openfga_api_url():
            raise PermissionError("current configuration permission adapter unavailable")
        with self._connect(scope) as conn:
            apply_asset_transaction_scope(
                conn, org_id=scope.org_id, project_id=scope.project_id)
            members = conn.execute(
                """SELECT role FROM meta_membership
                   WHERE org_id=%s AND project_id=%s AND subject=%s""",
                (*scope.key, principal.subject),
            ).fetchall()
            if len(members) != 1:
                raise PermissionError("current persisted membership required")
            try:
                require_control_role(
                    roles=[members[0]["role"]], operation=APPLY_INSTALLATION_OPERATION)
            except AssetRegistryError as exc:
                raise PermissionError("current configuration role required") from exc
            # Installation and registry readers use separate read-only snapshots.
            # This is guidance only; prepare() locks and rechecks everything.
            record = PostgresInstallationStore(
                connect_factory=lambda: self._connect(scope)).get_installation(
                    org_id=scope.org_id, project_id=scope.project_id,
                    installation_id=installation_id,
                )
            _, lock = load_stored_lock(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                composition_id=record.current.composition_id,
                revision=record.current.lock_revision,
            )
            if (
                record.current.lock_hash,
                record.current.permission_diff_hash,
                record.current.migration_plan_hash,
                record.current.contribution_diff_hash,
            ) != (
                lock.lock_hash, lock.permission_diff_hash,
                lock.migration_plan_hash, lock.contribution_diff_hash,
            ):
                raise LockIntegrityCorruptError()
            markings = lock.payload.permission_diff.target.markings
            granted = []
            for label in sorted(set(markings)):
                rows = conn.execute(
                    """SELECT object_key FROM authz_tuple
                       WHERE org_id=%s AND project_id=%s AND user_key=%s
                         AND relation='bearer' AND object_key=%s""",
                    (*scope.key, user_key(principal.subject), marking_key(label)),
                ).fetchall()
                if len(rows) == 1:
                    granted.append(label)
            require_target_markings(
                principal_markings=granted, target_markings=markings, conceal=True)
            blockers = []
            if record.state != "approved" or record.active_revision is not None:
                blockers.append("APPROVED_INACTIVE_INSTALLATION_REQUIRED")
            selection = self._resolver.select(scope) if not blockers else None
            if selection is None or selection.installation_id != installation_id:
                blockers.append("SIGNED_APPROVED_BI_TEMPLATE_UNAVAILABLE")
                selection = None
            instance_ids = [item[2] for item in _ROLE_BLUEPRINTS]
            rows = conn.execute(
                """SELECT instance_id,version FROM aip_agent_instance
                   WHERE org_id=%s AND project_id=%s AND status='active'
                     AND instance_id=ANY(%s) ORDER BY instance_id""",
                (*scope.key, instance_ids),
            ).fetchall()
            versions = {str(row["instance_id"]): int(row["version"]) for row in rows}
            if (len(rows) != len(instance_ids) or len(versions) != len(instance_ids)
                    or any(version < 1 for version in versions.values())):
                blockers.append("SIX_ACTIVE_AGENT_INSTANCES_MISSING")
            return SignedBIPlanAdmissionSnapshot(
                installation_id=installation_id,
                installation_revision=record.current_revision,
                installation_etag=record.etag_version,
                template_ref=selection.template_ref if selection else None,
                active_instance_versions=versions,
                blockers=blockers, candidate_ready=not blockers,
            )
