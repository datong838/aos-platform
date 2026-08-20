export type OperationalTenant = { orgId: string; projectId: string };

export type OperationalStageCounts = {
  definition: number;
  bound: number;
  enabled: number;
  runnable: number;
};

export type AipOperationalProjection = {
  tenant: OperationalTenant;
  roles: OperationalStageCounts;
  capabilities: OperationalStageCounts;
  tools: OperationalStageCounts;
  evalGates: OperationalStageCounts;
  routes: OperationalStageCounts;
  overallReadiness: "ready" | "blocked";
  blockerCodes: string[];
  sources: {
    agentReadinessAt: string;
    modelRuntimeAt: string;
  };
  snapshotHash: string;
  generatedAt: string;
};
