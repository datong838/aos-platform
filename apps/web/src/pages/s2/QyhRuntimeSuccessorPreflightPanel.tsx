import { useEffect, useState } from "react";
import { aipModelRuntime, type ExactRuntimeRef } from "../../api/aipModelRuntime";
import { inspectQyhSuccessorPreflight, QYH_RUNTIME_SUCCESSOR, type QyhSuccessorPreflight } from "../../api/aipModelRuntime/qyhSuccessorPreflight";

export function QyhRuntimeSuccessorPreflightPanel({ pairedPolicyRef, pairedPriceRef }: { pairedPolicyRef: ExactRuntimeRef; pairedPriceRef: ExactRuntimeRef }) {
  const [result, setResult] = useState<QyhSuccessorPreflight | null>(null);
  const [failed, setFailed] = useState(false);
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
  }, [pairedPolicyRef.assetId, pairedPolicyRef.revision, pairedPolicyRef.contentHash, pairedPriceRef.assetId, pairedPriceRef.revision, pairedPriceRef.contentHash]);
  return <section className="card" aria-label="栖月汇模型接续预检" style={{ padding: 18, marginTop: 16 }}>
    <h2>模型、策略与路由接续预检</h2>
    {!result && !failed ? <p role="status">正在读取栖月汇当前三个权威头…</p> : null}
    {failed ? <p role="alert" className="notice bad">接续预检未确认：当前权威读取失败；不会使用旧证据或提交草稿。</p> : null}
    {result ? <>
      <p className={`notice ${result.ready ? "good" : "bad"}`}><strong>{result.ready ? "三个追加式草稿可准备" : "接续预检存在阻断"}</strong> · 尚未发布、未评测、不可调用。</p>
      <ol>{result.steps.map((step) => <li key={step.id}><strong>{step.label}：{step.status === "ready" ? "可准备" : "已阻断"}</strong><br /><small>{step.reason}</small></li>)}</ol>
      <p>paired 策略 <code>{pairedPolicyRef.assetId}@{pairedPolicyRef.revision}</code> · 价格 <code>{pairedPriceRef.assetId}@{pairedPriceRef.revision}</code></p>
    </> : null}
  </section>;
}
