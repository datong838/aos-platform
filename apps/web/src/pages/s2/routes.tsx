import { lazy, type ComponentType } from "react";
import type { LazyExoticComponent } from "react";

function lazify<T extends ComponentType<any>>(
  factory: () => Promise<Record<string, unknown>>,
  name: string,
): LazyExoticComponent<T> {
  return lazy(() =>
    factory().then((m) => ({ default: m[name] as T })),
  );
}

const GraphExplorerPage = lazify(() => import("./workshop"), "GraphExplorerPage");
const EventsPage = lazify(() => import("./EventsPage"), "EventsPage");
const ToolsPage = lazify(() => import("./aip"), "ToolsPage");
const ProvidersPage = lazify(() => import("./aip"), "ProvidersPage");
const ProviderDetailPage = lazify(() => import("./aip"), "ProviderDetailPage");
const ModelRouterPage = lazify(() => import("./aip"), "ModelRouterPage");
const EvalsPage = lazify(() => import("./aip"), "EvalsPage");
const DecisionLineagePage = lazify(() => import("./aip"), "DecisionLineagePage");
const GraphHealthPage = lazify(() => import("./ontology"), "GraphHealthPage");
const FunnelPage = lazify(() => import("./ontology"), "FunnelPage");
const WikiPage = lazify(() => import("./ontology"), "WikiPage");
const BranchesPage = lazify(() => import("./ontology"), "BranchesPage");
const ObjectTypeDetailPage = lazify(() => import("./ObjectTypeDetailPage"), "ObjectTypeDetailPage");
const LinkTypeEditorPage = lazify(() => import("./LinkTypeEditorPage"), "LinkTypeEditorPage");
const ActionTypeEditorPage = lazify(() => import("./ActionTypeEditorPage"), "ActionTypeEditorPage");
const MediaSetsPage = lazify(() => import("./MediaSetsPage"), "MediaSetsPage");
const PipelinesPage = lazify(() => import("./data"), "PipelinesPage");
const BuildsPage = lazify(() => import("./data"), "BuildsPage");
const DatasetsPage = lazify(() => import("./data"), "DatasetsPage");
const SchedulesPage = lazify(() => import("./data"), "SchedulesPage");
const EdgeAgentsPage = lazify(() => import("./data"), "EdgeAgentsPage");
const PipelineCanvasPage = lazify(() => import("./pipelineCanvas"), "PipelineCanvasPage");
const SourceDetailPage = lazify(() => import("./sourceDetailPage"), "SourceDetailPage");
const ApolloConfigPage = lazify(() => import("./ConfigSecretsPage"), "ConfigSecretsPage");
const ApolloAssetsPage = lazify(() => import("./AssetBundlesPage"), "AssetBundlesPage");
const ReleasesPage = lazify(() => import("./ReleasesPage"), "ReleasesPage");
const SpokeDetailPage = lazify(() => import("./SpokeDetailPage"), "SpokeDetailPage");
const MaturityPage = lazify(() => import("./extras"), "MaturityPage");
const CopPage = lazify(() => import("./extras"), "CopPage");
const ModuleInterfacePage = lazify(() => import("./extras"), "ModuleInterfacePage");
const OkfFunnelPage = lazify(() => import("./remainder"), "OkfFunnelPage");
const PipelineProposalsPage = lazify(() => import("./remainder"), "PipelineProposalsPage");
const ApolloFerryPage = lazify(() => import("./FerryPage"), "FerryPage");
const ApolloChangePage = lazify(() => import("./ChangeOrdersPage"), "ChangeOrdersPage");
const SyncConfigPage = lazify(() => import("./SyncConfigPage"), "SyncConfigPage");
const SyncRoutesPage = lazify(() => import("./SyncRoutesPage"), "SyncRoutesPage");
const OkfOverviewPage = lazify(() => import("./remainder"), "OkfOverviewPage");
const IntegrationCasesPage = lazify(() => import("./IntegrationCasesPage"), "IntegrationCasesPage");
const AnalyticsPage = lazify(() => import("./analytics"), "AnalyticsPage");
const ObservabilityPage = lazify(() => import("./ObservabilityPage"), "ObservabilityPage");
const MemoryGovernancePage = lazify(() => import("./MemoryGovernancePage"), "MemoryGovernancePage");
const LogicCanvasPage = lazify(() => import("./LogicCanvasPage"), "LogicCanvasPage");
const AgentsPage = lazify(() => import("./CanonicalAgentsPage"), "CanonicalAgentsPage");
const CanonicalAgentRegistryPage = lazify(() => import("./CanonicalAgentRegistryPage"), "CanonicalAgentRegistryPage");
const CanonicalCapabilityPage = lazify(() => import("../CanonicalCapabilityPage"), "CanonicalCapabilityPage");
const ProductionContractsPage = lazify(() => import("./ProductionContractsPage"), "ProductionContractsPage");
const AgentImportPage = lazify(() => import("./AgentImportPage"), "AgentImportPage");
const CapabilityImportPage = lazify(() => import("./CapabilityImportPage"), "CapabilityImportPage");
const WorkshopCreatePage = lazify(() => import("./WorkshopCreatePage"), "WorkshopCreatePage");
const WorkshopModulePage = lazify(() => import("./WorkshopModulePage"), "WorkshopModulePage");
const WikiIndexPage = lazify(() => import("./WikiIndexPage"), "WikiIndexPage");
const WidgetRegistryPage = lazify(() => import("./WidgetRegistryPage"), "WidgetRegistryPage");
const VariablesPage = lazify(() => import("./VariablesPage"), "VariablesPage");
const StylesPage = lazify(() => import("./StylesPage"), "StylesPage");
const DataConnectionPage = lazify(() => import("./DataConnectionPage"), "DataConnectionPage");
const DataSourceCreatePage = lazify(() => import("./DataSourceCreatePage"), "DataSourceCreatePage");
const RiskAlertPage = lazify(() => import("./RiskAlertPage"), "RiskAlertPage");
const PropertyEditorPage = lazify(() => import("./PropertyEditorPage"), "PropertyEditorPage");
const FunctionEditorPage = lazify(() => import("./FunctionEditorPage"), "FunctionEditorPage");
const WikiDetailPage = lazify(() => import("./WikiDetailPage"), "WikiDetailPage");
const WikiDiffPage = lazify(() => import("./WikiDiffPage"), "WikiDiffPage");
const DatasetPreviewPage = lazify(() => import("./DatasetPreviewPage"), "DatasetPreviewPage");
const DataHealthPage = lazify(() => import("./DataHealthPage"), "DataHealthPage");
const CodeRepositoriesPage = lazify(() => import("./CodeRepositoriesPage"), "CodeRepositoriesPage");
const DataLineagePage = lazify(() => import("./DataLineagePage"), "DataLineagePage");
const BuildModalPage = lazify(() => import("./BuildModalPage"), "BuildModalPage");

// Phase 7 · 系统管理 + 全局搜索
const UserSettingsPage = lazify(() => import("./UserSettingsPage"), "UserSettingsPage");
const AuditLogPage = lazify(() => import("./AuditLogPage"), "AuditLogPage");
const PermissionManagerPage = lazify(() => import("./PermissionManagerPage"), "PermissionManagerPage");

/** Paths promoted in T-UI S2 knife-1～3 ([43]/[45]/[49]). */
export const S2_LIVE_ROUTES: { path: string; Component: ComponentType }[] = [
  { path: "workshop/graph", Component: GraphExplorerPage },
  { path: "workshop/events", Component: EventsPage },
  { path: "workshop/cop", Component: CopPage },
  { path: "workshop/module-interface", Component: ModuleInterfacePage },
  { path: "aip/tools", Component: ToolsPage },
  { path: "aip/model-providers", Component: ProvidersPage },
  { path: "aip/model-providers/:providerId", Component: ProviderDetailPage },
  { path: "aip/model-router", Component: ModelRouterPage },
  { path: "aip/evals", Component: EvalsPage },
  { path: "aip/lineage", Component: DecisionLineagePage },
  { path: "aip/maturity", Component: MaturityPage },
  { path: "ontology/graph-health", Component: GraphHealthPage },
  { path: "ontology/funnel", Component: FunnelPage },
  { path: "ontology/okf-funnel", Component: OkfFunnelPage },
  { path: "ontology/wiki", Component: WikiPage },
  { path: "ontology/branches", Component: BranchesPage },
  { path: "ontology/object-types/:typeId", Component: ObjectTypeDetailPage },
  { path: "ontology/link-types/:linkId", Component: LinkTypeEditorPage },
  { path: "ontology/action-types/:actionId", Component: ActionTypeEditorPage },
  { path: "data/media-sets", Component: MediaSetsPage },
  { path: "data/connections", Component: DataConnectionPage },
  { path: "data/sources/new", Component: DataSourceCreatePage },
  { path: "data/sources/:sourceId", Component: SourceDetailPage },
  { path: "data/pipelines", Component: PipelinesPage },
  { path: "data/pipelines/:pipelineId", Component: PipelineCanvasPage },
  { path: "data/pipeline-proposals", Component: PipelineProposalsPage },
  { path: "data/builds", Component: BuildsPage },
  { path: "data/datasets", Component: DatasetsPage },
  { path: "data/schedules", Component: SchedulesPage },
  { path: "data/code-repos", Component: CodeRepositoriesPage },
  { path: "data/lineage", Component: DataLineagePage },
  { path: "data/health", Component: DataHealthPage },
  { path: "data/datasets/:datasetId", Component: DatasetPreviewPage },
  { path: "data/builds/current", Component: BuildModalPage },
  { path: "data/agents", Component: EdgeAgentsPage },
  { path: "data/sync-config", Component: SyncConfigPage },
  { path: "data/sync-routes", Component: SyncRoutesPage },
  { path: "ontology/okf-overview", Component: OkfOverviewPage },
  { path: "apollo/cases", Component: IntegrationCasesPage },
  { path: "apollo/release", Component: ReleasesPage },
  { path: "apollo/spoke", Component: SpokeDetailPage },
  { path: "apollo/ferry", Component: ApolloFerryPage },
  { path: "apollo/assets", Component: ApolloAssetsPage },
  { path: "apollo/change", Component: ApolloChangePage },
  { path: "apollo/config", Component: ApolloConfigPage },
  { path: "analytics", Component: AnalyticsPage },
  { path: "aip/observability", Component: ObservabilityPage },
  { path: "aip/memory-governance", Component: MemoryGovernancePage },
  { path: "aip/logic", Component: LogicCanvasPage },
  { path: "aip/logic/:flowId", Component: LogicCanvasPage },
  { path: "aip/agent-registry", Component: CanonicalAgentRegistryPage },
  { path: "aip/agents", Component: AgentsPage },
  { path: "aip/capabilities", Component: CanonicalCapabilityPage },
  { path: "aip/production-contracts", Component: ProductionContractsPage },
  { path: "aip/agent-import", Component: AgentImportPage },
  { path: "aip/capability-import", Component: CapabilityImportPage },
  { path: "workshop/create", Component: WorkshopCreatePage },
  { path: "workshop/module", Component: WorkshopModulePage },
  { path: "workshop/widget-registry", Component: WidgetRegistryPage },
  { path: "workshop/variables", Component: VariablesPage },
  { path: "workshop/styles", Component: StylesPage },
  { path: "ontology/wiki-index", Component: WikiIndexPage },
  { path: "workshop/risk-alerts", Component: RiskAlertPage },
  { path: "ontology/properties/:typeId", Component: PropertyEditorPage },
  { path: "ontology/functions", Component: FunctionEditorPage },
  { path: "ontology/wiki/:wikiId", Component: WikiDetailPage },
  { path: "ontology/wiki/:wikiId/diff", Component: WikiDiffPage },
  // Phase 7 · 系统管理
  { path: "settings/profile", Component: UserSettingsPage },
  { path: "settings/audit", Component: AuditLogPage },
  { path: "settings/permissions", Component: PermissionManagerPage },
];

export const S2_LIVE_PATHS = new Set(S2_LIVE_ROUTES.map((r) => `/${r.path}`));
