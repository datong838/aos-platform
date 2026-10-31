import { useEffect, useState } from "react";
import { aipModelRuntime, type ExactRuntimeRef } from "../../api/aipModelRuntime";
import { inspectQyhSuccessorPreflight, QYH_RUNTIME_SUCCESSOR, type QyhSuccessorPreflight } from "../../api/aipModelRuntime/qyhSuccessorPreflight";
import { prepareQyhSuccessorDrafts } from "../../api/aipModelRuntime/successorDrafts";

export function QyhRuntimeSuccessorPreflightPanel({ pairedPolicyRef, pairedPriceRef }: { pairedPolicyRef: ExactRuntimeRef; pairedPriceRef: ExactRuntimeRef }) {
  const [result, setResult] = useState<QyhSuccessorPreflight | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  const [preparing, setPreparing] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let current = true;
    setResult(null); setFailed(false);
    Promise.all([
      aipModelRuntime.model(QYH_RUNTIME_SUCCESSOR.modelId),
      aipModelRuntime.policy(QYH_RUNTIME_SUCCESSOR.policyId),
      aipModelRuntime.route(QYH_RUNTIME_SUCCESSOR.routeId),
    ]).then(([model, policy, route]) => {
      if (current) setResult(inspectQyhSuccessorPreflight({ model, policy, route, pairedPolicyRef, pairedPriceRef }));
    }).catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [pairedPolicyRef.assetId, pairedPolicyRef.revision, pairedPolicyRef.contentHash, pairedPriceRef.assetId, pairedPriceRef.revision, pairedPriceRef.contentHash, reload]);
  async function prepare() {
    if (!result?.ready || preparing || attempted) return;
    setAttempted(true); setPreparing(true); setMessage("");
    try {
      const prepared = await prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef }, aipModelRuntime);
      setMessage(`三个草稿已精确回读：模型 r${prepared.model.revision}、策略 r${prepared.policy.revision}、路由 r${prepared.route.revision}；仍未评测、未激活、未调用模型。`);
    } catch {
      setMessage("草稿结果未确认或当前头已漂移；已停止后续写入，只能重新读取当前头，不会自动重发。");
    } finally { setPreparing(false); }
  }
  return <section className="card" aria-label="栖月汇模型接续预检" style={{ padding: 18, marginTop: 16 }}>
    <h2>模型、策略与路由接续预检</h2>
    {!result && !failed ? <p role="status">正在读取栖月汇当前三个权威头…</p> : null}
    {failed ? <p role="alert" className="notice bad">接续预检未确认：当前权威读取失败；不会使用旧证据或提交草稿。</p> : null}
    {result ? <>
      <p className={`notice ${result.ready ? "good" : "bad"}`}><strong>{result.ready ? "三个追加式草稿可准备" : "接续预检存在阻断"}</strong> · 尚未发布、未评测、不可调用。</p>
      <ol>{result.steps.map((step) => <li key={step.id}><strong>{step.label}：{step.status === "ready" ? "可准备" : "已阻断"}</strong><br /><small>{step.reason}</small></li>)}</ol>
      <p>paired 策略 <code>{pairedPolicyRef.assetId}@{pairedPolicyRef.revision}</code> · 价格 <code>{pairedPriceRef.assetId}@{pairedPriceRef.revision}</code></p>
      {result.ready ? <button type="button" className="btn btn-primary" disabled={preparing || attempted} onClick={() => void prepare()}>{preparing ? "正在逐步回读…" : "确认准备三个草稿（不激活）"}</button> : null}
      {message ? <p role="status">{message}</p> : null}
      {attempted && !preparing && !message.includes("三个草稿已精确回读") ? <button type="button" className="btn" onClick={() => setReload((value) => value + 1)}>重新读取当前头（不重发）</button> : null}
    </> : null}
  </section>;
}
