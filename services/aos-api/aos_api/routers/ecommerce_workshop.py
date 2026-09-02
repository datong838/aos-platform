"""Canonical read-only HTTP adapter for the ecommerce Workshop catalog."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from datetime import UTC, datetime
from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Security
from fastapi.security import HTTPBearer

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_catalog import (
    EcommerceWorkshopCatalog,
    build_ecommerce_workshop_catalog,
)
from aos_api.ecommerce_workshop_contracts import (
    EcommerceWorkshopModuleListResponse,
    EcommerceWorkshopModuleReadinessResponse,
    WorkshopFeatureActivationCommandRequest,
    WorkshopFeatureActivationCommandResponse,
    WorkshopFeatureActivationListResponse,
)
from aos_api.ecommerce_workshop_feature_activation import (
    EcommerceWorkshopFeatureActivationService,
    WorkshopFeatureActivationConflict,
    WorkshopFeatureActivationError,
    WorkshopFeatureActivationForbidden,
    WorkshopFeatureActivationUnavailable,
)
from aos_api.ecommerce_workshop_prepare_contracts import (
    EcommerceWorkshopPrepareRequest,
    EcommerceWorkshopPrepareResponse,
)
from aos_api.ecommerce_workshop_prepare_service import (
    EcommerceWorkshopPrepareService,
    PrepareConflict,
    PrepareDependencyBlocked,
    PrepareError,
)
from aos_api.ecommerce_workshop_evidence_build_service import (
    EcommerceWorkshopEvidenceBuildService,
    WorkshopEvidenceBuildBlocked,
    WorkshopEvidenceBuildError,
    WorkshopEvidenceBuildRequest,
    WorkshopEvidenceBuildResponse,
)
from aos_api.ecommerce_workshop_freeze_contracts import (
    WorkshopFreezeRequest,
    WorkshopFreezeResponse,
)
from aos_api.ecommerce_workshop_freeze_service import (
    EcommerceWorkshopFreezeService,
    WorkshopFreezeBlocked,
    WorkshopFreezeConflict,
    WorkshopFreezeError,
)
from aos_api.ecommerce_workshop_handoff_contracts import (
    ModuleHandoffCompileRequest,
    ModuleHandoffCompileResponse,
)
from aos_api.ecommerce_workshop_handoff_service import (
    ModuleHandoffCompiler,
    ModuleHandoffCompilerDrift,
    ModuleHandoffCompilerError,
)
from aos_api.ecommerce_workshop_analyst import EcommerceWorkshopAnalyst
from aos_api.ecommerce_workshop_analyst_source_reader import EcommerceWorkshopAnalystSourceReader
from aos_api.ecommerce_workshop_growth_scenario import EcommerceWorkshopGrowthScenario
from aos_api.ecommerce_workshop_dispatch_scenario import EcommerceWorkshopDispatchScenario
from aos_api.ecommerce_workshop_dispatch_scenario_contracts import DispatchScenarioContribution
from aos_api.ecommerce_workshop_batch_scenario import EcommerceWorkshopBatchScenario
from aos_api.ecommerce_workshop_batch_scenario_contracts import BatchScenarioContribution
from aos_api.ecommerce_workshop_learning_scenario import EcommerceWorkshopLearningScenario
from aos_api.ecommerce_workshop_learning_scenario_contracts import LearningScenarioContribution
from aos_api.ecommerce_workshop_full_video_scenario import EcommerceWorkshopFullVideoScenario
from aos_api.ecommerce_workshop_full_video_scenario_contracts import FullVideoScenarioContribution
from aos_api.ecommerce_workshop_analyst_contracts import WorkshopAnalystViewEnvelope
from aos_api.ecommerce_workshop_content_campaign import (
    EcommerceWorkshopContentCampaign,
)
from aos_api.ecommerce_workshop_content_campaign_contracts import (
    WorkshopContentCampaignViewEnvelope,
)
from aos_api.ecommerce_workshop_creator_growth import EcommerceWorkshopCreatorGrowth
from aos_api.ecommerce_workshop_creator_growth_contracts import (
    WorkshopCreatorGrowthViewEnvelope,
)
from aos_api.ecommerce_workshop_creator_growth_store import (
    EcommerceWorkshopCreatorGrowthStore,
)
from aos_api.ecommerce_workshop_creator_prepare import (
    CreateCreatorMatchObservationRequest,
    CreatorBatchPreparationRevision,
    CreatorContributionView,
    CreatorDiscoveryProfileRequest,
    CreatorDiscoveryProfileRevision,
    CreatorNormalizerReceipt,
    CreatorPrepareBlocked,
    CreatorPrepareConflict,
    CreatorPreparedMatchDecision,
    CreatorPreparedMatchObservation,
    DecideCreatorMatchRequest,
    EcommerceWorkshopCreatorPrepareService,
    FreezeCreatorBatchRequest,
    NormalizeCreatorArtifactRequest,
    PrepareCreatorBatchRequest,
)
from aos_api.ecommerce_workshop_creator_prepare_store import EcommerceWorkshopCreatorPrepareStore
from aos_api.ecommerce_workshop_creator_lifecycle import (
    CreatorBatchStartDecisionRevision,
    CreatorLifecycleBlocked,
    CreatorLifecycleConflict,
    CreatorLifecycleView,
    EcommerceWorkshopCreatorLifecycleService,
    StartCreatorBatchRequest,
)
from aos_api.ecommerce_workshop_creator_lifecycle_store import EcommerceWorkshopCreatorLifecycleStore
from aos_api.ecommerce_workshop_media_studio import EcommerceWorkshopMediaStudio
from aos_api.ecommerce_workshop_media_studio_lifecycle import EcommerceWorkshopMediaStudioLifecycle
from aos_api.ecommerce_workshop_media_publish import EcommerceWorkshopMediaPublish
from aos_api.ecommerce_workshop_media_cumulative import EcommerceWorkshopMediaCumulative
from aos_api.aip_action_adapters import ACTION_ADAPTERS
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_media_finance_store import AipMediaFinanceStore
from aos_api.aip_media_provider_job_store import AipMediaProviderJobStore
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_start_service import AipProductionStartService
from aos_api.ecommerce_workshop_media_studio_contracts import (
    WorkshopMediaStudioViewEnvelope,
)
from aos_api.ecommerce_workshop_price_governance import EcommerceWorkshopPriceGovernance
from aos_api.ecommerce_workshop_remedy_scenario import EcommerceWorkshopRemedyScenario
from aos_api.ecommerce_workshop_price_governance_contracts import WorkshopPriceGovernanceViewEnvelope
from aos_api.ecommerce_workshop_price_research import (
    CreatePriceMatchObservationRequest,
    DecideProductMatchRequest,
    EcommerceWorkshopPriceResearchService,
    FreezePriceResearchBatchRequest,
    MonitoringPolicyRequest,
    MonitoringPolicyRevision,
    NormalizePriceObservationRequest,
    PreparePriceResearchBatchRequest,
    PriceObservationRevision,
    PriceResearchBatchRevision,
    PriceResearchBlocked,
    PriceResearchConflict,
    PriceResearchContributionView,
    PriceResearchProfileRequest,
    PriceResearchProfileRevision,
    ProductMatchDecisionRevision,
    ProductMatchObservation,
)
from aos_api.ecommerce_workshop_price_research_store import EcommerceWorkshopPriceResearchStore
from aos_api.ecommerce_workshop_price_disposition import (
    CreatePriceCaseRequest,
    CreatePriceDispositionContractRequest,
    EcommerceWorkshopPriceDispositionService,
    FreezePriceDispositionRequest,
    PreparePriceDispositionRequest,
    PriceCaseRevision,
    PriceDispositionBlocked,
    PriceDispositionConflict,
    PriceDispositionContractRevision,
    PriceDispositionContributionView,
    PriceDispositionObservation,
    PriceDispositionRevision,
    RecordPriceDispositionObservationRequest,
)
from aos_api.ecommerce_workshop_price_disposition_store import EcommerceWorkshopPriceDispositionStore
from aos_api.ecommerce_workshop_customer import EcommerceWorkshopCustomer
from aos_api.ecommerce_workshop_customer_source_reader import EcommerceWorkshopCustomerSourceReader
from aos_api.ecommerce_workshop_customer_contracts import WorkshopCustomerViewEnvelope
from aos_api.ecommerce_workshop_customer_lifecycle import (
    CreateCustomerConsentPolicyRequest,
    CreateCustomerDialogueRequest,
    CreateCustomerJourneyRequest,
    CreateCustomerSegmentRequest,
    CustomerConsentPolicyRevision,
    CustomerDialogueBatchRevision,
    CustomerDialogueStrategyRevision,
    CustomerJourneyRevision,
    CustomerLifecycleBlocked,
    CustomerLifecycleConflict,
    CustomerLifecycleContributionView,
    CustomerSegmentRevision,
    EcommerceWorkshopCustomerLifecycleService,
    FreezeCustomerDialogueBatchRequest,
    PrepareCustomerDialogueBatchRequest,
)
from aos_api.ecommerce_workshop_customer_lifecycle_store import EcommerceWorkshopCustomerLifecycleStore
from aos_api.ecommerce_workshop_customer_contact import (
    CreateCustomerFrequencyPolicyRequest,
    CustomerBatchStartDecisionRevision,
    CustomerConsentWithdrawalObservation,
    CustomerContactBlocked,
    CustomerContactConflict,
    CustomerContactContributionView,
    CustomerDispatchObservation,
    CustomerFrequencyPolicyRevision,
    EcommerceWorkshopCustomerContactService,
    RecordCustomerConsentWithdrawalRequest,
    RecordCustomerDispatchObservationRequest,
    StartCustomerDialogueBatchRequest,
)
from aos_api.ecommerce_workshop_customer_contact_store import EcommerceWorkshopCustomerContactStore
from aos_api.ecommerce_workshop_three_module_closure import (
    BindThreeModuleEffectRequest,
    BindThreeModuleHandoffRequest,
    BindThreeModuleUsageRequest,
    CompileThreeModuleClosureRequest,
    EcommerceWorkshopThreeModuleClosureService,
    ThreeModule,
    ThreeModuleClosureBlocked,
    ThreeModuleClosureConflict,
    ThreeModuleClosureContributionView,
    ThreeModuleClosureRevision,
    ThreeModuleEffectBindingRevision,
    ThreeModuleHandoffBindingRevision,
    ThreeModuleUsageBindingRevision,
)
from aos_api.ecommerce_workshop_three_module_closure_store import EcommerceWorkshopThreeModuleClosureStore
from aos_api.ecommerce_workshop_shared_context import EcommerceWorkshopSharedContext
from aos_api.ecommerce_workshop_shared_context_contracts import WorkshopSharedContextEnvelope
from aos_api.ecommerce_workshop_operations import EcommerceWorkshopOperations
from aos_api.ecommerce_operation_commands import EcommerceOperationCommands
from aos_api.ecommerce_operation_command_contracts import (
    OperationCommandReadinessEnvelope,
)
from aos_api.ecommerce_operation_command_execution_contracts import (
    ChangeOperationMembershipCommandRequest,
    ClassifyOperationCommandRequest,
    CreateOperationCaseCommandRequest,
    KillOperationAutomationCommandRequest,
    ManageOperationSlaCommandRequest,
    OperationCommandExecutionEnvelope,
)
from aos_api.ecommerce_operation_command_service import (
    CanonicalOperationActionControl,
    EcommerceOperationCommandService,
    OperationCommandConflict,
    OperationCommandDependencyUnavailable,
)
from aos_api.ecommerce_operation_command_observation import (
    EcommerceOperationCommandObservationService,
    OperationCommandObservationConflict,
    OperationCommandObservationEnvelope,
    OperationCommandObservationUnavailable,
    build_operation_observation_control,
)
from aos_api.ecommerce_workshop_operations_contracts import (
    WorkshopOperationsViewEnvelope,
)
from aos_api.ecommerce_workshop_source_readiness import (
    EcommerceWorkshopSourceReadiness,
    SourceReadinessTenantMismatchError,
)
from aos_api.ecommerce_workshop_task_cockpit import (
    EcommerceWorkshopTaskCockpit,
    TaskCockpitPersistenceError,
)
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitActionReceiptEnvelope,
    TaskCockpitApprovalReviewEnvelope,
    TaskCockpitCheckpointPageEnvelope,
    TaskCockpitCoreEnvelope,
    TaskCockpitProductionContextEnvelope,
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitSkillContributionEnvelope,
    TaskCockpitStepPageEnvelope,
)
from aos_api.errors import ApiError, ErrorBody
from aos_api.public_contracts import TaskStatus
from aos_api.source_readiness import build_source_readiness_service
from aos_api.source_readiness_contracts import SourceReadinessEnvelope
from aos_api.tenant_scope import TenantScope

_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/ecommerce-workshop",
    tags=["ecommerce-workshop"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
    500: {"model": ErrorBody},
    503: {"model": ErrorBody},
}
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
ModuleIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=160,
        pattern=r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$",
    ),
]
FeatureIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=160,
        pattern=r"^aip[.][a-z0-9]+(?:[.-][a-z0-9]+)*$",
    ),
]
RunIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$",
    ),
]
ContextIdPath = Annotated[
    str,
    Path(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]{32,128}$"),
]
ResultT = TypeVar("ResultT")


@lru_cache(maxsize=1)
def get_ecommerce_workshop_catalog() -> EcommerceWorkshopCatalog:
    return build_ecommerce_workshop_catalog()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_feature_activation_service() -> EcommerceWorkshopFeatureActivationService:
    return EcommerceWorkshopFeatureActivationService()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_task_cockpit() -> EcommerceWorkshopTaskCockpit:
    return EcommerceWorkshopTaskCockpit()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_dispatch_scenario() -> EcommerceWorkshopDispatchScenario:
    return EcommerceWorkshopDispatchScenario()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_batch_scenario() -> EcommerceWorkshopBatchScenario:
    return EcommerceWorkshopBatchScenario()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_handoff_compiler() -> ModuleHandoffCompiler:
    return ModuleHandoffCompiler(
        cockpit=get_ecommerce_workshop_task_cockpit(),
        catalog=get_ecommerce_workshop_catalog(),
    )


@lru_cache(maxsize=1)
def get_ecommerce_workshop_source_readiness() -> EcommerceWorkshopSourceReadiness:
    return EcommerceWorkshopSourceReadiness(build_source_readiness_service())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_operations() -> EcommerceWorkshopOperations:
    return EcommerceWorkshopOperations()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_prepare_service() -> EcommerceWorkshopPrepareService:
    return EcommerceWorkshopPrepareService()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_evidence_build_service() -> EcommerceWorkshopEvidenceBuildService:
    return EcommerceWorkshopEvidenceBuildService()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_freeze_service() -> EcommerceWorkshopFreezeService:
    return EcommerceWorkshopFreezeService()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_content_campaign() -> EcommerceWorkshopContentCampaign:
    return EcommerceWorkshopContentCampaign()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_creator_growth() -> EcommerceWorkshopCreatorGrowth:
    return EcommerceWorkshopCreatorGrowth(store=EcommerceWorkshopCreatorGrowthStore())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_creator_prepare() -> EcommerceWorkshopCreatorPrepareService:
    return EcommerceWorkshopCreatorPrepareService(EcommerceWorkshopCreatorPrepareStore())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_creator_lifecycle() -> EcommerceWorkshopCreatorLifecycleService:
    batch_store = EcommerceWorkshopCreatorPrepareStore()
    return EcommerceWorkshopCreatorLifecycleService(
        EcommerceWorkshopCreatorLifecycleStore(), batch_store
    )


@lru_cache(maxsize=1)
def get_ecommerce_workshop_price_research() -> EcommerceWorkshopPriceResearchService:
    return EcommerceWorkshopPriceResearchService(EcommerceWorkshopPriceResearchStore())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_price_disposition() -> EcommerceWorkshopPriceDispositionService:
    return EcommerceWorkshopPriceDispositionService(
        EcommerceWorkshopPriceDispositionStore(), EcommerceWorkshopPriceResearchStore()
    )


@lru_cache(maxsize=1)
def get_ecommerce_workshop_media_studio() -> EcommerceWorkshopMediaStudio:
    production_store = AipProductionContractStore()
    provider_job_store = AipMediaProviderJobStore()
    media_finance_store = AipMediaFinanceStore()
    lifecycle = EcommerceWorkshopMediaStudioLifecycle(
        production_store=production_store,
        production_start_service=AipProductionStartService(contract_store=production_store),
        provider_job_store=provider_job_store,
        media_finance_store=media_finance_store,
    )
    action_store = AipActionStore()
    publisher = EcommerceWorkshopMediaPublish(
        production_store=production_store,
        action_store=action_store,
        action_execution=AipActionExecutionService(action_store, ACTION_ADAPTERS),
    )
    return EcommerceWorkshopMediaStudio(
        provider_job_store=provider_job_store,
        media_finance_store=media_finance_store,
        lifecycle=lifecycle,
        publisher=publisher,
        cumulative=EcommerceWorkshopMediaCumulative(),
    )


@lru_cache(maxsize=1)
def get_ecommerce_workshop_analyst() -> EcommerceWorkshopAnalyst:
    return EcommerceWorkshopAnalyst(reader=EcommerceWorkshopAnalystSourceReader(), growth_scenario=EcommerceWorkshopGrowthScenario())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_learning_scenario() -> EcommerceWorkshopLearningScenario:
    return EcommerceWorkshopLearningScenario()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_full_video_scenario() -> EcommerceWorkshopFullVideoScenario:
    return EcommerceWorkshopFullVideoScenario()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_price_governance() -> EcommerceWorkshopPriceGovernance:
    return EcommerceWorkshopPriceGovernance(remedy_scenario=EcommerceWorkshopRemedyScenario())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_customer() -> EcommerceWorkshopCustomer:
    return EcommerceWorkshopCustomer(reader=EcommerceWorkshopCustomerSourceReader())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_customer_lifecycle() -> EcommerceWorkshopCustomerLifecycleService:
    return EcommerceWorkshopCustomerLifecycleService(EcommerceWorkshopCustomerLifecycleStore())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_customer_contact() -> EcommerceWorkshopCustomerContactService:
    return EcommerceWorkshopCustomerContactService(
        EcommerceWorkshopCustomerContactStore(), EcommerceWorkshopCustomerLifecycleStore()
    )


@lru_cache(maxsize=1)
def get_ecommerce_workshop_three_module_closure() -> EcommerceWorkshopThreeModuleClosureService:
    return EcommerceWorkshopThreeModuleClosureService(EcommerceWorkshopThreeModuleClosureStore())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_shared_context() -> EcommerceWorkshopSharedContext:
    return EcommerceWorkshopSharedContext()


@lru_cache(maxsize=1)
def get_ecommerce_operation_commands() -> EcommerceOperationCommands:
    return EcommerceOperationCommands()


@lru_cache(maxsize=1)
def get_ecommerce_operation_command_service() -> EcommerceOperationCommandService:
    return EcommerceOperationCommandService(
        action_control=CanonicalOperationActionControl()
    )


@lru_cache(maxsize=1)
def get_ecommerce_operation_command_observation_service() -> EcommerceOperationCommandObservationService:
    return EcommerceOperationCommandObservationService(
        action_control=build_operation_observation_control()
    )


CatalogDependency = Annotated[
    EcommerceWorkshopCatalog, Depends(get_ecommerce_workshop_catalog)
]
FeatureActivationServiceDependency = Annotated[
    EcommerceWorkshopFeatureActivationService,
    Depends(get_ecommerce_workshop_feature_activation_service),
]
TaskCockpitDependency = Annotated[
    EcommerceWorkshopTaskCockpit, Depends(get_ecommerce_workshop_task_cockpit)
]
DispatchScenarioDependency = Annotated[
    EcommerceWorkshopDispatchScenario, Depends(get_ecommerce_workshop_dispatch_scenario)
]
BatchScenarioDependency = Annotated[
    EcommerceWorkshopBatchScenario, Depends(get_ecommerce_workshop_batch_scenario)
]
HandoffCompilerDependency = Annotated[
    ModuleHandoffCompiler, Depends(get_ecommerce_workshop_handoff_compiler)
]
SourceReadinessDependency = Annotated[
    EcommerceWorkshopSourceReadiness,
    Depends(get_ecommerce_workshop_source_readiness),
]
OperationsDependency = Annotated[
    EcommerceWorkshopOperations,
    Depends(get_ecommerce_workshop_operations),
]
PrepareServiceDependency = Annotated[
    EcommerceWorkshopPrepareService,
    Depends(get_ecommerce_workshop_prepare_service),
]
EvidenceBuildServiceDependency = Annotated[
    EcommerceWorkshopEvidenceBuildService,
    Depends(get_ecommerce_workshop_evidence_build_service),
]
FreezeServiceDependency = Annotated[
    EcommerceWorkshopFreezeService,
    Depends(get_ecommerce_workshop_freeze_service),
]
ContentCampaignDependency = Annotated[
    EcommerceWorkshopContentCampaign,
    Depends(get_ecommerce_workshop_content_campaign),
]
CreatorGrowthDependency = Annotated[
    EcommerceWorkshopCreatorGrowth,
    Depends(get_ecommerce_workshop_creator_growth),
]
CreatorPrepareDependency = Annotated[
    EcommerceWorkshopCreatorPrepareService,
    Depends(get_ecommerce_workshop_creator_prepare),
]
CreatorLifecycleDependency = Annotated[
    EcommerceWorkshopCreatorLifecycleService,
    Depends(get_ecommerce_workshop_creator_lifecycle),
]
MediaStudioDependency = Annotated[
    EcommerceWorkshopMediaStudio,
    Depends(get_ecommerce_workshop_media_studio),
]
AnalystDependency = Annotated[
    EcommerceWorkshopAnalyst,
    Depends(get_ecommerce_workshop_analyst),
]
LearningScenarioDependency = Annotated[
    EcommerceWorkshopLearningScenario,
    Depends(get_ecommerce_workshop_learning_scenario),
]
FullVideoScenarioDependency = Annotated[
    EcommerceWorkshopFullVideoScenario,
    Depends(get_ecommerce_workshop_full_video_scenario),
]
PriceGovernanceDependency = Annotated[
    EcommerceWorkshopPriceGovernance,
    Depends(get_ecommerce_workshop_price_governance),
]
PriceResearchDependency = Annotated[
    EcommerceWorkshopPriceResearchService,
    Depends(get_ecommerce_workshop_price_research),
]
PriceDispositionDependency = Annotated[
    EcommerceWorkshopPriceDispositionService,
    Depends(get_ecommerce_workshop_price_disposition),
]
CustomerDependency = Annotated[
    EcommerceWorkshopCustomer,
    Depends(get_ecommerce_workshop_customer),
]
CustomerLifecycleDependency = Annotated[
    EcommerceWorkshopCustomerLifecycleService,
    Depends(get_ecommerce_workshop_customer_lifecycle),
]
CustomerContactDependency = Annotated[
    EcommerceWorkshopCustomerContactService,
    Depends(get_ecommerce_workshop_customer_contact),
]
ThreeModuleClosureDependency = Annotated[
    EcommerceWorkshopThreeModuleClosureService,
    Depends(get_ecommerce_workshop_three_module_closure),
]
SharedContextDependency = Annotated[
    EcommerceWorkshopSharedContext,
    Depends(get_ecommerce_workshop_shared_context),
]
OperationCommandsDependency = Annotated[
    EcommerceOperationCommands,
    Depends(get_ecommerce_operation_commands),
]
OperationCommandServiceDependency = Annotated[
    EcommerceOperationCommandService,
    Depends(get_ecommerce_operation_command_service),
]
OperationCommandObservationDependency = Annotated[
    EcommerceOperationCommandObservationService,
    Depends(get_ecommerce_operation_command_observation_service),
]


def _operation_command_idempotency(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="ECOMMERCE_OPERATION_COMMAND_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def _prepare_idempotency(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(
            code="WORKSHOP_PREPARE_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..120 characters",
            status_code=400,
        )
    return cleaned


def _map_prepare_error(exc: PrepareError) -> ApiError:
    if isinstance(exc, PrepareConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, PrepareDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="Workshop prepare failed closed", status_code=503)


def _map_evidence_build_error(exc: WorkshopEvidenceBuildError) -> ApiError:
    if isinstance(exc, WorkshopEvidenceBuildBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="Workshop evidence build failed closed", status_code=503)


def _map_freeze_error(exc: WorkshopFreezeError) -> ApiError:
    if isinstance(exc, WorkshopFreezeConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, WorkshopFreezeBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="Workshop freeze failed closed", status_code=503)


def _map_creator_prepare_error(exc: CreatorPrepareBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, CreatorPrepareConflict) else 422,
    )


def _map_creator_lifecycle_error(exc: CreatorLifecycleBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, CreatorLifecycleConflict) else 422,
    )


def _map_price_research_error(exc: PriceResearchBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, PriceResearchConflict) else 422,
    )


def _map_price_disposition_error(exc: PriceDispositionBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, PriceDispositionConflict) else 422,
    )


def _map_customer_lifecycle_error(exc: CustomerLifecycleBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, CustomerLifecycleConflict) else 422,
    )


def _map_customer_contact_error(exc: CustomerContactBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, CustomerContactConflict) else 422,
    )


def _map_three_module_closure_error(exc: ThreeModuleClosureBlocked) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409 if isinstance(exc, ThreeModuleClosureConflict) else 422,
    )


def _map_operation_command_error(exc: Exception) -> ApiError:
    if isinstance(exc, OperationCommandConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    return ApiError(
        code=getattr(exc, "code", "ECOMMERCE_OPERATION_COMMAND_ERROR"),
        message=str(exc) or "operation command failed closed",
        status_code=503,
    )


def _reject_query_parameters(request: Request) -> None:
    if request.query_params:
        raise ApiError(
            code="VALIDATION",
            message="ecommerce Workshop reads do not accept query parameters",
            status_code=400,
        )


def _reject_unknown_query_parameters(
    request: Request, *, allowed: frozenset[str]
) -> None:
    unknown = sorted(set(request.query_params) - allowed)
    duplicated = sorted(
        key for key in allowed if len(request.query_params.getlist(key)) > 1
    )
    if unknown or duplicated:
        raise ApiError(
            code="VALIDATION",
            message="unsupported ecommerce Workshop query parameters",
            status_code=400,
            details={"unknown": unknown, "duplicated": duplicated},
        )


def _invoke(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except AssetRegistryError as exc:
        raise ApiError(
            code=exc.code.value,
            message=str(exc),
            status_code=exc.http_status,
            details=exc.details,
        ) from exc


def _require_task_cockpit_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.task-cockpit",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_operations_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.operations",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_content_campaign_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.content-campaign",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_creator_growth_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.creator-growth",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_media_studio_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.media-studio",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_analyst_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.analyst",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_price_governance_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.price-governance",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_customer_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.customer",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_three_module_installation(
    module: ThreeModule, *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    checks = {
        ThreeModule.CREATOR: _require_creator_growth_installation,
        ThreeModule.PRICE: _require_price_governance_installation,
        ThreeModule.CUSTOMER: _require_customer_installation,
    }
    checks[module](principal=principal, catalog=catalog)


def _require_visible_workshop_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    projection = _invoke(
        lambda: catalog.list_modules(
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )
    if projection.count == 0:
        raise ApiError(
            code="WORKSHOP_NOT_INSTALLED",
            message="No active ecommerce Workshop module is visible",
            status_code=404,
        )


@router.get(
    "/modules",
    response_model=EcommerceWorkshopModuleListResponse,
    operation_id="ecommerceWorkshopModulesList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_modules(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
) -> EcommerceWorkshopModuleListResponse:
    _reject_query_parameters(request)
    return _invoke(
        lambda: catalog.list_modules(
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


@router.get(
    "/modules/{module_id}/readiness",
    response_model=EcommerceWorkshopModuleReadinessResponse,
    operation_id="ecommerceWorkshopModuleReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_module_readiness(
    request: Request,
    module_id: ModuleIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
) -> EcommerceWorkshopModuleReadinessResponse:
    _reject_query_parameters(request)
    return _invoke(
        lambda: catalog.get_readiness(
            module_id=module_id,
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _execute_feature_activation_command(
    *,
    operation: Literal["activate", "revoke"],
    feature_id: str,
    body: WorkshopFeatureActivationCommandRequest,
    idempotency_key: str,
    principal: Principal,
    service: EcommerceWorkshopFeatureActivationService,
) -> WorkshopFeatureActivationCommandResponse:
    try:
        return service.execute(
            principal=principal,
            feature_id=feature_id,
            operation=operation,
            body=body,
            idempotency_key=idempotency_key,
        )
    except WorkshopFeatureActivationForbidden as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=403) from exc
    except WorkshopFeatureActivationConflict as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except WorkshopFeatureActivationUnavailable as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc
    except WorkshopFeatureActivationError as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc


@router.get(
    "/aip-features",
    response_model=WorkshopFeatureActivationListResponse,
    operation_id="ecommerceWorkshopAipFeaturesList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_aip_features(
    principal: PrincipalDependency,
    service: FeatureActivationServiceDependency,
) -> WorkshopFeatureActivationListResponse:
    try:
        return service.list_current(principal=principal)
    except WorkshopFeatureActivationUnavailable as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc
    except WorkshopFeatureActivationError as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc


@router.post(
    "/aip-features/{feature_id}/activate",
    response_model=WorkshopFeatureActivationCommandResponse,
    operation_id="ecommerceWorkshopAipFeatureActivate",
    responses=_ERRORS,
)
def activate_ecommerce_workshop_aip_feature(
    feature_id: FeatureIdPath,
    body: WorkshopFeatureActivationCommandRequest,
    principal: PrincipalDependency,
    service: FeatureActivationServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> WorkshopFeatureActivationCommandResponse:
    return _execute_feature_activation_command(
        operation="activate",
        feature_id=feature_id,
        body=body,
        idempotency_key=idempotency_key,
        principal=principal,
        service=service,
    )


@router.post(
    "/aip-features/{feature_id}/revoke",
    response_model=WorkshopFeatureActivationCommandResponse,
    operation_id="ecommerceWorkshopAipFeatureRevoke",
    responses=_ERRORS,
)
def revoke_ecommerce_workshop_aip_feature(
    feature_id: FeatureIdPath,
    body: WorkshopFeatureActivationCommandRequest,
    principal: PrincipalDependency,
    service: FeatureActivationServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> WorkshopFeatureActivationCommandResponse:
    return _execute_feature_activation_command(
        operation="revoke",
        feature_id=feature_id,
        body=body,
        idempotency_key=idempotency_key,
        principal=principal,
        service=service,
    )


@router.post(
    "/modules/{module_id}/commands/prepare",
    response_model=EcommerceWorkshopPrepareResponse,
    operation_id="ecommerceWorkshopPrepare",
    responses=_ERRORS,
)
def prepare_ecommerce_workshop_module(
    request: Request,
    module_id: ModuleIdPath,
    body: EcommerceWorkshopPrepareRequest,
    principal: PrincipalDependency,
    service: PrepareServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> EcommerceWorkshopPrepareResponse:
    _reject_query_parameters(request)
    try:
        return service.prepare(
            TenantScope(principal.org_id, principal.project_id),
            actor=principal.subject,
            module_id=module_id,
            idempotency_key=_prepare_idempotency(idempotency_key),
            body=body,
        )
    except PrepareError as exc:
        raise _map_prepare_error(exc) from exc


@router.post(
    "/modules/{module_id}/commands/build-evidence",
    response_model=WorkshopEvidenceBuildResponse,
    operation_id="ecommerceWorkshopBuildEvidence",
    responses=_ERRORS,
)
def build_ecommerce_workshop_evidence(
    request: Request,
    module_id: ModuleIdPath,
    body: WorkshopEvidenceBuildRequest,
    principal: PrincipalDependency,
    service: EvidenceBuildServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> WorkshopEvidenceBuildResponse:
    _reject_query_parameters(request)
    try:
        return service.build(
            TenantScope(principal.org_id, principal.project_id),
            actor=principal.subject,
            module_id=module_id,
            idempotency_key=_prepare_idempotency(idempotency_key),
            body=body,
        )
    except WorkshopEvidenceBuildError as exc:
        raise _map_evidence_build_error(exc) from exc


@router.post(
    "/modules/{module_id}/commands/freeze",
    response_model=WorkshopFreezeResponse,
    operation_id="ecommerceWorkshopFreeze",
    responses=_ERRORS,
)
def freeze_ecommerce_workshop_production_context(
    request: Request,
    module_id: ModuleIdPath,
    body: WorkshopFreezeRequest,
    principal: PrincipalDependency,
    service: FreezeServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> WorkshopFreezeResponse:
    _reject_query_parameters(request)
    try:
        return service.freeze(
            TenantScope(principal.org_id, principal.project_id),
            actor=principal.subject,
            module_id=module_id,
            idempotency_key=_prepare_idempotency(idempotency_key),
            body=body,
        )
    except WorkshopFreezeError as exc:
        raise _map_freeze_error(exc) from exc


@router.get(
    "/source-readiness",
    response_model=SourceReadinessEnvelope,
    operation_id="ecommerceWorkshopSourceReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_source_readiness_envelope(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    source_readiness: SourceReadinessDependency,
) -> SourceReadinessEnvelope:
    _reject_query_parameters(request)
    _require_visible_workshop_installation(principal=principal, catalog=catalog)
    try:
        return source_readiness.read(
            org_id=principal.org_id,
            project_id=principal.project_id,
        )
    except SourceReadinessTenantMismatchError as exc:
        raise ApiError(
            code="SOURCE_READINESS_TENANT_MISMATCH",
            message="SourceReadiness dependency failed closed",
            status_code=500,
        ) from exc


@router.get(
    "/views/operations",
    response_model=WorkshopOperationsViewEnvelope,
    operation_id="ecommerceWorkshopOperationsViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_operations_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    operations: OperationsDependency,
) -> WorkshopOperationsViewEnvelope:
    _reject_query_parameters(request)
    _require_operations_installation(principal=principal, catalog=catalog)
    return operations.read(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.get(
    "/views/content-campaign",
    response_model=WorkshopContentCampaignViewEnvelope,
    operation_id="ecommerceWorkshopContentCampaignViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_content_campaign_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    content_campaign: ContentCampaignDependency,
) -> WorkshopContentCampaignViewEnvelope:
    _reject_query_parameters(request)
    _require_content_campaign_installation(principal=principal, catalog=catalog)
    return content_campaign.read(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.get(
    "/views/creator-growth",
    response_model=WorkshopCreatorGrowthViewEnvelope,
    operation_id="ecommerceWorkshopCreatorGrowthViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_creator_growth_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    creator_growth: CreatorGrowthDependency,
) -> WorkshopCreatorGrowthViewEnvelope:
    _reject_query_parameters(request)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    return creator_growth.read(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.post(
    "/creator-growth/discovery-profiles",
    response_model=CreatorDiscoveryProfileRevision,
    operation_id="ecommerceWorkshopCreatorDiscoveryProfileCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_creator_discovery_profile(
    body: CreatorDiscoveryProfileRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorDiscoveryProfileRevision:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.create_profile(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CreatorPrepareBlocked as exc:
        raise _map_creator_prepare_error(exc) from exc


@router.post(
    "/creator-growth/normalize",
    response_model=CreatorNormalizerReceipt,
    operation_id="ecommerceWorkshopCreatorArtifactNormalize",
    status_code=201,
    responses=_ERRORS,
)
def normalize_creator_artifact(
    body: NormalizeCreatorArtifactRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorNormalizerReceipt:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.normalize(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CreatorPrepareBlocked as exc:
        raise _map_creator_prepare_error(exc) from exc


@router.post(
    "/creator-growth/match-observations",
    response_model=CreatorPreparedMatchObservation,
    operation_id="ecommerceWorkshopCreatorMatchObservationCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_creator_match_observation(
    body: CreateCreatorMatchObservationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorPreparedMatchObservation:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.observe_match(TenantScope(principal.org_id, principal.project_id), body)
    except CreatorPrepareBlocked as exc:
        raise _map_creator_prepare_error(exc) from exc


@router.post(
    "/creator-growth/match-decisions",
    response_model=CreatorPreparedMatchDecision,
    operation_id="ecommerceWorkshopCreatorMatchDecisionCreate",
    status_code=201,
    responses=_ERRORS,
)
def decide_creator_match(
    body: DecideCreatorMatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorPreparedMatchDecision:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.decide_match(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CreatorPrepareBlocked as exc:
        raise _map_creator_prepare_error(exc) from exc


@router.post(
    "/creator-growth/batches/prepare",
    response_model=CreatorBatchPreparationRevision,
    operation_id="ecommerceWorkshopCreatorBatchPrepare",
    status_code=201,
    responses=_ERRORS,
)
def prepare_creator_batch(
    body: PrepareCreatorBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorBatchPreparationRevision:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.prepare_batch(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CreatorPrepareBlocked as exc:
        raise _map_creator_prepare_error(exc) from exc


@router.post(
    "/creator-growth/batches/{batch_id}/freeze",
    response_model=CreatorBatchPreparationRevision,
    operation_id="ecommerceWorkshopCreatorBatchFreeze",
    responses=_ERRORS,
)
def freeze_creator_batch(
    batch_id: Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")],
    body: FreezeCreatorBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorBatchPreparationRevision:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.freeze_batch(TenantScope(principal.org_id, principal.project_id), batch_id, body, principal.subject)
    except CreatorPrepareBlocked as exc:
        raise _map_creator_prepare_error(exc) from exc


@router.get(
    "/views/creator-growth/contributions",
    response_model=CreatorContributionView,
    operation_id="ecommerceWorkshopCreatorContributionViewGet",
    responses=_ERRORS,
)
def get_creator_contribution_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorPrepareDependency,
) -> CreatorContributionView:
    _reject_query_parameters(request)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    return service.contribution_view(TenantScope(principal.org_id, principal.project_id))


@router.post(
    "/creator-growth/batches/{batch_id}/start",
    response_model=CreatorBatchStartDecisionRevision,
    operation_id="ecommerceWorkshopCreatorBatchStart",
    status_code=201,
    responses=_ERRORS,
)
def start_creator_batch(
    batch_id: Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")],
    body: StartCreatorBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorLifecycleDependency,
) -> CreatorBatchStartDecisionRevision:
    _prepare_idempotency(idempotency_key)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    try:
        return service.start_batch(
            TenantScope(principal.org_id, principal.project_id),
            batch_id,
            body,
            principal.subject,
        )
    except CreatorLifecycleBlocked as exc:
        raise _map_creator_lifecycle_error(exc) from exc


@router.get(
    "/views/creator-growth/lifecycle",
    response_model=CreatorLifecycleView,
    operation_id="ecommerceWorkshopCreatorLifecycleViewGet",
    responses=_ERRORS,
)
def get_creator_lifecycle_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CreatorLifecycleDependency,
) -> CreatorLifecycleView:
    _reject_query_parameters(request)
    _require_creator_growth_installation(principal=principal, catalog=catalog)
    return service.view(TenantScope(principal.org_id, principal.project_id))


@router.get(
    "/views/media-studio",
    response_model=WorkshopMediaStudioViewEnvelope,
    operation_id="ecommerceWorkshopMediaStudioViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_media_studio_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    media_studio: MediaStudioDependency,
) -> WorkshopMediaStudioViewEnvelope:
    _reject_query_parameters(request)
    _require_media_studio_installation(principal=principal, catalog=catalog)
    return media_studio.read(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.get(
    "/views/media-studio/full-production-scenario",
    response_model=FullVideoScenarioContribution,
    operation_id="ecommerceWorkshopMediaStudioFullProductionScenarioGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_media_studio_full_production_scenario(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    scenario: FullVideoScenarioDependency,
) -> FullVideoScenarioContribution:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_media_studio_installation(principal=principal, catalog=catalog)
    return scenario.read(
        scope=TenantScope(principal.org_id, principal.project_id),
        cutoff=datetime.now(UTC),
    )


@router.get(
    "/views/analyst",
    response_model=WorkshopAnalystViewEnvelope,
    operation_id="ecommerceWorkshopAnalystViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_analyst_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    analyst: AnalystDependency,
) -> WorkshopAnalystViewEnvelope:
    _reject_query_parameters(request)
    _require_analyst_installation(principal=principal, catalog=catalog)
    return analyst.read(org_id=principal.org_id, project_id=principal.project_id)


@router.get(
    "/views/analyst/learning-scenario",
    response_model=LearningScenarioContribution,
    operation_id="ecommerceWorkshopAnalystLearningScenarioGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_analyst_learning_scenario(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    scenario: LearningScenarioDependency,
) -> LearningScenarioContribution:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_analyst_installation(principal=principal, catalog=catalog)
    return scenario.read(
        scope=TenantScope(principal.org_id, principal.project_id),
        cutoff=datetime.now(UTC),
    )


@router.get(
    "/views/price-governance",
    response_model=WorkshopPriceGovernanceViewEnvelope,
    operation_id="ecommerceWorkshopPriceGovernanceViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_price_governance_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    price_governance: PriceGovernanceDependency,
) -> WorkshopPriceGovernanceViewEnvelope:
    _reject_query_parameters(request)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    return price_governance.read(org_id=principal.org_id, project_id=principal.project_id)


@router.post(
    "/price-governance/research-profiles",
    response_model=PriceResearchProfileRevision,
    operation_id="ecommerceWorkshopPriceResearchProfileCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_price_research_profile(
    body: PriceResearchProfileRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> PriceResearchProfileRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.create_profile(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.post(
    "/price-governance/observations/normalize",
    response_model=PriceObservationRevision,
    operation_id="ecommerceWorkshopPriceObservationNormalize",
    status_code=201,
    responses=_ERRORS,
)
def normalize_price_observation(
    body: NormalizePriceObservationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> PriceObservationRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.normalize(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.post(
    "/price-governance/match-observations",
    response_model=ProductMatchObservation,
    operation_id="ecommerceWorkshopPriceMatchObservationCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_price_match_observation(
    body: CreatePriceMatchObservationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> ProductMatchObservation:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.observe_match(TenantScope(principal.org_id, principal.project_id), body)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.post(
    "/price-governance/match-decisions",
    response_model=ProductMatchDecisionRevision,
    operation_id="ecommerceWorkshopPriceMatchDecisionCreate",
    status_code=201,
    responses=_ERRORS,
)
def decide_price_match(
    body: DecideProductMatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> ProductMatchDecisionRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.decide_match(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.post(
    "/price-governance/monitoring-policies",
    response_model=MonitoringPolicyRevision,
    operation_id="ecommerceWorkshopPriceMonitoringPolicyCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_price_monitoring_policy(
    body: MonitoringPolicyRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> MonitoringPolicyRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.create_policy(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.post(
    "/price-governance/batches/prepare",
    response_model=PriceResearchBatchRevision,
    operation_id="ecommerceWorkshopPriceResearchBatchPrepare",
    status_code=201,
    responses=_ERRORS,
)
def prepare_price_research_batch(
    body: PreparePriceResearchBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> PriceResearchBatchRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.prepare_batch(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.post(
    "/price-governance/batches/{batch_id}/freeze",
    response_model=PriceResearchBatchRevision,
    operation_id="ecommerceWorkshopPriceResearchBatchFreeze",
    responses=_ERRORS,
)
def freeze_price_research_batch(
    batch_id: Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")],
    body: FreezePriceResearchBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> PriceResearchBatchRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.freeze_batch(TenantScope(principal.org_id, principal.project_id), batch_id, body, principal.subject)
    except PriceResearchBlocked as exc:
        raise _map_price_research_error(exc) from exc


@router.get(
    "/views/price-governance/contributions",
    response_model=PriceResearchContributionView,
    operation_id="ecommerceWorkshopPriceResearchContributionViewGet",
    responses=_ERRORS,
)
def get_price_research_contribution_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceResearchDependency,
) -> PriceResearchContributionView:
    _reject_query_parameters(request)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    return service.contribution_view(TenantScope(principal.org_id, principal.project_id))


@router.post(
    "/price-governance/cases",
    response_model=PriceCaseRevision,
    operation_id="ecommerceWorkshopPriceCaseCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_price_case(
    body: CreatePriceCaseRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceDispositionDependency,
) -> PriceCaseRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.create_case(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceDispositionBlocked as exc:
        raise _map_price_disposition_error(exc) from exc


@router.post(
    "/price-governance/disposition-contracts",
    response_model=PriceDispositionContractRevision,
    operation_id="ecommerceWorkshopPriceDispositionContractCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_price_disposition_contract(
    body: CreatePriceDispositionContractRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceDispositionDependency,
) -> PriceDispositionContractRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.create_contract(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceDispositionBlocked as exc:
        raise _map_price_disposition_error(exc) from exc


@router.post(
    "/price-governance/dispositions/prepare",
    response_model=PriceDispositionRevision,
    operation_id="ecommerceWorkshopPriceDispositionPrepare",
    status_code=201,
    responses=_ERRORS,
)
def prepare_price_disposition(
    body: PreparePriceDispositionRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceDispositionDependency,
) -> PriceDispositionRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.prepare(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except PriceDispositionBlocked as exc:
        raise _map_price_disposition_error(exc) from exc


@router.post(
    "/price-governance/dispositions/{disposition_id}/freeze",
    response_model=PriceDispositionRevision,
    operation_id="ecommerceWorkshopPriceDispositionFreeze",
    responses=_ERRORS,
)
def freeze_price_disposition(
    disposition_id: Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")],
    body: FreezePriceDispositionRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceDispositionDependency,
) -> PriceDispositionRevision:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.freeze(TenantScope(principal.org_id, principal.project_id), disposition_id, body, principal.subject)
    except PriceDispositionBlocked as exc:
        raise _map_price_disposition_error(exc) from exc


@router.post(
    "/price-governance/disposition-observations",
    response_model=PriceDispositionObservation,
    operation_id="ecommerceWorkshopPriceDispositionObservationRecord",
    status_code=201,
    responses=_ERRORS,
)
def record_price_disposition_observation(
    body: RecordPriceDispositionObservationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceDispositionDependency,
) -> PriceDispositionObservation:
    _prepare_idempotency(idempotency_key)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    try:
        return service.record_observation(TenantScope(principal.org_id, principal.project_id), body)
    except PriceDispositionBlocked as exc:
        raise _map_price_disposition_error(exc) from exc


@router.get(
    "/views/price-governance/dispositions",
    response_model=PriceDispositionContributionView,
    operation_id="ecommerceWorkshopPriceDispositionContributionViewGet",
    responses=_ERRORS,
)
def get_price_disposition_contribution_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: PriceDispositionDependency,
) -> PriceDispositionContributionView:
    _reject_query_parameters(request)
    _require_price_governance_installation(principal=principal, catalog=catalog)
    return service.contribution_view(TenantScope(principal.org_id, principal.project_id))


@router.get(
    "/views/customer",
    response_model=WorkshopCustomerViewEnvelope,
    operation_id="ecommerceWorkshopCustomerViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_customer_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    customer: CustomerDependency,
) -> WorkshopCustomerViewEnvelope:
    _reject_query_parameters(request)
    _require_customer_installation(principal=principal, catalog=catalog)
    return customer.read(org_id=principal.org_id, project_id=principal.project_id)


@router.post(
    "/customer/consent-policies",
    response_model=CustomerConsentPolicyRevision,
    operation_id="ecommerceWorkshopCustomerConsentPolicyCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_customer_consent_policy(
    body: CreateCustomerConsentPolicyRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerConsentPolicyRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.create_consent_policy(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CustomerLifecycleBlocked as exc:
        raise _map_customer_lifecycle_error(exc) from exc


@router.post(
    "/customer/segments",
    response_model=CustomerSegmentRevision,
    operation_id="ecommerceWorkshopCustomerSegmentCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_customer_segment(
    body: CreateCustomerSegmentRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerSegmentRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.create_segment(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CustomerLifecycleBlocked as exc:
        raise _map_customer_lifecycle_error(exc) from exc


@router.post(
    "/customer/journeys",
    response_model=CustomerJourneyRevision,
    operation_id="ecommerceWorkshopCustomerJourneyCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_customer_journey(
    body: CreateCustomerJourneyRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerJourneyRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.create_journey(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CustomerLifecycleBlocked as exc:
        raise _map_customer_lifecycle_error(exc) from exc


@router.post(
    "/customer/dialogues",
    response_model=CustomerDialogueStrategyRevision,
    operation_id="ecommerceWorkshopCustomerDialogueCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_customer_dialogue(
    body: CreateCustomerDialogueRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerDialogueStrategyRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.create_dialogue(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CustomerLifecycleBlocked as exc:
        raise _map_customer_lifecycle_error(exc) from exc


@router.post(
    "/customer/dialogue-batches/prepare",
    response_model=CustomerDialogueBatchRevision,
    operation_id="ecommerceWorkshopCustomerDialogueBatchPrepare",
    status_code=201,
    responses=_ERRORS,
)
def prepare_customer_dialogue_batch(
    body: PrepareCustomerDialogueBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerDialogueBatchRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.prepare_batch(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CustomerLifecycleBlocked as exc:
        raise _map_customer_lifecycle_error(exc) from exc


@router.post(
    "/customer/dialogue-batches/{batch_id}/freeze",
    response_model=CustomerDialogueBatchRevision,
    operation_id="ecommerceWorkshopCustomerDialogueBatchFreeze",
    responses=_ERRORS,
)
def freeze_customer_dialogue_batch(
    batch_id: Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")],
    body: FreezeCustomerDialogueBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerDialogueBatchRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.freeze_batch(TenantScope(principal.org_id, principal.project_id), batch_id, body, principal.subject)
    except CustomerLifecycleBlocked as exc:
        raise _map_customer_lifecycle_error(exc) from exc


@router.get(
    "/views/customer/contributions",
    response_model=CustomerLifecycleContributionView,
    operation_id="ecommerceWorkshopCustomerLifecycleContributionViewGet",
    responses=_ERRORS,
)
def get_customer_lifecycle_contribution_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerLifecycleDependency,
) -> CustomerLifecycleContributionView:
    _reject_query_parameters(request)
    _require_customer_installation(principal=principal, catalog=catalog)
    return service.contribution_view(TenantScope(principal.org_id, principal.project_id))


@router.post(
    "/customer/frequency-policies",
    response_model=CustomerFrequencyPolicyRevision,
    operation_id="ecommerceWorkshopCustomerFrequencyPolicyCreate",
    status_code=201,
    responses=_ERRORS,
)
def create_customer_frequency_policy(
    body: CreateCustomerFrequencyPolicyRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerContactDependency,
) -> CustomerFrequencyPolicyRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.create_frequency_policy(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except CustomerContactBlocked as exc:
        raise _map_customer_contact_error(exc) from exc


@router.post(
    "/customer/consent-withdrawals",
    response_model=CustomerConsentWithdrawalObservation,
    operation_id="ecommerceWorkshopCustomerConsentWithdrawalRecord",
    status_code=201,
    responses=_ERRORS,
)
def record_customer_consent_withdrawal(
    body: RecordCustomerConsentWithdrawalRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerContactDependency,
) -> CustomerConsentWithdrawalObservation:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.record_withdrawal(TenantScope(principal.org_id, principal.project_id), body)
    except CustomerContactBlocked as exc:
        raise _map_customer_contact_error(exc) from exc


@router.post(
    "/customer/dialogue-batches/{batch_id}/start-governance",
    response_model=CustomerBatchStartDecisionRevision,
    operation_id="ecommerceWorkshopCustomerDialogueBatchStartGovernance",
    status_code=201,
    responses=_ERRORS,
)
def start_customer_dialogue_batch_governance(
    batch_id: Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")],
    body: StartCustomerDialogueBatchRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerContactDependency,
) -> CustomerBatchStartDecisionRevision:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.start_batch(TenantScope(principal.org_id, principal.project_id), batch_id, body, principal.subject)
    except CustomerContactBlocked as exc:
        raise _map_customer_contact_error(exc) from exc


@router.post(
    "/customer/dispatch-observations",
    response_model=CustomerDispatchObservation,
    operation_id="ecommerceWorkshopCustomerDispatchObservationRecord",
    status_code=201,
    responses=_ERRORS,
)
def record_customer_dispatch_observation(
    body: RecordCustomerDispatchObservationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerContactDependency,
) -> CustomerDispatchObservation:
    _prepare_idempotency(idempotency_key)
    _require_customer_installation(principal=principal, catalog=catalog)
    try:
        return service.record_dispatch_observation(TenantScope(principal.org_id, principal.project_id), body)
    except CustomerContactBlocked as exc:
        raise _map_customer_contact_error(exc) from exc


@router.get(
    "/views/customer/contact-contributions",
    response_model=CustomerContactContributionView,
    operation_id="ecommerceWorkshopCustomerContactContributionViewGet",
    responses=_ERRORS,
)
def get_customer_contact_contribution_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: CustomerContactDependency,
) -> CustomerContactContributionView:
    _reject_query_parameters(request)
    _require_customer_installation(principal=principal, catalog=catalog)
    return service.contribution_view(TenantScope(principal.org_id, principal.project_id))


@router.post(
    "/three-module-closures",
    response_model=ThreeModuleClosureRevision,
    operation_id="ecommerceWorkshopThreeModuleClosureCompile",
    status_code=201,
    responses=_ERRORS,
)
def compile_three_module_closure(
    body: CompileThreeModuleClosureRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: ThreeModuleClosureDependency,
) -> ThreeModuleClosureRevision:
    _prepare_idempotency(idempotency_key)
    _require_three_module_installation(body.module, principal=principal, catalog=catalog)
    try:
        return service.compile(TenantScope(principal.org_id, principal.project_id), body, principal.subject)
    except ThreeModuleClosureBlocked as exc:
        raise _map_three_module_closure_error(exc) from exc


@router.post(
    "/three-module-closures/usage-bindings",
    response_model=ThreeModuleUsageBindingRevision,
    operation_id="ecommerceWorkshopThreeModuleUsageBind",
    status_code=201,
    responses=_ERRORS,
)
def bind_three_module_usage(
    body: BindThreeModuleUsageRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: ThreeModuleClosureDependency,
) -> ThreeModuleUsageBindingRevision:
    _prepare_idempotency(idempotency_key)
    scope = TenantScope(principal.org_id, principal.project_id)
    try:
        _require_three_module_installation(
            service.require_closure(scope, body.closure_ref).module,
            principal=principal,
            catalog=catalog,
        )
        return service.bind_usage(scope, body)
    except ThreeModuleClosureBlocked as exc:
        raise _map_three_module_closure_error(exc) from exc


@router.post(
    "/three-module-closures/effect-bindings",
    response_model=ThreeModuleEffectBindingRevision,
    operation_id="ecommerceWorkshopThreeModuleEffectBind",
    status_code=201,
    responses=_ERRORS,
)
def bind_three_module_effect(
    body: BindThreeModuleEffectRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: ThreeModuleClosureDependency,
) -> ThreeModuleEffectBindingRevision:
    _prepare_idempotency(idempotency_key)
    scope = TenantScope(principal.org_id, principal.project_id)
    try:
        _require_three_module_installation(
            service.require_closure(scope, body.closure_ref).module,
            principal=principal,
            catalog=catalog,
        )
        return service.bind_effect(scope, body)
    except ThreeModuleClosureBlocked as exc:
        raise _map_three_module_closure_error(exc) from exc


@router.post(
    "/three-module-closures/handoff-bindings",
    response_model=ThreeModuleHandoffBindingRevision,
    operation_id="ecommerceWorkshopThreeModuleHandoffBind",
    status_code=201,
    responses=_ERRORS,
)
def bind_three_module_handoff(
    body: BindThreeModuleHandoffRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: ThreeModuleClosureDependency,
) -> ThreeModuleHandoffBindingRevision:
    _prepare_idempotency(idempotency_key)
    scope = TenantScope(principal.org_id, principal.project_id)
    try:
        _require_three_module_installation(
            service.require_closure(scope, body.closure_ref).module,
            principal=principal,
            catalog=catalog,
        )
        return service.bind_handoff(scope, body)
    except ThreeModuleClosureBlocked as exc:
        raise _map_three_module_closure_error(exc) from exc


@router.get(
    "/views/{module}/closure-contributions",
    response_model=ThreeModuleClosureContributionView,
    operation_id="ecommerceWorkshopThreeModuleClosureContributionViewGet",
    responses=_ERRORS,
)
def get_three_module_closure_contribution_view(
    request: Request,
    module: ThreeModule,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: ThreeModuleClosureDependency,
) -> ThreeModuleClosureContributionView:
    _reject_query_parameters(request)
    _require_three_module_installation(module, principal=principal, catalog=catalog)
    return service.contribution_view(TenantScope(principal.org_id, principal.project_id), module)


@router.get(
    "/contexts/{context_id}",
    response_model=WorkshopSharedContextEnvelope,
    operation_id="ecommerceWorkshopSharedContextGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_shared_context_view(
    request: Request,
    context_id: ContextIdPath,
    principal: PrincipalDependency,
    shared_context: SharedContextDependency,
) -> WorkshopSharedContextEnvelope:
    _reject_query_parameters(request)
    return shared_context.read(org_id=principal.org_id, project_id=principal.project_id, context_id=context_id)


@router.get(
    "/commands/operations/readiness",
    response_model=OperationCommandReadinessEnvelope,
    operation_id="ecommerceWorkshopOperationCommandReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_operation_command_readiness(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    commands: OperationCommandsDependency,
) -> OperationCommandReadinessEnvelope:
    _reject_query_parameters(request)
    _require_operations_installation(principal=principal, catalog=catalog)
    return commands.read_readiness(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.get(
    "/commands/operations/observations/{proposal_id}/leases/{lease_id}",
    response_model=OperationCommandObservationEnvelope,
    operation_id="ecommerceWorkshopOperationCommandObservationGet",
    responses=_ERRORS,
)
def get_ecommerce_operation_command_observation(
    request: Request,
    proposal_id: Annotated[str, Path(min_length=1, max_length=300)],
    lease_id: Annotated[str, Path(min_length=1, max_length=300)],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    observations: OperationCommandObservationDependency,
) -> OperationCommandObservationEnvelope:
    _reject_query_parameters(request)
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return observations.read(principal, proposal_id, lease_id)
    except OperationCommandObservationConflict as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except OperationCommandObservationUnavailable as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc


@router.post(
    "/commands/operations/classify",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationClassifyPost",
    responses=_ERRORS,
)
def classify_ecommerce_operation_event(
    body: ClassifyOperationCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.classify(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/create-case",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationCreateCasePost",
    responses=_ERRORS,
)
def create_ecommerce_operation_case(
    body: CreateOperationCaseCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.create_case(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/change-membership",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationChangeMembershipPost",
    responses=_ERRORS,
)
def change_ecommerce_operation_membership(
    body: ChangeOperationMembershipCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.change_membership(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/manage-sla",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationManageSlaPost",
    responses=_ERRORS,
)
def manage_ecommerce_operation_sla(
    body: ManageOperationSlaCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.manage_sla(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/automation-kill",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationAutomationKillPost",
    responses=_ERRORS,
)
def kill_ecommerce_operation_automation(
    body: KillOperationAutomationCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.automation_kill(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.get(
    "/views/task-cockpit",
    response_model=TaskCockpitCoreEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitCoreGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_core(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
    status: Annotated[TaskStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
) -> TaskCockpitCoreEnvelope:
    _reject_unknown_query_parameters(
        request, allowed=frozenset({"status", "limit", "cursor"})
    )
    _require_task_cockpit_installation(
        principal=principal,
        catalog=catalog,
    )
    try:
        return cockpit.read_core(
            org_id=principal.org_id,
            project_id=principal.project_id,
            status=status,
            limit=limit,
            cursor=cursor,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/dispatch-scenario",
    response_model=DispatchScenarioContribution,
    operation_id="ecommerceWorkshopTaskCockpitDispatchScenarioGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_dispatch_scenario(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    scenario: DispatchScenarioDependency,
) -> DispatchScenarioContribution:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    return scenario.read(
        scope=TenantScope(principal.org_id, principal.project_id),
        cutoff=datetime.now(UTC),
    )


@router.get(
    "/views/task-cockpit/batch-scenario",
    response_model=BatchScenarioContribution,
    operation_id="ecommerceWorkshopTaskCockpitBatchScenarioGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_batch_scenario(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    scenario: BatchScenarioDependency,
) -> BatchScenarioContribution:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    return scenario.read(
        scope=TenantScope(principal.org_id, principal.project_id),
        cutoff=datetime.now(UTC),
    )


@router.get(
    "/views/task-cockpit/runs/{run_id}/production-context",
    response_model=TaskCockpitProductionContextEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunProductionContextGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_run_production_context(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
) -> TaskCockpitProductionContextEnvelope:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_production_context(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/skill-contributions",
    response_model=TaskCockpitSkillContributionEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunSkillContributionsGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_run_skill_contributions(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
) -> TaskCockpitSkillContributionEnvelope:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_skill_contributions(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/responsibility-handoffs",
    response_model=TaskCockpitResponsibilityHandoffEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunResponsibilityHandoffsGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_run_responsibility_handoffs(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
) -> TaskCockpitResponsibilityHandoffEnvelope:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_responsibility_handoffs(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.post(
    "/views/task-cockpit/runs/{run_id}/handoffs/compile",
    response_model=ModuleHandoffCompileResponse,
    operation_id="ecommerceWorkshopTaskCockpitRunHandoffCompile",
    responses=_ERRORS,
)
def compile_ecommerce_workshop_task_cockpit_run_handoff(
    request: Request,
    run_id: RunIdPath,
    body: ModuleHandoffCompileRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    compiler: HandoffCompilerDependency,
) -> ModuleHandoffCompileResponse:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return compiler.compile(
            TenantScope(principal.org_id, principal.project_id),
            run_id,
            body,
            roles=principal.roles,
            principal_markings=principal.markings,
        )
    except AssetRegistryError as exc:
        raise ApiError(
            code=exc.code.value,
            message=str(exc),
            status_code=exc.http_status,
            details=exc.details,
        ) from exc
    except ModuleHandoffCompilerDrift as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except ModuleHandoffCompilerError as exc:
        raise ApiError(
            code=exc.code,
            message="Workshop Handoff compilation failed closed",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/approval-review-issues",
    response_model=TaskCockpitApprovalReviewEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunApprovalReviewIssuesGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_run_approval_review_issues(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
) -> TaskCockpitApprovalReviewEnvelope:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_approval_review_issues(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/action-receipts",
    response_model=TaskCockpitActionReceiptEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunActionReceiptsGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_run_action_receipts(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
) -> TaskCockpitActionReceiptEnvelope:
    _reject_unknown_query_parameters(request, allowed=frozenset())
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_action_receipts(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/steps",
    response_model=TaskCockpitStepPageEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunStepsList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_task_cockpit_run_steps(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
) -> TaskCockpitStepPageEnvelope:
    _reject_unknown_query_parameters(
        request, allowed=frozenset({"limit", "cursor"})
    )
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_steps(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
            limit=limit,
            cursor=cursor,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/checkpoints",
    response_model=TaskCockpitCheckpointPageEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunCheckpointsList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_task_cockpit_run_checkpoints(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
) -> TaskCockpitCheckpointPageEnvelope:
    _reject_unknown_query_parameters(
        request, allowed=frozenset({"limit", "cursor"})
    )
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_checkpoints(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
            limit=limit,
            cursor=cursor,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc
