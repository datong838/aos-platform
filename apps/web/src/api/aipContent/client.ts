import { apiGet, apiPost } from "../client";
import { getTenant } from "../tenant";
import type {
  AvatarHeartbeatCommand,
  AvatarLiveCommand,
  AvatarReconcileCommand,
  AvatarSessionOpenRequest,
  AvatarSessionSnapshot,
  ExpectedVersionCommand,
  FailureCommand,
  MediaClaimCommand,
  MediaCompleteCommand,
  MediaJobCreateRequest,
  MediaJobSnapshot,
  MediaReconcileCommand,
  Tenant,
  UnknownCommand,
} from "./contracts";
import {
  parseAvatarSessionSnapshot,
  parseAvatarSessionSnapshots,
  parseMediaJobSnapshot,
  parseMediaJobSnapshots,
} from "./parser";

export type AipContentTransport = {
  get(path: string): Promise<unknown>;
  post(path: string, body: unknown, headers: Record<string, string>): Promise<unknown>;
};

const defaultTransport: AipContentTransport = {
  get: (path) => apiGet<unknown>(path),
  post: (path, body, headers) => apiPost<unknown>(path, body, headers),
};

export class AipContentSdk {
  constructor(
    private readonly transport: AipContentTransport = defaultTransport,
    private readonly tenantProvider: () => Tenant = getTenant,
  ) {}

  async listMediaJobs(limit = 100): Promise<MediaJobSnapshot[]> {
    return parseMediaJobSnapshots(
      await this.transport.get(`/v1/aip/content/media-jobs?limit=${validLimit(limit)}`),
      this.tenantProvider(),
    );
  }

  async getMediaJob(jobId: string): Promise<MediaJobSnapshot> {
    return parseMediaJobSnapshot(
      await this.transport.get(`/v1/aip/content/media-jobs/${encodedId(jobId)}`),
      this.tenantProvider(),
    );
  }

  async submitMediaJob(body: MediaJobCreateRequest, idempotencyKey: string): Promise<MediaJobSnapshot> {
    rejectAuthorityFields(body);
    return this.mediaPost("", body, idempotencyKey);
  }

  claimMediaJob(jobId: string, body: MediaClaimCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/claim`, validVersion(body), key); }
  heartbeatMediaJob(jobId: string, body: MediaClaimCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/heartbeat`, validVersion(body), key); }
  completeMediaJob(jobId: string, body: MediaCompleteCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/complete`, validVersion(body), key); }
  failMediaJob(jobId: string, body: FailureCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/fail`, validVersion(body), key); }
  cancelMediaJob(jobId: string, body: FailureCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/cancel`, validVersion(body), key); }
  markMediaJobUnknown(jobId: string, body: UnknownCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/mark-unknown`, validVersion(body), key); }
  reconcileMediaJob(jobId: string, body: MediaReconcileCommand, key: string) { return this.mediaPost(`/${encodedId(jobId)}/reconcile`, validVersion(body), key); }

  async listAvatarSessions(limit = 100): Promise<AvatarSessionSnapshot[]> {
    return parseAvatarSessionSnapshots(
      await this.transport.get(`/v1/aip/content/avatar-sessions?limit=${validLimit(limit)}`),
      this.tenantProvider(),
    );
  }

  async getAvatarSession(sessionId: string): Promise<AvatarSessionSnapshot> {
    return parseAvatarSessionSnapshot(
      await this.transport.get(`/v1/aip/content/avatar-sessions/${encodedId(sessionId)}`),
      this.tenantProvider(),
    );
  }

  async openAvatarSession(body: AvatarSessionOpenRequest, idempotencyKey: string): Promise<AvatarSessionSnapshot> {
    rejectAuthorityFields(body);
    return this.avatarPost("", body, idempotencyKey);
  }

  readyAvatarSession(id: string, body: ExpectedVersionCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/ready`, validVersion(body), key); }
  liveAvatarSession(id: string, body: AvatarLiveCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/live`, validVersion(body), key); }
  heartbeatAvatarSession(id: string, body: AvatarHeartbeatCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/heartbeat`, validVersion(body), key); }
  pauseAvatarSession(id: string, body: ExpectedVersionCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/pause`, validVersion(body), key); }
  resumeAvatarSession(id: string, body: AvatarLiveCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/resume`, validVersion(body), key); }
  closingAvatarSession(id: string, body: ExpectedVersionCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/closing`, validVersion(body), key); }
  closeAvatarSession(id: string, body: ExpectedVersionCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/close`, validVersion(body), key); }
  failAvatarSession(id: string, body: FailureCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/fail`, validVersion(body), key); }
  killAvatarSession(id: string, body: FailureCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/kill`, validVersion(body), key); }
  markAvatarSessionUnknown(id: string, body: UnknownCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/mark-unknown`, validVersion(body), key); }
  reconcileAvatarSession(id: string, body: AvatarReconcileCommand, key: string) { return this.avatarPost(`/${encodedId(id)}/reconcile`, validVersion(body), key); }

  private async mediaPost(path: string, body: unknown, key: string): Promise<MediaJobSnapshot> {
    rejectAuthorityFields(body);
    return parseMediaJobSnapshot(
      await this.transport.post(`/v1/aip/content/media-jobs${path}`, body, { "Idempotency-Key": validKey(key) }),
      this.tenantProvider(),
    );
  }

  private async avatarPost(path: string, body: unknown, key: string): Promise<AvatarSessionSnapshot> {
    rejectAuthorityFields(body);
    return parseAvatarSessionSnapshot(
      await this.transport.post(`/v1/aip/content/avatar-sessions${path}`, body, { "Idempotency-Key": validKey(key) }),
      this.tenantProvider(),
    );
  }
}

function encodedId(value: string): string {
  if (!value || value !== value.trim() || value.length > 240) throw new TypeError("content runtime id 无效");
  return encodeURIComponent(value);
}

function validKey(value: string): string {
  if (!value || value !== value.trim() || value.length > 120) throw new TypeError("Idempotency-Key 无效");
  return value;
}

function validLimit(value: number): number {
  if (!Number.isInteger(value) || value < 1 || value > 200) throw new TypeError("limit 必须是 1..200 的整数");
  return value;
}

function validVersion<T extends ExpectedVersionCommand>(body: T): T {
  if (!Number.isInteger(body.expectedVersion) || body.expectedVersion < 1) throw new TypeError("expectedVersion 必须是正整数");
  rejectAuthorityFields(body);
  return body;
}

function rejectAuthorityFields(value: unknown): void {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError("content runtime body 必须是对象");
  for (const key of ["tenant", "orgId", "projectId", "occurredAt"]) {
    if (Object.prototype.hasOwnProperty.call(value, key)) throw new TypeError(`content runtime body 禁止字段 ${key}`);
  }
}

export const aipContentSdk = new AipContentSdk();
export * from "./contracts";
