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
const MediaSetsPage = lazify(() => import("./data"), "MediaSetsPage");
const PipelinesPage = lazify(() => import("./data"), "PipelinesPage");
const BuildsPage = lazify(() => import("./data"), "BuildsPage");
const DatasetsPage = lazify(() => import("./data"), "DatasetsPage");
const SchedulesPage = lazify(() => import("./data"), "SchedulesPage");
const DataHealthPage = lazify(() => import("./data"), "DataHealthPage");
const EdgeAgentsPage = lazify(() => import("./data"), "EdgeAgentsPage");
const PipelineCanvasPage = lazify(() => import("./pipelineCanvas"), "PipelineCanvasPage");
const SourceDetailPage = lazify(() => import("./sourceDetailPage"), "SourceDetailPage");
const ApolloSpokePage = lazify(() => import("./apollo"), "ApolloSpokePage");
const ApolloConfigPage = lazify(() => import("./apollo"), "ApolloConfigPage");
const ApolloAssetsPage = lazify(() => import("./apollo"), "ApolloAssetsPage");
const HubFleetPage = lazify(() => import("./HubFleetPage"), "HubFleetPage");
const ReleasesPage = lazify(() => import("./ReleasesPage"), "ReleasesPage");
const SpokeDetailPage = lazify(() => import("./SpokeDetailPage"), "SpokeDetailPage");
const MaturityPage = lazify(() => import("./extras"), "MaturityPage");
const CopPage = lazify(() => import("./extras"), "CopPage");
const ModuleInterfacePage = lazify(() => import("./extras"), "ModuleInterfacePage");
const OkfFunnelPage = lazify(() => import("./remainder"), "OkfFunnelPage");
const PipelineProposalsPage = lazify(() => import("./remainder"), "PipelineProposalsPage");
const CodeReposPage = lazify(() => import("./remainder"), "CodeReposPage");
const DataLineagePage = lazify(() => import("./remainder"), "DataLineagePage");
const ApolloReleasePage = lazify(() => import("./remainder"), "ApolloReleasePage");
const ApolloFerryPage = lazify(() => import("./remainder"), "ApolloFerryPage");
const ApolloChangePage = lazify(() => import("./remainder"), "ApolloChangePage");
const SyncConfigPage = lazify(() => import("./remainder"), "SyncConfigPage");
const SyncRoutesPage = lazify(() => import("./remainder"), "SyncRoutesPage");
const OkfOverviewPage = lazify(() => import("./remainder"), "OkfOverviewPage");
const IntegrationCasesPage = lazify(() => import("./remainder"), "IntegrationCasesPage");
const AnalyticsPage = lazify(() => import("./analytics"), "AnalyticsPage");
const OrderManagementPage = lazify(() => import("./OrderManagementPage"), "OrderManagementPage");
const ObservabilityPage = lazify(() => import("./ObservabilityPage"), "ObservabilityPage");
const LogicCanvasPage = lazify(() => import("./LogicCanvasPage"), "LogicCanvasPage");
const AgentRegistryPage = lazify(() => import("./AgentRegistryPage"), "AgentRegistryPage");
const AgentsPage = lazify(() => import("./AgentsPage"), "AgentsPage");
const AgentImportPage = lazify(() => import("./AgentImportPage"), "AgentImportPage");
const CapabilityImportPage = lazify(() => import("./CapabilityImportPage"), "CapabilityImportPage");
const WorkshopCreatePage = lazify(() => import("./WorkshopCreatePage"), "WorkshopCreatePage");
const WorkshopModulePage = lazify(() => import("./WorkshopModulePage"), "WorkshopModulePage");
const WikiIndexPage = lazify(() => import("./WikiIndexPage"), "WikiIndexPage");
const WidgetRegistryPage = lazify(() => import("./WidgetRegistryPage"), "WidgetRegistryPage");
const VariablesPage = lazify(() => import("./VariablesPage"), "VariablesPage");
const StylesPage = lazify(() => import("./StylesPage"), "StylesPage");

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
  { path: "data/sources/:sourceId", Component: SourceDetailPage },
  { path: "data/pipelines", Component: PipelinesPage },
  { path: "data/pipelines/:pipelineId", Component: PipelineCanvasPage },
  { path: "data/pipeline-proposals", Component: PipelineProposalsPage },
  { path: "data/builds", Component: BuildsPage },
  { path: "data/datasets", Component: DatasetsPage },
  { path: "data/schedules", Component: SchedulesPage },
  { path: "data/code-repos", Component: CodeReposPage },
  { path: "data/lineage", Component: DataLineagePage },
  { path: "data/health", Component: DataHealthPage },
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
  { path: "workshop/orders", Component: OrderManagementPage },
  { path: "aip/observability", Component: ObservabilityPage },
  { path: "aip/logic", Component: LogicCanvasPage },
  { path: "aip/agent-registry", Component: AgentRegistryPage },
  { path: "aip/agents", Component: AgentsPage },
  { path: "aip/agent-import", Component: AgentImportPage },
  { path: "aip/capability-import", Component: CapabilityImportPage },
  { path: "workshop/create", Component: WorkshopCreatePage },
  { path: "workshop/module", Component: WorkshopModulePage },
  { path: "workshop/widget-registry", Component: WidgetRegistryPage },
  { path: "workshop/variables", Component: VariablesPage },
  { path: "workshop/styles", Component: StylesPage },
  { path: "ontology/wiki-index", Component: WikiIndexPage },
];

export const S2_LIVE_PATHS = new Set(S2_LIVE_ROUTES.map((r) => `/${r.path}`));
