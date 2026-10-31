import { useEffect, useState } from "react";
import { assetControlClient } from "../../../api/assetControl/client";
import { createIdempotentCommand, idempotencyKeyFor } from "../../../api/assetControl/idempotency";
import { serializeSuccessorRegistration, type SuccessorPreparation, type SuccessorRegistrationCommand } from "../../../api/assetControl/successorRegistration";
import { getTenant } from "../../../api/tenant";
import { useBudgetRequestGuard } from "../useBudgetRequestGuard";

type Owner = { orgId: string; projectId: string; subject: string | null; installationId: string };
function ownerFor(installationId: string): Owner {
  const t = getTenant(); return { orgId: t.orgId, projectId: t.projectId, subject: t.subject ?? null, installationId };
}
function readOriginal(slot: string, owner: Owner) {
  try {
    const raw = sessionStorage.getItem(slot);
    if (raw === null) return { pending: null, blocked: false };
    const value = JSON.parse(raw);
    if (!value || Object.keys(value).length !== 3 || value.schemaVersion !== "aos.successor-registration.intent/v1" ||
        !value.owner || Object.keys(value.owner).length !== 4 ||
        Object.entries(owner).some(([k, v]) => value.owner[k] !== v)) throw new Error();
    const command = serializeSuccessorRegistration(value.command);
    if (command.registration.installationRef.installationId !== owner.installationId) throw new Error();
    return { pending: command, blocked: false };
  } catch { return { pending: null, blocked: true }; }
}

export function SuccessorRegistrationPanel({ installationId, allowedPrepare, disabled, onRegistered }: {
  installationId: string; allowedPrepare: boolean; disabled: boolean; onRegistered: () => void;
}) {
  const [owner] = useState(() => ownerFor(installationId));
  const slot = `aos-successor-intent:${JSON.stringify(owner)}`;
  const [original] = useState(() => readOriginal(slot, owner));
  const [pending, setPending] = useState<SuccessorRegistrationCommand | null>(original.pending);
  const [material, setMaterial] = useState<SuccessorPreparation | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(original.blocked ? "原操作记录无法核对，暂不能提交新登记。" : null);
  const sameOwner = () => JSON.stringify(ownerFor(installationId)) === JSON.stringify(owner);
  const guard = useBudgetRequestGuard(() => { setMaterial(null); setMessage(null); setError("身份已变化，请重新核对当前业务。"); });
  useEffect(() => { if (pending) guard.markAttempted(pending.registration.idempotencyKey); }, []);
  const unavailable = disabled || guard.busy || original.blocked || !owner.subject;

  async function prepare() {
    if (unavailable || !sameOwner() || !allowedPrepare || pending) return;
    const current = guard.begin(); if (!current) return;
    setMaterial(null); setMessage(null); setError(null);
    try {
      const key = idempotencyKeyFor(createIdempotentCommand());
      const result = await assetControlClient.getSuccessorPreparation(installationId, key);
      if (current()) setMaterial(result);
    } catch { if (current()) setError("暂时无法核对接续条件，请稍后重新核对。"); }
    finally { guard.finish(current); }
  }
  function observed() {
    try { sessionStorage.removeItem(slot); setPending(null); }
    catch { setError("登记已确认，原操作记录仍保留，可继续查看结果。"); }
    setMaterial(null); setMessage("接续登记已确认，尚未启动业务。"); onRegistered();
  }
  async function submit() {
    if (unavailable || !sameOwner() || !allowedPrepare || pending || !material?.ready) return;
    const command = serializeSuccessorRegistration(material.options[0].command);
    if (guard.attempted(command.registration.idempotencyKey)) return;
    const current = guard.begin(); if (!current) return;
    setError(null);
    try {
      try {
        sessionStorage.setItem(slot, JSON.stringify({ schemaVersion: "aos.successor-registration.intent/v1", owner, command }));
      } catch { if (current()) setError("无法保存本次操作记录，尚未提交登记。"); return; }
      guard.markAttempted(command.registration.idempotencyKey);
      setPending(command); setMaterial(null);
      await assetControlClient.createSuccessorRegistration(command);
      if (current()) observed();
    } catch { if (current()) setError("登记结果尚未确认，请查看原登记结果；不会重复提交。"); }
    finally { guard.finish(current); }
  }
  async function read() {
    if (unavailable || !sameOwner() || !pending) return;
    const current = guard.begin(); if (!current) return;
    setError(null);
    try { await assetControlClient.readSuccessorRegistration(pending); if (current()) observed(); }
    catch { if (current()) setError("原登记结果仍未确认，记录已保留；系统不会重复提交。"); }
    finally { guard.finish(current); }
  }
  if (!sameOwner() || (!allowedPrepare && !pending && !original.blocked)) return null;
  return <section aria-label="接续经营业务" style={{ marginTop: 12 }}>
    <h4>接续经营业务</h4>
    <p>先核对原安装退出和当前安装准备情况。接续登记保留原业务记录，不会自动启动业务。</p>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    {pending ? <button disabled={unavailable} onClick={() => void read()}>查看原登记结果</button> :
      <button disabled={unavailable || !allowedPrepare} onClick={() => void prepare()}>核对接续条件</button>}
    {material && !pending && <div>
      {material.reasons.map(reason => <p key={reason}>{reason}</p>)}
      {material.ready && <div role="group" aria-label="确认经营接续">
        <p>{material.options[0].label}。本次仅登记接续材料，实际切换仍需核对和批准。</p>
        <button disabled={unavailable || !allowedPrepare} onClick={() => void submit()}>确认接续登记</button>
        <button disabled={guard.busy} onClick={() => setMaterial(null)}>取消</button>
      </div>}
    </div>}
  </section>;
}
