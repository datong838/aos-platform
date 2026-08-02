import { apiGet, apiPost } from "../../api/client";
import {
  assertLogicPublicationDetailMatches,
  assertLogicPublicationRequest,
  normalizeLogicPublication,
  normalizeLogicPublicationList,
  type LogicPublication,
  type LogicPublicationListResponse,
  type LogicPublishRequest,
} from "./logicPublicationContracts";

function resourceId(value: string, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} 必须是非空字符串`);
  return value;
}

function publicationDetailPath(graphId: string, publicationId: string): string {
  return `/v1/aip/logic/graphs/${encodeURIComponent(graphId)}/publications/${encodeURIComponent(publicationId)}`;
}

async function readPublicationDetail(
  graphId: string,
  publicationId: string,
  request?: LogicPublishRequest,
): Promise<LogicPublication> {
  const response = await apiGet<unknown>(publicationDetailPath(graphId, publicationId));
  const normalized = normalizeLogicPublication(response, { graphId, ...(request ? { request } : {}) });
  if (normalized.publication_id !== publicationId) {
    throw new Error("publication_id 与请求路径不一致");
  }
  return normalized;
}

export async function listLogicPublications(graphId: string): Promise<LogicPublicationListResponse> {
  const safeGraphId = resourceId(graphId, "graphId");
  const response = await apiGet<unknown>(
    `/v1/aip/logic/graphs/${encodeURIComponent(safeGraphId)}/publications`,
  );
  return normalizeLogicPublicationList(response, safeGraphId);
}

export async function getLogicPublication(
  graphId: string,
  publicationId: string,
): Promise<LogicPublication> {
  return readPublicationDetail(
    resourceId(graphId, "graphId"),
    resourceId(publicationId, "publicationId"),
  );
}

export async function publishLogicGraph(
  graphId: string,
  request: LogicPublishRequest,
): Promise<LogicPublication> {
  const safeGraphId = resourceId(graphId, "graphId");
  assertLogicPublicationRequest(request);
  const posted = normalizeLogicPublication(await apiPost<unknown>(
    `/v1/aip/logic/graphs/${encodeURIComponent(safeGraphId)}/publish`,
    request,
  ), { graphId: safeGraphId, request });
  const reread = await readPublicationDetail(
    safeGraphId,
    posted.publication_id,
    request,
  );
  assertLogicPublicationDetailMatches(posted, reread);
  return reread;
}
