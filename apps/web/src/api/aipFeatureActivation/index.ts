import { apiGet, apiPost } from "../client";
import type { AipFeatureActivationCommandResponse, AipFeatureActivationList } from "./contracts";
import { parseAipFeatureActivationCommand, parseAipFeatureActivationList } from "./parser";

const ROOT = "/v1/ecommerce-workshop/aip-features";
const FEATURE = /^aip\.[a-z0-9]+(?:[.-][a-z0-9]+)*$/;
function id(value: string): string { if (!FEATURE.test(value)) throw new TypeError("featureId 无效"); return encodeURIComponent(value); }

export const aipFeatureActivation = {
  async list(): Promise<AipFeatureActivationList> {
    return parseAipFeatureActivationList(await apiGet<unknown>(ROOT));
  },
  async activate(input: { featureId: string; expectedRevision: number; contentHash: string; expiresAt: string }, key: string): Promise<AipFeatureActivationCommandResponse> {
    return parseAipFeatureActivationCommand(await apiPost<unknown>(`${ROOT}/${id(input.featureId)}/activate`, { expectedRevision: input.expectedRevision, contentHash: input.contentHash, expiresAt: input.expiresAt }, { "Idempotency-Key": key }));
  },
  async revoke(input: { featureId: string; expectedRevision: number }, key: string): Promise<AipFeatureActivationCommandResponse> {
    return parseAipFeatureActivationCommand(await apiPost<unknown>(`${ROOT}/${id(input.featureId)}/revoke`, { expectedRevision: input.expectedRevision }, { "Idempotency-Key": key }));
  },
};

export * from "./contracts";
