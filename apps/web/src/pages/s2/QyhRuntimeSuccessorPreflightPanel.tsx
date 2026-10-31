import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { aipModelRuntime, type ExactRuntimeRef } from "../../api/aipModelRuntime";
import type { QyhSuccessorPreflight } from "../../api/aipModelRuntime/qyhSuccessorPreflight";
import { inspectQyhSuccessorDraftState, prepareQyhSuccessorDrafts, type QyhSuccessorDraftState } from "../../api/aipModelRuntime/successorDrafts";

export function QyhRuntimeSuccessorPreflightPanel({ pairedPolicyRef, pairedPriceRef }: { pairedPolicyRef: ExactRuntimeRef; pairedPriceRef: ExactRuntimeRef }) {
  const [result, setResult] = useState<QyhSuccessorPreflight | null>(null);
  const [draftState, setDraftState] = useState<QyhSuccessorDraftState | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  const [preparing, setPreparing] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let current = true;
    setResult(null); setDraftState(null); setFailed(false);
    inspectQyhSuccessorDraftState({ pairedPolicyRef, pairedPriceRef }, aipModelRuntime).then((state) => {
      if (current) { setDraftState(state); setResult(state.preflight); }
    }).catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [pairedPolicyRef.assetId, pairedPolicyRef.revision, pairedPolicyRef.contentHash, pairedPriceRef.assetId, pairedPriceRef.revision, pairedPriceRef.contentHash, reload]);
  async function prepare() {
    if (!result?.ready || draftState?.status !== "ready_to_prepare" || preparing || attempted) return;
    setAttempted(true); setPreparing(true); setMessage("");
    try {
      const prepared = await prepareQyhSuccessorDrafts({ pairedPolicyRef, pairedPriceRef }, aipModelRuntime);
      setDraftState({ status: "prepared", observed: { model: true, policy: true, route: true }, model: prepared.model, policy: prepared.policy, route: prepared.route, preflight: result });
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
      <p className={`notice ${draftState?.status === "partial_observed" || !result.ready ? "bad" : "good"}`}><strong>{draftState?.status === "prepared" ? "三个追加式草稿已准备" : draftState?.status === "partial_observed" ? "检测到部分草稿，已冻结自动续接" : result.ready ? "三个追加式草稿可准备" : "接续预检存在阻断"}</strong> · {draftState?.status === "prepared" ? "待办理 Eval，仍未评测、未激活、不可调用。" : "尚未评测、不可调用。"}</p>
      <ol>{result.steps.map((step) => { const observed = draftState?.observed[step.id] ?? false; return <li key={step.id}><strong>{step.label}：{observed ? "已精确观察" : step.status === "ready" ? "可准备" : "已阻断"}</strong><br /><small>{observed ? `当前草稿已按 paired 引用回读；${step.id === "route" ? "仍待 Eval" : "不代表激活"}` : step.reason}</small></li>; })}</ol>
      <p>paired 策略 <code>{pairedPolicyRef.assetId}@{pairedPolicyRef.revision}</code> · 价格 <code>{pairedPriceRef.assetId}@{pairedPriceRef.revision}</code></p>
      {result.ready && draftState?.status === "ready_to_prepare" ? <button type="button" className="btn btn-primary" disabled={preparing || attempted} onClick={() => void prepare()}>{preparing ? "正在逐步回读…" : "确认准备三个草稿（不激活）"}</button> : null}
      {draftState?.status === "partial_observed" ? <p role="alert">只读观察到部分精确草稿；为避免 unknown 重发，不自动补写。请先核对原命令结果和当前权威头。</p> : null}
      {draftState?.status === "prepared" ? <p><Link className="btn" to="/aip/evals">进入评测门控（不会自动运行）</Link></p> : null}
      {message ? <p role="status">{message}</p> : null}
      {attempted && !preparing && !message.includes("三个草稿已精确回读") ? <button type="button" className="btn" onClick={() => setReload((value) => value + 1)}>重新读取当前头（不重发）</button> : null}
    </> : null}
  </section>;
}
