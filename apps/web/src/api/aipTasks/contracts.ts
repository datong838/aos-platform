import {
  TASK_RUN_STATUSES,
  TASK_STATUSES,
  assertKnownStatus,
  type ResourceRef,
  type TaskRunStatus,
  type TaskStatus,
} from "../aip/contracts";

export type ActorRef = { actorType: string; actorId: string };
export type PlanStep = {
  stepKey: string;
  title: string;
  capabilityRef?: ResourceRef | null;
  inputRefs?: ResourceRef[];
};

export type TaskSnapshot = {
  id: string;
  type: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: number;
  goal: Record<string, unknown>;
  selectionRef: ResourceRef | null;
  policyRevision: string | null;
  createdBy: ActorRef;
  createdAt: string;
  currentPlanRevisionId: string | null;
  version: number;
  updatedAt: string;
};

export type PlanRevisionSnapshot = {
  id: string;
  taskId: string;
  revision: number;
  contentHash: string;
  steps: PlanStep[];
  dependencies: Array<Record<string, unknown>>;
  risk: Record<string, unknown>;
  approvalStatus: "draft" | "approved" | "superseded" | "rejected";
  approvedBy: string | null;
  approvedAt: string | null;
  createdBy: ActorRef;
  createdAt: string;
};

export type TaskRunSnapshot = {
  id: string;
  taskId: string;
  planRevisionId: string;
  status: TaskRunStatus;
  startedAt: string | null;
  finishedAt: string | null;
  lastCheckpointId: string | null;
  logicGraphId: string | null;
  logicRevision: number | null;
  version: number;
  createdBy: ActorRef;
  createdAt: string;
  updatedAt: string;
};

export type TaskRunListResponse = { items: TaskRunSnapshot[]; count: number };
export type TaskTimeline = {
  task: TaskSnapshot;
  plan: PlanRevisionSnapshot;
  run: TaskRunSnapshot;
  steps: Array<Record<string, unknown>>;
  checkpoints: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
};
export type RunControlResult = { task: TaskSnapshot; run: TaskRunSnapshot };

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 响应格式无效`);
  return value as Record<string, unknown>;
}
function stringValue(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${label} 缺失`);
  return value;
}
function nullableString(value: unknown, label: string): string | null {
  return value === null ? null : stringValue(value, label);
}
function positiveInt(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new TypeError(`${label} 无效`);
  return value as number;
}
function actor(value: unknown, label: string): ActorRef {
  const item = record(value, label);
  return { actorType: stringValue(item.actorType, `${label}.actorType`), actorId: stringValue(item.actorId, `${label}.actorId`) };
}
function objectValue(value: unknown, label: string): Record<string, unknown> {
  return record(value, label);
}
function records(value: unknown, label: string): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) throw new TypeError(`${label} 必须是数组`);
  return value.map((item, index) => record(item, `${label}[${index}]`));
}

export function parseTaskSnapshot(value: unknown): TaskSnapshot {
  const item = record(value, "Task");
  return {
    id: stringValue(item.id, "Task.id"), type: stringValue(item.type, "Task.type"),
    title: stringValue(item.title, "Task.title"), description: typeof item.description === "string" ? item.description : "",
    status: assertKnownStatus(item.status, TASK_STATUSES, "Task.status"),
    priority: typeof item.priority === "number" ? item.priority : 0,
    goal: objectValue(item.goal ?? {}, "Task.goal"),
    selectionRef: item.selectionRef === null || item.selectionRef === undefined ? null : item.selectionRef as ResourceRef,
    policyRevision: item.policyRevision === null || item.policyRevision === undefined ? null : stringValue(item.policyRevision, "Task.policyRevision"),
    createdBy: actor(item.createdBy, "Task.createdBy"), createdAt: stringValue(item.createdAt, "Task.createdAt"),
    currentPlanRevisionId: item.currentPlanRevisionId === null ? null : nullableString(item.currentPlanRevisionId, "Task.currentPlanRevisionId"),
    version: positiveInt(item.version, "Task.version"), updatedAt: stringValue(item.updatedAt, "Task.updatedAt"),
  };
}

export function parsePlanRevision(value: unknown): PlanRevisionSnapshot {
  const item = record(value, "PlanRevision");
  if (!Array.isArray(item.steps)) throw new TypeError("PlanRevision.steps 必须是数组");
  const approval = stringValue(item.approvalStatus, "PlanRevision.approvalStatus");
  if (!["draft", "approved", "superseded", "rejected"].includes(approval)) throw new TypeError("PlanRevision.approvalStatus 未知");
  return {
    id: stringValue(item.id, "PlanRevision.id"), taskId: stringValue(item.taskId, "PlanRevision.taskId"),
    revision: positiveInt(item.revision, "PlanRevision.revision"), contentHash: stringValue(item.contentHash, "PlanRevision.contentHash"),
    steps: item.steps.map((raw, index) => {
      const step = record(raw, `PlanRevision.steps[${index}]`);
      return { stepKey: stringValue(step.stepKey, "stepKey"), title: stringValue(step.title, "title") };
    }),
    dependencies: records(item.dependencies ?? [], "PlanRevision.dependencies"), risk: objectValue(item.risk ?? {}, "PlanRevision.risk"),
    approvalStatus: approval as PlanRevisionSnapshot["approvalStatus"],
    approvedBy: item.approvedBy === null ? null : nullableString(item.approvedBy, "PlanRevision.approvedBy"),
    approvedAt: item.approvedAt === null ? null : nullableString(item.approvedAt, "PlanRevision.approvedAt"),
    createdBy: actor(item.createdBy, "PlanRevision.createdBy"), createdAt: stringValue(item.createdAt, "PlanRevision.createdAt"),
  };
}

export function parseTaskRun(value: unknown): TaskRunSnapshot {
  const item = record(value, "TaskRun");
  return {
    id: stringValue(item.id, "TaskRun.id"), taskId: stringValue(item.taskId, "TaskRun.taskId"),
    planRevisionId: stringValue(item.planRevisionId, "TaskRun.planRevisionId"),
    status: assertKnownStatus(item.status, TASK_RUN_STATUSES, "TaskRun.status"),
    startedAt: item.startedAt === null ? null : nullableString(item.startedAt, "TaskRun.startedAt"),
    finishedAt: item.finishedAt === null ? null : nullableString(item.finishedAt, "TaskRun.finishedAt"),
    lastCheckpointId: item.lastCheckpointId === null ? null : nullableString(item.lastCheckpointId, "TaskRun.lastCheckpointId"),
    logicGraphId: item.logicGraphId === null ? null : nullableString(item.logicGraphId, "TaskRun.logicGraphId"),
    logicRevision: item.logicRevision === null ? null : positiveInt(item.logicRevision, "TaskRun.logicRevision"),
    version: positiveInt(item.version, "TaskRun.version"), createdBy: actor(item.createdBy, "TaskRun.createdBy"),
    createdAt: stringValue(item.createdAt, "TaskRun.createdAt"), updatedAt: stringValue(item.updatedAt, "TaskRun.updatedAt"),
  };
}

export function parseTaskRunList(value: unknown): TaskRunListResponse {
  const item = record(value, "TaskRunList");
  if (!Array.isArray(item.items) || typeof item.count !== "number") throw new TypeError("TaskRunList 响应格式无效");
  const items = item.items.map(parseTaskRun);
  if (items.length !== item.count) throw new TypeError("TaskRunList count 不一致");
  return { items, count: item.count };
}

export function parseTimeline(value: unknown): TaskTimeline {
  const item = record(value, "TaskTimeline");
  const task = parseTaskSnapshot(item.task);
  const plan = parsePlanRevision(item.plan);
  const run = parseTaskRun(item.run);
  if (plan.taskId !== task.id || run.taskId !== task.id || run.planRevisionId !== plan.id) throw new TypeError("TaskTimeline 资源引用不一致");
  return { task, plan, run, steps: records(item.steps, "steps"), checkpoints: records(item.checkpoints, "checkpoints"), artifacts: records(item.artifacts, "artifacts"), evidence: records(item.evidence, "evidence") };
}

export function parseControlResult(value: unknown): RunControlResult {
  const item = record(value, "RunControlResult");
  const task = parseTaskSnapshot(item.task);
  const run = parseTaskRun(item.run);
  if (run.taskId !== task.id) throw new TypeError("RunControlResult 资源引用不一致");
  return { task, run };
}
