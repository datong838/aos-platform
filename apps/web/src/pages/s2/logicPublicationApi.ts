import { aipClient } from "../../api/aip/client";
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

async function readPublicationDetail(
  graphId: string,
  publicationId: string,
  request?: LogicPublishRequest,
): Promise<LogicPublication> {
  const response = await aipClient.request<unknown>("getLogicPublication", { params: { graph_id: graphId, publication_id: publicationId } });
  const normalized = normalizeLogicPublication(response, { graphId, ...(request ? { request } : {}) });
  if (normalized.publication_id !== publicationId) {
    throw new Error("publication_id 与请求路径不一致");
  }
  return normalized;
}

export async function listLogicPublications(graphId: string): Promise<LogicPublicationListResponse> {
  const safeGraphId = resourceId(graphId, "graphId");
  const response = await aipClient.request<unknown>("listLogicPublications", { params: { graph_id: safeGraphId } });
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
  const posted = normalizeLogicPublication(await aipClient.request<unknown>("publishLogicGraph", {
    params: { graph_id: safeGraphId },
    body: request,
  }), { graphId: safeGraphId, request });
  const reread = await readPublicationDetail(
    safeGraphId,
    posted.publication_id,
    request,
  );
  assertLogicPublicationDetailMatches(posted, reread);
  return reread;
}
