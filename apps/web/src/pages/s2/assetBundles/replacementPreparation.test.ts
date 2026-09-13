import { describe, it, expect, vi } from 'vitest';
import { AssetControlClient } from '../../../api/assetControl/client';
import { INSTALLATION_ACTIVE_FIXTURE as installation } from '../../../api/assetControl/installationActionFixtures';
import { STORED_COMPOSITION_LOCK_FIXTURE as lock } from '../../../api/assetControl/compositionFixtures';
import { prepareReplacement, replaceRequestedVersion } from './replacementPreparation';
function client() {
  const value = new AssetControlClient({ fetch: vi.fn(() => { throw new Error('unexpected write or network'); }) });
  vi.spyOn(value, 'getInstallation').mockResolvedValue(installation);
  vi.spyOn(value, 'getCompositionLock').mockResolvedValue(lock);
  const node = lock.payload.resolved[0]!;
  vi.spyOn(value, 'getRegistryBundleVersion').mockResolvedValue({ publisher: node.publisher, bundleId: node.id, version: node.version, contentHash: node.contentHash, status: 'published', signature: { signature: 'fixture' } } as Awaited<ReturnType<typeof value.getRegistryBundleVersion>>);
  return value;
}
describe('prepare replacement without effects', () => {
  it('pins original root version and current exact predecessor without historical registry snapshot', async () => {
    const api = client(); const result = await prepareReplacement(installation.installationId, api, () => 'actor-a');
    expect(result.request.requested[0]!.version).toBe('1.0.0');
    expect(result.request.registrySnapshotHash).toBeUndefined();
    expect(result.request.currentInstallationRef).toEqual({ installationId: installation.installationId, revision: installation.currentRevision, lockHash: installation.current.lockHash, overlayRevision: installation.current.overlayRevision });
    expect(api.getInstallation).toHaveBeenCalledTimes(2);
  });
  it('rejects stale installation or identity during read', async () => {
    const api = client(); vi.mocked(api.getInstallation).mockResolvedValueOnce(installation).mockResolvedValueOnce({ ...installation, etagVersion: installation.etagVersion + 1 });
    await expect(prepareReplacement(installation.installationId, api, () => 'actor')).rejects.toThrow('状态已变化');
    let n = 0; await expect(prepareReplacement(installation.installationId, client(), () => String(n++))).rejects.toThrow('身份已变化');
  });
  it('rejects changed lock and withdrawn package', async () => {
    const api = client(); vi.mocked(api.getCompositionLock).mockResolvedValue({ ...lock, lockHash: 'sha256:bad' });
    await expect(prepareReplacement(installation.installationId, api, () => 'actor')).rejects.toThrow('安装锁');
    const other = client(); const version = await other.getRegistryBundleVersion('commerce', '1.0.0', 'aos');
    vi.mocked(other.getRegistryBundleVersion).mockResolvedValue({ ...version, signature: null });
    await expect(prepareReplacement(installation.installationId, other, () => 'actor')).rejects.toThrow('版本当前不可用');
  });
  it('keeps all other roots when selecting an upgraded package', async () => {
    const prepared = await prepareReplacement(installation.installationId, client(), () => 'actor');
    const second = { publisher: 'aos', id: 'adapter', version: '1.5.0' };
    const request = { ...prepared.request, requested: [...prepared.request.requested, second] };
    const result = replaceRequestedVersion(request, { publisher: 'aos', id: 'commerce', version: '1.8.0' });
    expect(result.requested).toContainEqual(second); expect(result.requested).toHaveLength(2);
    expect(result.currentInstallationRef).toEqual(request.currentInstallationRef);
  });
});
