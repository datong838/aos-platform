import { useState, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { getAuthRevision, getTenant } from "../../api/tenant";
import { useJsonGet } from "./shared";

type Source = { id: string; name?: string; displayName?: string; configurationRevision?: string };
type Registration = { id: string; sourceId: string; sourceConfigurationRevision: string; datasetRid: string; name: string };
type Pending = Registration & { key: string };

function scopeIdentity(): string {
  const tenant = getTenant();
  return JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]);
}

function subscribe(listener: () => void): () => void {
  window.addEventListener("aos-tenant-updated", listener);
  window.addEventListener("aos-auth-updated", listener);
  return () => {
    window.removeEventListener("aos-tenant-updated", listener);
    window.removeEventListener("aos-auth-updated", listener);
  };
}

function storageKey(): string {
  const tenant = getTenant();
  return `aos:pipeline-registration:pending:${tenant.orgId}:${tenant.projectId}:${tenant.subject ?? ""}`;
}

function readPending(): Pending | null {
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return null;
    const item = JSON.parse(raw) as Pending;
    if (item && typeof item.id === "string" && typeof item.key === "string" && item.key &&
        typeof item.sourceId === "string" && typeof item.sourceConfigurationRevision === "string" &&
        typeof item.datasetRid === "string" && typeof item.name === "string") return item;
  } catch { /* Unknown local marker remains a freeze, never a resend permit. */ }
  return { id: "待对账标记不可读", sourceId: "", sourceConfigurationRevision: "",
           datasetRid: "", name: "", key: "" };
}

function matches(receipt: Registration, pending: Pending): boolean {
  return receipt.id === pending.id && receipt.sourceId === pending.sourceId &&
    receipt.sourceConfigurationRevision === pending.sourceConfigurationRevision &&
    receipt.datasetRid === pending.datasetRid && receipt.name === pending.name;
}

export function PipelineRegistrationPanel({ onRegistered }: { onRegistered: () => void }) {
  const scope = useSyncExternalStore(subscribe, scopeIdentity, scopeIdentity);
  return <Details key={scope} scope={scope} onRegistered={onRegistered} />;
}

function Details({ scope, onRegistered }: { scope: string; onRegistered: () => void }) {
  const { data, err, loading, reload } = useJsonGet<{ items: Source[] }>("/v1/sources", { authoritative: true });
  const [pending, setPending] = useState<Pending | null>(readPending);
  const [sourceId, setSourceId] = useState("");
  const [pipelineId, setPipelineId] = useState("");
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const sources = data?.items ?? [];
  const currentScope = () => scopeIdentity() === scope;

  async function reconcile(item: Pending) {
    if (!currentScope() || !item.key) return;
    setBusy(true);
    try {
      const receipt = await apiGetAuthoritative<Registration>(
        `/v1/pipeline-registrations/${encodeURIComponent(item.id)}/receipt?key=${encodeURIComponent(item.key)}`);
      if (!currentScope() || !matches(receipt, item)) {
        setMessage("原请求回执与待登记内容不一致；保持冻结，请核查。");
        return;
      }
      localStorage.removeItem(storageKey());
      setPending(null);
      setOpen(false);
      setMessage(`管道 ${item.id} 已正式登记；仍需配置画布和审批，未执行源读取。`);
      onRegistered();
      reload();
    } catch {
      if (currentScope()) setMessage("原请求结果尚未核清；保持冻结，不得重新提交。");
    } finally { if (currentScope()) setBusy(false); }
  }

  async function submit() {
    if (!currentScope() || pending || busy) return;
    const id = pipelineId.trim();
    const label = name.trim();
    const source = sources.find(item => item.id === sourceId);
    if (!/^[A-Za-z][A-Za-z0-9._-]{0,119}$/.test(id) || !label || !source?.configurationRevision) {
      setMessage("请选择当前来源，并填写规范的管道 ID 和名称。");
      return;
    }
    setBusy(true);
    try {
      const current = await apiGetAuthoritative<{ items: Source[] }>("/v1/sources");
      if (!currentScope() || !current.items.some(item => item.id === source.id &&
          item.configurationRevision === source.configurationRevision)) {
        setMessage("来源配置已变化；请刷新后重新选择。");
        return;
      }
      const item: Pending = { id, sourceId: source.id,
        sourceConfigurationRevision: source.configurationRevision,
        datasetRid: `ri.dataset.${id}`, name: label, key: crypto.randomUUID() };
      localStorage.setItem(storageKey(), JSON.stringify(item));
      setPending(item);
      try {
        await apiPostUnqueued<Registration>("/v1/pipeline-registrations", {
          pipelineId: item.id, sourceId: item.sourceId,
          sourceConfigurationRevision: item.sourceConfigurationRevision, name: item.name,
        }, { "Idempotency-Key": item.key });
      } catch {
        if (currentScope()) setMessage("提交结果未知；只读核对原回执，不重发。");
        return;
      }
      await reconcile(item);
    } catch {
      if (currentScope()) setMessage("来源读取或本地待对账标记失败；未能安全提交。");
    } finally { if (currentScope()) setBusy(false); }
  }

  return <section aria-label="正式管道登记" style={{ border: "1px solid var(--aos-border)", padding: 12, margin: "8px 0" }}>
    <h3>正式管道登记</h3>
    <p>先登记已授权的数据源，再创建管道配置。登记不会连接来源、执行同步或批准 SourceSelection。</p>
    {err && <p role="alert">来源列表未核清：{err}</p>}
    {loading && <p role="status">正在读取当前来源…</p>}
    {!loading && sources.length === 0 && <p>当前没有可用的正式来源。<Link to="/data">前往数据源管理</Link></p>}
    {pending && <div role="alert"><p>管道 {pending.id} 的原提交结果待对账；禁止再次提交。</p>
      <button type="button" disabled={busy || !pending.key} onClick={() => void reconcile(pending)}>只读核对原回执</button>
    </div>}
    {message && <p role="status">{message}</p>}
    {!pending && sources.length > 0 && <>
      <button type="button" disabled={busy || loading || Boolean(err)} onClick={() => setOpen(value => !value)}>新建管道</button>
      {open && <div role="group" aria-label="新建管道表单">
        <label>已授权来源<select aria-label="已授权来源" value={sourceId} onChange={event => setSourceId(event.target.value)}>
          <option value="">请选择当前来源</option>
          {sources.filter(source => source.configurationRevision).map(source =>
            <option key={source.id} value={source.id}>{source.displayName || source.name || source.id}</option>)}
        </select></label>
        <label>管道 ID<input aria-label="管道 ID" value={pipelineId} onChange={event => setPipelineId(event.target.value)} /></label>
        <label>名称<input aria-label="管道名称" value={name} onChange={event => setName(event.target.value)} /></label>
        <button type="button" disabled={busy} onClick={() => void submit()}>登记管道配置</button>
      </div>}
    </>}
  </section>;
}
