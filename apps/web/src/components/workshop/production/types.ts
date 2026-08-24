export type ProductionUiState = "loading" | "empty" | "partial" | "stale" | "blocked" | "forbidden" | "unknown" | "ready" | "failed";

export type ProductionExactRef = {
  resourceType: string;
  resourceId: string;
  revision: number;
  contentHash: string;
};

export type ProductionBlocker = {
  code: string;
  message: string;
  owner: string;
  requiredAction: string;
  cutoffAt: string | null;
  href?: string;
};

export type ProductionReceipt = {
  receiptId: string;
  label: string;
  href?: string;
};

export type ProductionContributionLineage = {
  atomicSkillRef: ProductionExactRef | null;
  logicRef: ProductionExactRef | null;
  coworker: { roleName: string; assigneeId: string } | null;
  workshopContribution: string;
};

export type ProductionIntent<Kind extends string = string> = {
  kind: Kind;
  subjectRef: ProductionExactRef;
};

export type ProductionComponentBase<Kind extends string = string> = {
  title: string;
  state: ProductionUiState;
  lineage: ProductionContributionLineage;
  blockers: ProductionBlocker[];
  receipts?: ProductionReceipt[];
  allowedIntents?: readonly Kind[];
  onIntent?: (intent: ProductionIntent<Kind>) => void;
};

export type ProductionDiffRow = { field: string; before: string; after: string };
export type ProductionStage = { stageId: string; title: string; state: ProductionUiState; assignee: string | null };
