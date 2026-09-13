import { getApiBase } from './apiBase';
import { getTenant, tenantAuthHeaders } from './tenant';
import { parseUiSession } from './assetControl/runtimeInstallations';
import type { RuntimeUiSession } from './assetControl/types';

export type RuntimeWorkshopEntry = {
  module: { moduleId: string; displayName: string; menuLabel: string; route: string; order: number };
  moduleRef: Record<string, string>;
  installationId: string; installationRevision: number;
  generation: string; executionEpoch: number; bindingRevision: number;
  ui: RuntimeUiSession; resourceOnly: true;
};
export type RuntimeWorkshopCatalog = {
  schemaVersion: 'aos.runtime-workshop-catalog/v1';
  tenant: { orgId: string; projectId: string };
  evaluatedAt: string; dataCutoff: string | null;
  items: RuntimeWorkshopEntry[]; count: number;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const hash = /^sha256:[0-9a-f]{64}$/;
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('工作台目录格式无效');
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== 'string' || !value || value !== value.trim() || value.includes('\0')) throw new Error('工作台目录文本无效');
  return value;
}
function positive(value: unknown): number {
  if (!Number.isSafeInteger(value) || Number(value) < 1) throw new Error('工作台运行版本无效');
  return value as number;
}
function timestamp(value: unknown): string {
  const result = text(value);
  if (!result.includes('T') || !Number.isFinite(Date.parse(result))) throw new Error('工作台目录时间无效');
  return result;
}
function entry(value: unknown): RuntimeWorkshopEntry {
  const raw = record(value), module = record(raw.module), ref = record(raw.moduleRef);
  if (module.schema !== 'aos.workshop-module/v1' || raw.resourceOnly !== true) throw new Error('工作台目录协议不匹配');
  const installationId = text(raw.installationId), generation = text(raw.generation);
  if (!uuid.test(installationId) || !uuid.test(generation)) throw new Error('工作台运行身份无效');
  const route = text(module.route);
  if (!/^\/[a-zA-Z0-9._~-]+(?:\/[a-zA-Z0-9._~-]+)*$/.test(route) || route.split('/').some(p => p === '.' || p === '..')) throw new Error('工作台路径无效');
  const ui = parseUiSession(raw.ui);
  if (!ui || ui.initialRoute !== route || !ui.routeClaims.includes(route)) throw new Error('工作台资源不属于当前路径');
  const url = new URL(ui.signedResourceUrl);
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname)))
      || url.username || url.password || url.searchParams.getAll('contentHash').length !== 1
      || url.searchParams.get('contentHash') !== ui.resourceHash) throw new Error('工作台签名资源地址无效');
  const moduleRef: Record<string, string> = {};
  for (const key of ['publisher','bundleId','version','bundleContentHash','moduleArtifactRef','moduleArtifactHash']) moduleRef[key] = text(ref[key]);
  if (!hash.test(moduleRef.bundleContentHash) || !hash.test(moduleRef.moduleArtifactHash)) throw new Error('工作台来源摘要无效');
  if (!Number.isSafeInteger(module.order) || Number(module.order) < 0) throw new Error('工作台排序无效');
  return { module: { moduleId: text(module.moduleId), displayName: text(module.displayName), menuLabel: text(module.menuLabel), route, order: module.order as number },
    moduleRef, installationId, generation, installationRevision: positive(raw.installationRevision),
    executionEpoch: positive(raw.executionEpoch), bindingRevision: positive(raw.bindingRevision), ui, resourceOnly: true };
}
export function parseRuntimeWorkshopCatalog(value: unknown, tenant: { orgId: string; projectId: string }): RuntimeWorkshopCatalog {
  const raw = record(value), scope = record(raw.tenant);
  if (raw.schemaVersion !== 'aos.runtime-workshop-catalog/v1' || scope.orgId !== tenant.orgId || scope.projectId !== tenant.projectId
      || !Array.isArray(raw.items) || raw.count !== raw.items.length) throw new Error('工作台目录与当前租户不一致');
  const items = raw.items.map(entry);
  if (new Set(items.map(i => i.module.route)).size !== items.length || new Set(items.map(i => i.module.moduleId)).size !== items.length) throw new Error('工作台入口存在冲突');
  return { schemaVersion: 'aos.runtime-workshop-catalog/v1', tenant: { ...tenant }, evaluatedAt: timestamp(raw.evaluatedAt),
    dataCutoff: raw.dataCutoff === null ? null : timestamp(raw.dataCutoff), items, count: items.length };
}
export async function listRuntimeWorkshops(signal?: AbortSignal): Promise<RuntimeWorkshopCatalog> {
  const { orgId, projectId } = getTenant();
  const response = await fetch(`${getApiBase()}/v1/runtime-workshop/modules`, { headers: tenantAuthHeaders(), cache: 'no-store', signal });
  if (!response.ok) throw new Error('工作台目录读取失败，请刷新安装状态或检查访问权限。');
  return parseRuntimeWorkshopCatalog(await response.json(), { orgId, projectId });
}
