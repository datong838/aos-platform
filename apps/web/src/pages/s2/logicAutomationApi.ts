import { apiGetAuthoritative, apiPost, apiPut } from "../../api/client";
import type {
  LogicAutomationListResponse,
  LogicAutomationPolicy,
  LogicAutomationRun,
  LogicAutomationRunListResponse,
  LogicAutomationStatus,
  LogicAutomationTrigger,
} from "./logicAutomationContracts";

function graphPath(graphId: string): string {
  return `/v1/aip/logic/graphs/${encodeURIComponent(graphId)}/automations`;
}

export function listLogicAutomations(graphId: string): Promise<LogicAutomationListResponse> {
  return apiGetAuthoritative(graphPath(graphId));
}

export function createLogicAutomation(
  graphId: string,
  body: { publication_id: string; name: string; trigger_type: LogicAutomationTrigger; schedule: string },
): Promise<LogicAutomationPolicy> {
  return apiPost(graphPath(graphId), body);
}

export function updateLogicAutomation(
  graphId: string,
  automationId: string,
  body: { expected_revision: number; status?: LogicAutomationStatus; name?: string; schedule?: string },
): Promise<LogicAutomationPolicy> {
  return apiPut(`${graphPath(graphId)}/${encodeURIComponent(automationId)}`, body);
}

export function triggerLogicAutomation(
  graphId: string,
  automationId: string,
  idempotencyKey: string,
): Promise<LogicAutomationRun> {
  return apiPost(
    `${graphPath(graphId)}/${encodeURIComponent(automationId)}/trigger`,
    {},
    { "Idempotency-Key": idempotencyKey },
  );
}

export function listLogicAutomationRuns(
  graphId: string,
  automationId: string,
): Promise<LogicAutomationRunListResponse> {
  return apiGetAuthoritative(`${graphPath(graphId)}/${encodeURIComponent(automationId)}/runs`);
}
