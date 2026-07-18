import { apiGet } from "./api/client";

export type OverviewMetrics = {
  health: string;
  sidecar: string;
  defaultModel: string;
  modules: number;
  models: number;
  plugins: number;
  tools: number;
  workOrders: number;
  pendingDrafts: number;
  objectTypePublished: boolean;
  datasets: number;
  builds: number;
  evalsGreen: boolean;
};

const EMPTY: OverviewMetrics = {
  health: "…",
  sidecar: "…",
  defaultModel: "—",
  modules: 0,
  models: 0,
  plugins: 0,
  tools: 0,
  workOrders: 0,
  pendingDrafts: 0,
  objectTypePublished: false,
  datasets: 0,
  builds: 0,
  evalsGreen: false,
};

/** W20 · 概览页只读指标聚合 */
export async function fetchOverviewMetrics(): Promise<OverviewMetrics> {
  const next = { ...EMPTY };

  try {
    const h = await apiGet<{ status: string }>("/v1/health");
    next.health = h.status;
  } catch (e) {
    next.health = String((e as Error).message || e);
  }

  const results = await Promise.allSettled([
    apiGet<{ items: unknown[] }>("/v1/modules"),
    apiGet<{ items: unknown[]; sidecar?: string; defaultTextModel?: string }>("/v1/aip/models"),
    apiGet<{ items: unknown[]; totals?: { all: number } }>("/v1/plugins"),
    apiGet<{ items: unknown[] }>("/v1/aip/tools"),
    apiGet<{
      snapshot?: {
        objectCount?: number;
        pendingDrafts?: number;
        objectTypePublished?: boolean;
        modules?: number;
      };
    }>("/v1/demo/story"),
    apiGet<{ items: unknown[] }>("/v1/datasets"),
    apiGet<{ items: unknown[] }>("/v1/builds"),
    apiGet<{ green?: boolean }>("/v1/aip/evals/status"),
  ]);

  const mod = results[0].status === "fulfilled" ? results[0].value : null;
  const models = results[1].status === "fulfilled" ? results[1].value : null;
  const plugins = results[2].status === "fulfilled" ? results[2].value : null;
  const tools = results[3].status === "fulfilled" ? results[3].value : null;
  const story = results[4].status === "fulfilled" ? results[4].value : null;
  const datasets = results[5].status === "fulfilled" ? results[5].value : null;
  const builds = results[6].status === "fulfilled" ? results[6].value : null;
  const evals = results[7].status === "fulfilled" ? results[7].value : null;

  next.modules = mod?.items?.length ?? story?.snapshot?.modules ?? 0;
  next.models = models?.items?.length ?? 0;
  next.plugins = plugins?.totals?.all ?? plugins?.items?.length ?? 0;
  next.tools = tools?.items?.length ?? 0;
  next.sidecar = models?.sidecar || "—";
  next.defaultModel = models?.defaultTextModel || "—";
  next.workOrders = story?.snapshot?.objectCount ?? 0;
  next.pendingDrafts = story?.snapshot?.pendingDrafts ?? 0;
  next.objectTypePublished = Boolean(story?.snapshot?.objectTypePublished);
  next.datasets = datasets?.items?.length ?? 0;
  next.builds = builds?.items?.length ?? 0;
  next.evalsGreen = Boolean(evals?.green);

  return next;
}
