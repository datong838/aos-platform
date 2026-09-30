import { useEffect, useRef, useState } from 'react';
import { apiGetAuthoritative, apiPostUnqueued } from '../../api/client';
import { getAuthRevision, getTenant } from '../../api/tenant';

type ReferenceInput = { policyId: string; revision: string; expectedHeadVersion: string };
type Result = { status: 'not_attempted' | 'unresolved' } | { status: 'observed'; proposalId: string };
const PATH = '/v1/aip/runtime-guard-policies/networks/proposal-intent';
const identity = () => { const t = getTenant(); return JSON.stringify([t.orgId, t.projectId, t.subject, getAuthRevision()]); };

export function restoreNetworkReference(search: string): Partial<ReferenceInput> {
  const p = new URLSearchParams(search);
  const policyId = p.get('networkPolicy') ?? '';
  const revision = p.get('networkRevision') ?? '';
  const expectedHeadVersion = p.get('networkHead') ?? '';
  try { reference({ policyId, revision, expectedHeadVersion }); return { policyId, revision, expectedHeadVersion }; }
  catch { return {}; }
}

function reference(input: ReferenceInput) {
  const policyId = input.policyId.trim();
  if (!policyId || policyId.length > 200 || !/^[1-9]\d*$/.test(input.revision)
      || !/^\d+$/.test(input.expectedHeadVersion) || !Number.isSafeInteger(Number(input.revision))
      || !Number.isSafeInteger(Number(input.expectedHeadVersion))) throw new Error('请填写精确网络策略 ID、候选修订和预期 head 版本');
  return { policyId, revision: Number(input.revision), headVersion: Number(input.expectedHeadVersion) };
}

function parse(value: unknown, query: boolean): Result {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('创建查询响应不完整');
  const r = value as Record<string, unknown>;
  if (Object.keys(r).some(k => !['status', 'proposalId'].includes(k))) throw new Error('创建查询响应字段未知');
  if (r.status === 'observed' && typeof r.proposalId === 'string' && r.proposalId.trim() === r.proposalId && r.proposalId.length > 0) {
    return { status: 'observed', proposalId: r.proposalId };
  }
  if ((r.status === 'unresolved' || (query && r.status === 'not_attempted')) && r.proposalId == null) return { status: r.status as 'unresolved' | 'not_attempted' };
  throw new Error('尚无有效提案凭证，请查询原请求');
}

export function NetworkProposalCreationPanel({ input, buildCandidate }: {
  input: ReferenceInput; buildCandidate: () => { body: unknown; expectedHeadVersion: number };
}) {
  const [expires, setExpires] = useState('');
  const [result, setResult] = useState<{ value: Result; fingerprint: string; identity: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('先查询原创建请求，再提交精确候选；结果未知时只能继续查询。');
  const busyRef = useRef(false);
  const generation = useRef(0);
  const attempted = useRef<string | null>(null);
  const fingerprint = JSON.stringify([input, expires]);
  const current = useRef(fingerprint); current.current = fingerprint;
  useEffect(() => {
    generation.current += 1; busyRef.current = false; setBusy(false); setResult(null);
  }, [fingerprint]);
  useEffect(() => {
    const invalidate = () => { generation.current += 1; busyRef.current = false; setBusy(false); setResult(null); setMessage('身份已变化，请重新核对当前工作区候选和原请求。'); };
    window.addEventListener('aos-auth-updated', invalidate);
    window.addEventListener('aos-tenant-updated', invalidate);
    return () => { generation.current += 1; window.removeEventListener('aos-auth-updated', invalidate); window.removeEventListener('aos-tenant-updated', invalidate); };
  }, []);
  let candidateReady = false;
  try { buildCandidate(); candidateReady = true; } catch { /* Existing form supplies its validation. */ }
  const expiry = new Date(expires).getTime();
  const validExpiry = Number.isFinite(expiry) && expiry > Date.now() && expiry <= Date.now()+15*60_000;
  const canSubmit = !busy && candidateReady && validExpiry && result?.fingerprint === fingerprint
    && result.identity === identity() && result.value.status === 'not_attempted';

  async function perform(submit: boolean) {
    if (busyRef.current || (submit && !canSubmit)) return;
    let ref: ReturnType<typeof reference>; let body: { candidate: unknown; expiresAt: string } | undefined;
    try {
      ref = reference(input);
      if (submit) {
        const built = buildCandidate();
        const time = new Date(expires).getTime();
        if (built.expectedHeadVersion !== ref.headVersion || !Number.isFinite(time) || time <= Date.now() || time > Date.now()+15*60_000) throw new Error('提案有效期须在未来 15 分钟内');
        body = { candidate: built.body, expiresAt: new Date(time).toISOString() };
      }
    } catch (e) { setMessage((e as Error).message); return; }
    const actor = identity(); const epoch = generation.current; const saved = fingerprint;
    const slot = JSON.stringify([actor, ref]);
    busyRef.current = true; setBusy(true);
    if (submit) { attempted.current = slot; setResult({ value: { status: 'unresolved' }, fingerprint: saved, identity: actor }); }
    setMessage(submit ? '正在提交审批提案…' : '正在查询服务器保存的原创建请求…');
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('networkPolicy', ref.policyId); url.searchParams.set('networkRevision', String(ref.revision)); url.searchParams.set('networkHead', String(ref.headVersion));
      window.history.replaceState(window.history.state, '', url);
      const value = parse(submit ? await apiPostUnqueued(PATH, body, { 'If-Match': String(ref.headVersion) })
        : await apiGetAuthoritative(PATH+'?'+new URLSearchParams({ policyId: ref.policyId, revision: String(ref.revision), headVersion: String(ref.headVersion) })), !submit);
      if (epoch !== generation.current || current.current !== saved || actor !== identity()) return;
      if (value.status === 'not_attempted' && attempted.current === slot) throw new Error('此前已提交但原记录未确认，禁止重发，请核对服务端持久记录');
      setResult({ value, fingerprint: saved, identity: actor });
      setMessage(value.status === 'observed' ? '已查到原提案，不表示批准或生效。' : value.status === 'unresolved' ? '原创建结果尚未确认，禁止重复提交；请继续查询原请求。' : '当前产品请求尚未登记；核对完整候选和提案有效期后可提交。');
    } catch (e) {
      if (epoch !== generation.current || current.current !== saved || actor !== identity()) return;
      setResult(null); setMessage(`请求未确认：${(e as Error).message}。请查询原请求，不能据此重发。`);
    } finally { if (epoch === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  const observed = result?.fingerprint === fingerprint && result.identity === identity() && result.value.status === 'observed' ? result.value : null;
  return <section aria-label="创建网络审批提案" className="mt-4 space-y-3 rounded border p-3">
    <h3 className="font-semibold">提交网络策略审批</h3>
    <p>复用上方精确候选。创建提案不表示批准或生效；生效仍需独立审批和受控服务处理。</p>
    <label className="block">提案有效期（未来 15 分钟内）<input aria-label="网络提案有效期" type="datetime-local" value={expires} disabled={busy} onChange={e => setExpires(e.target.value)} /></label>
    <div className="flex flex-wrap gap-2">
      <button type="button" className="btn" disabled={busy} onClick={() => void perform(false)}>查询原创建请求</button>
      <button type="button" className="btn" disabled={!canSubmit} onClick={() => void perform(true)}>提交审批提案</button>
    </div>
    <p role="status">{message}</p>
    {observed && <a href={'/aip/drafts?proposal='+encodeURIComponent(observed.proposalId)}>查看原提案与审批记录</a>}
  </section>;
}
