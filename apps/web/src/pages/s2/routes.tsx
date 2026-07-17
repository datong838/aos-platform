import type { ComponentType } from "react";
import { GraphExplorerPage, EventsPage } from "./workshop";
import {
  ToolsPage,
  ProvidersPage,
  ModelRouterPage,
  EvalsPage,
  DecisionLineagePage,
} from "./aip";
import { GraphHealthPage, FunnelPage, WikiPage, BranchesPage } from "./ontology";
import {
  MediaSetsPage,
  PipelinesPage,
  BuildsPage,
  DatasetsPage,
  SchedulesPage,
  DataHealthPage,
  EdgeAgentsPage,
} from "./data";
import { ApolloSpokePage, ApolloConfigPage, ApolloAssetsPage } from "./apollo";
import { MaturityPage, CopPage, ModuleInterfacePage } from "./extras";
import {
  OkfFunnelPage,
  PipelineProposalsPage,
  CodeReposPage,
  DataLineagePage,
  ApolloReleasePage,
  ApolloFerryPage,
  ApolloChangePage,
} from "./remainder";

/** Paths promoted in T-UI S2 knife-1～3 ([43]/[45]/[49]). */
export const S2_LIVE_ROUTES: { path: string; Component: ComponentType }[] = [
  { path: "workshop/graph", Component: GraphExplorerPage },
  { path: "workshop/events", Component: EventsPage },
  { path: "workshop/cop", Component: CopPage },
  { path: "workshop/module-interface", Component: ModuleInterfacePage },
  { path: "aip/tools", Component: ToolsPage },
  { path: "aip/model-providers", Component: ProvidersPage },
  { path: "aip/model-router", Component: ModelRouterPage },
  { path: "aip/evals", Component: EvalsPage },
  { path: "aip/lineage", Component: DecisionLineagePage },
  { path: "aip/maturity", Component: MaturityPage },
  { path: "ontology/graph-health", Component: GraphHealthPage },
  { path: "ontology/funnel", Component: FunnelPage },
  { path: "ontology/okf-funnel", Component: OkfFunnelPage },
  { path: "ontology/wiki", Component: WikiPage },
  { path: "ontology/branches", Component: BranchesPage },
  { path: "data/media-sets", Component: MediaSetsPage },
  { path: "data/pipelines", Component: PipelinesPage },
  { path: "data/pipeline-proposals", Component: PipelineProposalsPage },
  { path: "data/builds", Component: BuildsPage },
  { path: "data/datasets", Component: DatasetsPage },
  { path: "data/schedules", Component: SchedulesPage },
  { path: "data/code-repos", Component: CodeReposPage },
  { path: "data/lineage", Component: DataLineagePage },
  { path: "data/health", Component: DataHealthPage },
  { path: "data/agents", Component: EdgeAgentsPage },
  { path: "apollo/release", Component: ApolloReleasePage },
  { path: "apollo/spoke", Component: ApolloSpokePage },
  { path: "apollo/ferry", Component: ApolloFerryPage },
  { path: "apollo/assets", Component: ApolloAssetsPage },
  { path: "apollo/change", Component: ApolloChangePage },
  { path: "apollo/config", Component: ApolloConfigPage },
];

export const S2_LIVE_PATHS = new Set(S2_LIVE_ROUTES.map((r) => `/${r.path}`));
