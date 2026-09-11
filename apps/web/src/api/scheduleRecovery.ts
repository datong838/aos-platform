import { apiPostImmediate } from './client';
import { getTenant } from './tenant';

export type RecoveryResult = { status: string; id?: string; lastRun?: { rowsWritten?: number } };
type PendingClaim = { claimId: string; finishedAt: string };

/** Request identity only; current execution authority is always checked by the server. */
export async function recoverScheduledRun(scheduleId: string, runId: string, finishedAt: string): Promise<RecoveryResult> {
  const tenant = getTenant();
  const key = JSON.stringify(['schedule-recovery-v1', tenant.orgId, tenant.projectId, tenant.subject ?? '', scheduleId, runId]);
  const raw = sessionStorage.getItem(key);
  let pending: PendingClaim | undefined;
  if (raw !== null) {
    try {
      pending = JSON.parse(raw) as PendingClaim;
      if (!pending || typeof pending.finishedAt !== 'string' || typeof pending.claimId !== 'string' || !/^[0-9a-f-]{36}$/.test(pending.claimId)) throw new Error();
    } catch { throw new Error('恢复请求记录无法读取，请先核对原运行状态'); }
  }
  if (!pending || (finishedAt && pending.finishedAt && finishedAt !== pending.finishedAt)) {
    pending = { claimId: crypto.randomUUID(), finishedAt };
    sessionStorage.setItem(key, JSON.stringify(pending));
  }
  const result = await apiPostImmediate<RecoveryResult>(`/v1/schedules/${encodeURIComponent(scheduleId)}/runs/${encodeURIComponent(runId)}/recover`, { claimId: pending.claimId });
  if ((result.status === 'succeeded' || result.status === 'failed') && sessionStorage.getItem(key) === JSON.stringify(pending)) sessionStorage.removeItem(key);
  return result;
}
