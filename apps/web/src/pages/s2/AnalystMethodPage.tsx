import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { getTenant } from "../../api/tenant";
import { PageChrome } from "../../components/PageChrome";

type ExactRef = { resourceType: "MethodRevision"; resourceId: string; revision: number; contentHash: string };
type Method = {
  tenant: { orgId: string; projectId: string }; methodId: string; revision: number;
  contentHash: string; name: string; description: string;
  minSourceItems: number; maxSourceAgeSeconds: number; limitations: string[];
};
type Pending = { idempotencyKey: string; body: Record<string, unknown> };

const base = "/v1/ecommerce/analyst/methods";
const scopeKey = (methodId: string) => {
  const tenant = getTenant();
  return `aos:analyst-method:pending:${tenant.orgId}:${tenant.projectId}:${methodId}`;
};
const exactPath = (ref: ExactRef) => `${base}/${encodeURIComponent(ref.resourceId)}/revisions/${ref.revision}/${ref.contentHash}`;
const sameTenant = (method: Method) => {
  const tenant = getTenant();
  return method.tenant.orgId === tenant.orgId && method.tenant.projectId === tenant.projectId;
};

export function AnalystMethodPage() {
  const [methodId, setMethodId] = useState("sales-weapon-descriptive-snapshot");
  const [name, setName] = useState("销售武器包来源事实画像");
  const [description, setDescription] = useState("仅归纳获准来源的商品与服务事实，保留截止面、出处和未知项。");
  const [minSourceItems, setMinSourceItems] = useState(1);
  const [maxSourceAgeSeconds, setMaxSourceAgeSeconds] = useState(86400);
  const [limitations, setLimitations] = useState("只描述观察，不证明因果、可售库存、利润或功效。\n缺失来源或过期来源必须明确标记未知。");
  const [current, setCurrent] = useState<Method | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);

  useEffect(() => {
    setCurrent(null); setLoaded(false);
    const raw = localStorage.getItem(scopeKey(methodId));
    if (!raw) { setPending(null); return; }
    try { setPending(JSON.parse(raw) as Pending); }
    catch { setPending({ idempotencyKey: "不可解析的待对账请求", body: {} }); }
  }, [methodId]);

  const loadCurrent = async () => {
    setBusy(true); setNote("");
    try {
      const method = await apiGetAuthoritative<Method>(`${base}/${encodeURIComponent(methodId)}/current`);
      if (!sameTenant(method) || method.methodId !== methodId) throw new Error("当前版本与租户或方法 ID 不一致");
      setCurrent(method); setName(method.name); setDescription(method.description);
      setLoaded(true);
      setMinSourceItems(method.minSourceItems); setMaxSourceAgeSeconds(method.maxSourceAgeSeconds);
      setLimitations(method.limitations.join("\n"));
      setNote(`已回读当前正式版本 r${method.revision}。`);
    } catch (error) {
      if ((error as { status?: number }).status === 404) { setCurrent(null); setLoaded(true); setNote("该方法尚无正式版本，可创建 r1。") }
      else { setLoaded(false); setNote(`当前版本未核清：${String((error as Error).message || error)}`); }
    } finally { setBusy(false); }
  };

  const reconcile = async () => {
    if (!pending || pending.idempotencyKey === "不可解析的待对账请求") return;
    setBusy(true);
    try {
      const ref = await apiGetAuthoritative<ExactRef | null>(`${base}/receipts/${encodeURIComponent(pending.idempotencyKey)}`);
      if (!ref) { setNote("尚未查到正式回执，结果仍未知；保持冻结，不重发。"); return; }
      if (ref.resourceType !== "MethodRevision" || ref.resourceId !== methodId) throw new Error("回执指向其他方法");
      const method = await apiGetAuthoritative<Method>(exactPath(ref));
      if (!sameTenant(method) || method.methodId !== methodId || method.revision !== ref.revision || method.contentHash !== ref.contentHash) throw new Error("精确读回不一致");
      localStorage.removeItem(scopeKey(methodId)); setPending(null); setCurrent(method);
      setNote(`已通过正式回执及精确版本 r${ref.revision} 对账。`);
    } catch (error) { setNote(`对账未完成，保持冻结：${String((error as Error).message || error)}`); }
    finally { setBusy(false); }
  };

  const publish = async () => {
    if (busy || pending || !loaded || !methodId.trim()) return;
    const limitationItems = limitations.split("\n").map((value) => value.trim()).filter(Boolean);
    if (!name.trim() || !description.trim() || !limitationItems.length || minSourceItems < 1 || maxSourceAgeSeconds < 1) {
      setNote("请补全方法名称、描述、来源要求与限制说明。"); return;
    }
    const idempotencyKey = `analyst-method-${crypto.randomUUID()}`;
    const body = {
      methodId, name: name.trim(), description: description.trim(),
      algorithm: "descriptive_snapshot_v1", insightKind: "observation",
      minSourceItems, maxSourceAgeSeconds, limitations: limitationItems,
      expectedVersion: current?.revision ?? 0,
      priorRef: current ? { resourceType: "MethodRevision", resourceId: methodId,
        revision: current.revision, contentHash: current.contentHash } : null,
      createdAt: new Date().toISOString(),
    };
    const frozen = { idempotencyKey, body };
    localStorage.setItem(scopeKey(methodId), JSON.stringify(frozen)); setPending(frozen); setBusy(true);
    try {
      const response = await apiPostUnqueued<{ exactRef: ExactRef; method: Method }>(base, body, { "Idempotency-Key": idempotencyKey });
      const ref = response.exactRef;
      if (ref.resourceType !== "MethodRevision" || ref.resourceId !== methodId || !sameTenant(response.method)) throw new Error("发布响应与租户不一致");
      const verified = await apiGetAuthoritative<Method>(exactPath(ref));
      if (!sameTenant(verified) || verified.methodId !== methodId || verified.revision !== ref.revision || verified.contentHash !== ref.contentHash) throw new Error("精确读回不一致");
      localStorage.removeItem(scopeKey(methodId)); setPending(null); setCurrent(verified);
      setNote(`正式方法 r${ref.revision} 已发布并精确读回。它只定义描述性观察，不代表业务分析已运行。`);
    } catch (error) { setNote(`写入结果未核清，禁止重发；请按回执只读对账：${String((error as Error).message || error)}`); }
    finally { setBusy(false); }
  };

  return <PageChrome title="经营参谋 · 方法配置" lede="正式描述性观察方法；不读取商城源库，也不触发分析或外部动作。">
    <p><Link to="/aip/analyst">返回 AIP 分析师</Link></p>
    <section aria-label="方法版本配置" className="card">
      <label>方法 ID <input value={methodId} onChange={(event) => setMethodId(event.target.value.trim())} disabled={busy} /></label>
      <button type="button" onClick={loadCurrent} disabled={busy || !methodId}>读取当前正式版本</button>
      <p>当前版本：{current ? `r${current.revision} · ${current.contentHash}` : "未回读或尚无版本"}</p>
      <label>名称 <input value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>方法描述 <textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
      <label>最少来源项 <input type="number" min="1" max="100" value={minSourceItems} onChange={(event) => setMinSourceItems(Number(event.target.value))} /></label>
      <label>最长来源年龄（秒） <input type="number" min="1" value={maxSourceAgeSeconds} onChange={(event) => setMaxSourceAgeSeconds(Number(event.target.value))} /></label>
      <label>限制（每行一项） <textarea value={limitations} onChange={(event) => setLimitations(event.target.value)} /></label>
      <p>算法：descriptive_snapshot_v1；结论类型：observation。此处不能批准因果结论。</p>
      <button type="button" onClick={publish} disabled={busy || !!pending || !loaded}>提交正式方法版本</button>
    </section>
    {pending && <section role="alert"><p>存在未核清的写入请求，提交已冻结。不要再次提交或换键重发。</p><button type="button" onClick={reconcile} disabled={busy}>按回执只读对账</button></section>}
    {note && <p role="status">{note}</p>}
  </PageChrome>;
}
