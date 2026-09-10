export type SavedSource = { id: string; configurationRevision: string };
export type Discovery = { ok: boolean; sourceId: string; configurationRevision: string; tables: { name: string; type: string }[]; truncated: boolean; latencyMs: number };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function executableConfig(type: string, config: Record<string, string>): Record<string, string | number> {
  if (type !== 'jdbc-mysql-ssh') throw new Error('当前配置流程支持 MySQL SSH 隧道');
  const result: Record<string, string | number> = {};
  for (const key of ['sshHost','sshUser','sshPassword','sshKeyRef','dbHost','database','username','password','secretRef']) {
    if (config[key]) result[key] = config[key];
  }
  result.sshPort = Number(config.sshPort || 22);
  result.dbPort = Number(config.dbPort || 3306);
  return result;
}
export function verifySaved(value: SavedSource, id: string): SavedSource {
  if (!value || value.id !== id || !uuid.test(value.configurationRevision || '')) throw new Error('未确认配置保存结果，请重新读取数据源');
  return value;
}
export function verifyDiscovery(value: Discovery, saved: SavedSource): Discovery {
  if (!value?.ok || value.sourceId !== saved.id || value.configurationRevision !== saved.configurationRevision || !Array.isArray(value.tables)
      || value.tables.length > 500 || typeof value.truncated !== 'boolean'
      || value.tables.some(t => !t || typeof t.name !== 'string' || !t.name || typeof t.type !== 'string')) throw new Error('连接测试结果与当前配置不一致');
  return value;
}
