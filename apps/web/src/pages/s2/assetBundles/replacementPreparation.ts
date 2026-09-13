import { assetControlClient } from '../../../api/assetControl/client';
import type { CompositionRequest, InstallationResponse, RequestedBundle } from '../../../api/assetControl/types';
import { configurationIdentity } from './readHooks';

export class ReplacementPreparationError extends Error {}

export function replaceRequestedVersion(request: CompositionRequest, selected: RequestedBundle): CompositionRequest {
  if (!request.currentInstallationRef) return { ...request, requested: [selected] };
  const others = request.requested.filter(item => item.publisher !== selected.publisher || item.id !== selected.id);
  return { ...request, requested: [...others, selected] };
}
function currentKey(value: InstallationResponse) {
  return JSON.stringify([value.installationId, value.state, value.currentRevision, value.activeRevision, value.etagVersion,
    value.current.compositionId, value.current.lockRevision, value.current.lockHash, value.current.overlayRevision]);
}
export async function prepareReplacement(installationId: string, client = assetControlClient, identity = configurationIdentity) {
  const startIdentity = identity();
  function fresh() { if (identity() !== startIdentity) throw new ReplacementPreparationError('身份已变化，请重新准备替换计划'); }
  async function read<T>(operation: Promise<T>, message: string): Promise<T> {
    try { return await operation; } catch { throw new ReplacementPreparationError(message); }
  }
  const before = await read(client.getInstallation(installationId), '当前安装读取失败，请刷新安装列表'); fresh();
  if (before.installationId !== installationId || before.state !== 'active' || before.currentRevision !== before.activeRevision || before.current.revision !== before.currentRevision) throw new ReplacementPreparationError('需要当前活跃安装');
  const current = before.current;
  const lock = await read(client.getCompositionLock(current.compositionId, current.lockRevision), '当前安装的组合锁读取失败，请检查锁记录和读取权限'); fresh();
  if (lock.compositionId !== current.compositionId || lock.revision !== current.lockRevision || lock.lockHash !== current.lockHash
    || lock.permissionDiffHash !== current.permissionDiffHash || lock.migrationPlanHash !== current.migrationPlanHash || lock.contributionDiffHash !== current.contributionDiffHash) throw new ReplacementPreparationError('当前安装锁已变化');
  const requested: RequestedBundle[] = [];
  for (const root of lock.payload.request.requested) {
    const matches = lock.payload.resolved.filter(item => item.publisher === root.publisher && item.id === root.id);
    if (matches.length !== 1) throw new ReplacementPreparationError('当前安装根资产不完整');
    const resolved = matches[0]!;
    const version = await read(client.getRegistryBundleVersion(resolved.id, resolved.version, resolved.publisher), '原安装的版本详情读取失败，请检查资产目录'); fresh();
    if (version.publisher !== resolved.publisher || version.bundleId !== resolved.id || version.version !== resolved.version || version.status !== 'published' || !version.signature || version.contentHash !== resolved.contentHash) throw new ReplacementPreparationError('原安装版本当前不可用，请先检查资产目录');
    requested.push({ publisher: resolved.publisher, id: resolved.id, version: resolved.version });
  }
  const after = await read(client.getInstallation(installationId), '当前安装再次核验失败，请重新准备'); fresh();
  if (currentKey(before) !== currentKey(after)) throw new ReplacementPreparationError('安装状态已变化，请重新准备');
  const request: CompositionRequest = { ...lock.payload.request, requested,
    currentInstallationRef: { installationId, revision: before.currentRevision, lockHash: current.lockHash, overlayRevision: current.overlayRevision } };
  return { identity: startIdentity, request, draft: { displayName: `${before.displayName.slice(0,220)} · 恢复替换`, overlayRevision: current.overlayRevision } };
}
