/**
 * 147 · Web 适配层：租户上下文 → @aos/ontology-sdk
 */
import { createOntologyClient, type OntologyClient } from "@aos/ontology-sdk";
import { getApiBase } from "./apiBase";
import { getAccessToken, getTenant } from "./tenant";

/** 每次调用重建客户端，保证切区/换 token 立即生效（无缓存串区） */
export function getOntologyClient(): OntologyClient {
  const t = getTenant();
  return createOntologyClient({
    baseUrl: getApiBase(),
    token: getAccessToken() || "dev",
    orgId: t.orgId,
    projectId: t.projectId,
  });
}
