import { aipClient, type AipClient } from "../aip/client";
import {
  parseControlResult,
  parsePlanRevision,
  parseTaskRun,
  parseTaskRunList,
  parseTaskSnapshot,
  parseTimeline,
  type PlanRevisionSnapshot,
  type PlanStep,
  type RunControlResult,
  type TaskRunListResponse,
  type TaskRunSnapshot,
  type TaskSnapshot,
  type TaskTimeline,
} from "./contracts";

function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export class AipTasksSdk {
  constructor(private readonly client: AipClient = aipClient) {}

  async createTask(input: {
    title: string;
    description?: string;
    type?: string;
    priority?: number;
    goal?: Record<string, unknown>;
    idempotencyKey?: string;
  }): Promise<TaskSnapshot> {
    const { idempotencyKey: suppliedKey, ...body } = input;
    const requestKey = suppliedKey?.trim() || idempotencyKey("task");
    if (requestKey.length < 8 || requestKey.length > 200) throw new TypeError("Idempotency-Key 长度必须为 8～200 个字符");
    return parseTaskSnapshot(await this.client.request("createTask", { body, headers: { "Idempotency-Key": requestKey } }));
  }

  async getTask(taskId: string): Promise<TaskSnapshot> {
    return parseTaskSnapshot(await this.client.request("getTask", { params: { task_id: taskId } }));
  }

  async createPlan(task: TaskSnapshot, steps: PlanStep[]): Promise<PlanRevisionSnapshot> {
    return parsePlanRevision(await this.client.request("createPlanRevision", {
      params: { task_id: task.id }, headers: { "Idempotency-Key": idempotencyKey("plan") },
      body: { expectedTaskVersion: task.version, steps },
    }));
  }

  async approvePlan(task: TaskSnapshot, plan: PlanRevisionSnapshot): Promise<PlanRevisionSnapshot> {
    return parsePlanRevision(await this.client.request("approvePlanRevision", {
      params: { task_id: task.id, revision: String(plan.revision) }, headers: { "Idempotency-Key": idempotencyKey("approve") },
      body: { expectedTaskVersion: task.version, expectedContentHash: plan.contentHash },
    }));
  }

  async createRun(task: TaskSnapshot, plan: PlanRevisionSnapshot, logic: { graphId: string; revision: number }): Promise<TaskRunSnapshot> {
    return parseTaskRun(await this.client.request("createTaskRun", {
      params: { task_id: task.id }, headers: { "Idempotency-Key": idempotencyKey("run") },
      body: { planRevisionId: plan.id, expectedTaskVersion: task.version, logicGraphId: logic.graphId, logicRevision: logic.revision },
    }));
  }

  async listRunsByLogic(graphId: string, limit = 20): Promise<TaskRunListResponse> {
    return parseTaskRunList(await this.client.request("listTaskRunsByLogic", { params: { logic_graph_id: graphId, limit: String(limit) } }));
  }

  async timeline(runId: string): Promise<TaskTimeline> {
    return parseTimeline(await this.client.request("getTaskRunTimeline", { params: { run_id: runId } }));
  }

  async control(operation: "start" | "pause" | "resume" | "cancel" | "rollback", timeline: TaskTimeline, reason: string): Promise<RunControlResult> {
    const operationId = `${operation}TaskRun` as const;
    return parseControlResult(await this.client.request(operationId, {
      params: { run_id: timeline.run.id }, headers: { "Idempotency-Key": idempotencyKey(operation) },
      body: { expectedRunVersion: timeline.run.version, expectedTaskVersion: timeline.task.version, reason },
    }));
  }
}

export const aipTasksSdk = new AipTasksSdk();
