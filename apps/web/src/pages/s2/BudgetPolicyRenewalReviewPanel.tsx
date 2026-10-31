import { useEffect, useRef, useState } from 'react';
import { getTenant } from '../../api/tenant';
import { budgetIdentity, useBudgetRequestGuard } from './useBudgetRequestGuard';
import {
  readRenewalSource, readRenewalStatus, postRenewalOperation, postRenewalDecisionAndPublish, continueRenewalChain,
  restoreRenewalReference, saveRenewalReference, clearRenewalReference, readRenewalRecovery,
  assertRenewalPreparedSource, assertRenewalDecisionProposal, assertRenewalPublicationProposal,
  renewalProposalCommand, renewalTargetWindow,
  type RenewalSource, type RenewalStatus, type RenewalPreparedReceipt, type RenewalDecisionReceipt,
  type RenewalPublicationReceipt, type RenewalOperationResult, type RenewalChain, type RenewalReference,
  type RenewalDecisionCommand, type RenewalConsumeCommand, type RenewalRevocationCommand,
} from '../../api/aipBudgetPolicyRenewal';

const human = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';
function money(value: number) { const cents = BigInt(value); return `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`; }
function key(operation: string) { return `renewal-${operation}-${crypto.randomUUID()}`; }
const scope = { schemaVersion: 1 as const, orgId: 'org-org' as const, projectId: 'dev-project' as const };

export function BudgetPolicyRenewalReviewPanel() {
  const initial = useRef(restoreRenewalReference(typeof window === 'undefined' ? '' : window.location.search));
  const [ref, setRef] = useState<RenewalReference | null>(initial.current.state === 'ready' ? initial.current.ref : null);
  const invalid = initial.current.state === 'invalid';
  const [id, setId] = useState(''), [from, setFrom] = useState(''), [until, setUntil] = useState('');
  const [source, setSource] = useState<RenewalSource | null>(null), [status, setStatus] = useState<RenewalStatus | null>(null);
  const [prepared, setPrepared] = useState<RenewalPreparedReceipt | null>(null);
  const [decision, setDecision] = useState<RenewalDecisionReceipt | null>(null);
  const [publication, setPublication] = useState<RenewalPublicationReceipt | null>(null);
  const [chain, setChain] = useState<RenewalChain | null>(null);
  const [result, setResult] = useState<RenewalOperationResult | RenewalChain | null>(null);
  const [choice, setChoice] = useState(''), [publishChoice, setPublishChoice] = useState('');
  const [reason, setReason] = useState(''), [continuation, setContinuation] = useState('');
  const [message, setMessage] = useState('先读取实际来源，再输入明确的带时区续期窗口。批准和发布均需分别确认。');
  const actor = useRef('');
  function clearChoices() { setChoice(''); setPublishChoice(''); setReason(''); setContinuation(''); }
  function clearVisible() {
    setSource(null); setStatus(null); setPrepared(null); setDecision(null); setPublication(null); setChain(null); setResult(null);
    actor.current = ''; clearChoices();
  }
  const guard = useBudgetRequestGuard(() => {
    clearVisible(); setId(''); setFrom(''); setUntil('');
    setMessage('身份或工作区已变化；原请求保留，只能重新读取核对，不能自动重发。');
  });
  async function run(task: (current: () => boolean) => Promise<void>) {
    const current = guard.begin(); if (!current) return;
    try { await task(current); }
    catch (error) { if (current()) setMessage(`尚未确认：${error instanceof Error ? error.message : '请求失败'}。原请求已保留，请只读查询，勿重复提交。`); }
    finally { guard.finish(current); }
  }
  function accept(value: RenewalOperationResult | RenewalChain, p: RenewalPreparedReceipt | null = prepared) {
    // Validate every linkage before publishing any part of a response to UI state.
    if ('proposalId' in value) {
      const d = value.decision?.receipt, published = value.publication?.receipt;
      if (p && d && 'decisionPayload' in d) assertRenewalDecisionProposal(d, p);
      if (p && published && 'policy' in published) assertRenewalPublicationProposal(published, p);
    } else if (value.receipt) {
      const r = value.receipt;
      if (source && 'proposal' in r) assertRenewalPreparedSource(r, source);
      if (p && 'decisionPayload' in r) assertRenewalDecisionProposal(r, p);
      if (p && 'policy' in r) assertRenewalPublicationProposal(r, p);
    }
    setResult(value); clearChoices();
    if ('proposalId' in value) {
      setChain(value);
      const d = value.decision?.receipt, published = value.publication?.receipt;
      if (d && 'decisionPayload' in d) { if (p) assertRenewalDecisionProposal(d, p); setDecision(d); }
      if (published && 'policy' in published) { if (p) assertRenewalPublicationProposal(published, p); setPublication(published); }
      setMessage(value.state === 'published' ? '已观察到续期策略发布回执；不代表模型或业务已经运行。' :
        value.state.endsWith('not-attempted') ? '该阶段已确认尚未尝试；核对完整内容后，可明确选择继续。' : '组合请求结果尚未确认，只能查询原请求，不能重复批准或发布。');
    } else {
      const receipt = value.receipt;
      if (receipt && 'proposal' in receipt) { setPrepared(receipt); actor.current = budgetIdentity(); }
      if (receipt && 'decisionPayload' in receipt) { if (p) assertRenewalDecisionProposal(receipt, p); setDecision(receipt); }
      if (receipt && 'policy' in receipt) { if (p) assertRenewalPublicationProposal(receipt, p); setPublication(receipt); }
      setMessage(value.state === 'prepared' || (receipt && 'proposal' in receipt) ? '机器提案已准备，请逐项审阅完整来源、目标、窗口和差异，再明确选择。' :
        receipt && 'policy' in receipt ? '已观察到续期策略发布回执；不代表模型或业务已经运行。' :
        receipt && 'decisionPayload' in receipt ? receipt.decisionPayload.decision === 'revoked'
          ? '已记录批准撤销；这不会回滚已发布策略或已发生支出。'
          : `已记录${receipt.decisionPayload.decision === 'approved' ? '批准' : '拒绝'}意见；读取历史意见不会自动发布或运行模型。`
          : '原请求结果尚未确认，只能查询，不能换键重发。');
    }
  }
  async function query() {
    if (!ref) return;
    const original = ref;
    await run(async current => {
      const recovered = await readRenewalRecovery(original); if (!current()) return;
      setPrepared(recovered.prepared); actor.current = budgetIdentity();
      accept(recovered.result, recovered.prepared);
      if (recovered.prepared) {
        const p = recovered.prepared.proposal;
        setId(p.sourcePolicy.policyId); setFrom(p.targetActive.effectiveFrom); setUntil(p.targetActive.effectiveUntil);
        const s = await readRenewalSource(p.sourcePolicy.policyId); if (!current()) return;
        setSource(s);
        const configured = await readRenewalStatus(); if (!current()) return; setStatus(configured);
      }
    });
  }
  useEffect(() => {
    if (initial.current.state === 'ready') {
      guard.markAttempted(initial.current.ref); void query();
    }
  }, []);
  async function load() {
    if (guard.busyRef.current) return;
    setSource(null); setStatus(null); clearChoices();
    await run(async current => {
      const s = await readRenewalSource(id.trim()); if (!current()) return; setSource(s); actor.current = budgetIdentity();
      const configured = await readRenewalStatus(); if (!current()) return; setStatus(configured);
      if (prepared) assertRenewalPreparedSource(prepared, s);
      setMessage(configured.state === 'closed' ? '续期入口当前关闭。可查看来源，不能提交。' :
        s.state === 'blocked' ? '来源存在阻塞，请核对下方实际原因。' : '来源已读取；服务配置可用仍不代表预算获批或运行准入。');
    });
  }
  function aligned() {
    if (!prepared || !source) return false;
    try { assertRenewalPreparedSource(prepared, source); return true; } catch { return false; }
  }
  const identityMatches = () => actor.current === budgetIdentity() && getTenant().subject === human;
  const available = () => !invalid && identityMatches() && status?.writerEnabled === true;
  const canPrepare = () => {
    if (!available() || ref || !source) return false;
    try { renewalProposalCommand(source, 'form-validation-only', from, until); return true; } catch { return false; }
  };
  const canDecide = () => available() && aligned() && !!prepared && !decision && ref?.kind === 'operation' && ref.operation === 'propose' &&
    ['approved', 'rejected', 'approve-and-publish'].includes(choice) && !guard.attempted({ proposal: prepared.proposalId, phase: 'decide' });
  const approved = decision?.decisionPayload.decision === 'revoked' ? null :
    decision?.status === 'observed' && decision.decisionPayload.decision === 'approved' ? decision : publication;
  const known = result && !['unknown', 'unresolved', 'conflict', 'blocked'].includes(result.state);
  const canPublish = () => available() && aligned() && known && approved && !publication && ref?.kind === 'operation' && ref.operation === 'decide' &&
    publishChoice === 'publish' && !guard.attempted({ proposal: prepared?.proposalId, phase: 'consume' });
  const canRevoke = () => available() && prepared && approved && known && reason !== '' &&
    ['approval_withdrawn', 'scope_changed', 'dependency_changed'].includes(reason) &&
    !guard.attempted({ proposal: prepared.proposalId, phase: 'revoke' });
  const canContinue = () => available() && aligned() && chain && ref?.kind === 'chain' && ref.proposalId === chain.proposalId &&
    decision?.decisionPayload.decision !== 'revoked' && continuation === 'continue' &&
    ['decision-not-attempted', 'publication-not-attempted'].includes(chain.state) &&
    !guard.attempted({ proposal: chain.proposalId, phase: chain.state });
  function reserve(next: RenewalReference, phase: unknown) {
    guard.markAttempted(phase); setRef(next); setResult(null); clearChoices();
    saveRenewalReference(next); // A persistence failure prevents the network call below.
  }
  async function prepare() {
    if (guard.busyRef.current || !canPrepare() || !source) return;
    const s = source;
    await run(async current => {
      const originalKey = key('propose');
      const command = renewalProposalCommand(s, originalKey, from, until);
      const next: RenewalReference = { kind: 'operation', operation: 'propose', key: originalKey, proposalKey: originalKey };
      reserve(next, next);
      const value = await postRenewalOperation('propose', command);
      if (current()) accept(value);
    });
  }
  async function decide() {
    if (guard.busyRef.current || !canDecide() || !prepared || !ref) return;
    const p = prepared, proposalKey = ref.proposalKey, selected = choice;
    await run(async current => {
      const decisionKey = key('decide'), c: RenewalDecisionCommand = { ...scope, idempotencyKey: decisionKey,
        proposalId: p.proposalId, proposalHash: p.proposalHash, targetActiveHash: p.targetActiveHash,
        decision: selected === 'rejected' ? 'rejected' : 'approved' };
      const phase = { proposal: p.proposalId, phase: 'decide' };
      if (selected === 'approve-and-publish') {
        const consumeKey = key('consume');
        reserve({ kind: 'chain', proposalId: p.proposalId, decisionKey, consumeKey, proposalKey }, phase);
        const value = await postRenewalDecisionAndPublish(c, consumeKey); if (current()) accept(value, p);
      } else {
        reserve({ kind: 'operation', operation: 'decide', key: decisionKey, proposalKey }, phase);
        const value = await postRenewalOperation('decide', c); if (current()) accept(value, p);
      }
    });
  }
  async function publish() {
    if (guard.busyRef.current || !canPublish() || !prepared || !approved || !ref) return;
    const p = prepared, a = approved, proposalKey = ref.proposalKey;
    await run(async current => {
      const originalKey = key('consume'), c: RenewalConsumeCommand = { ...scope, idempotencyKey: originalKey,
        proposalId: p.proposalId, proposalHash: p.proposalHash, decisionId: a.decisionId, decisionHash: a.decisionHash };
      reserve({ kind: 'operation', operation: 'consume', key: originalKey, proposalKey }, { proposal: p.proposalId, phase: 'consume' });
      const value = await postRenewalOperation('consume', c); if (current()) accept(value, p);
    });
  }
  async function revoke() {
    if (guard.busyRef.current || !canRevoke() || !prepared || !approved || !ref) return;
    const p = prepared, a = approved, proposalKey = ref.proposalKey, selected = reason as RenewalRevocationCommand['reasonCode'];
    await run(async current => {
      const originalKey = key('revoke'), c: RenewalRevocationCommand = { ...scope, idempotencyKey: originalKey,
        proposalId: p.proposalId, proposalHash: p.proposalHash, decisionId: a.decisionId, decisionHash: a.decisionHash, reasonCode: selected };
      reserve({ kind: 'operation', operation: 'revoke', key: originalKey, proposalKey }, { proposal: p.proposalId, phase: 'revoke' });
      const value = await postRenewalOperation('revoke', c); if (current()) accept(value, p);
    });
  }
  async function advance() {
    if (guard.busyRef.current || !canContinue() || !chain || !ref) return;
    const original = chain, locator = ref;
    await run(async current => {
      reserve(locator, { proposal: original.proposalId, phase: original.state });
      const value = await continueRenewalChain(original); if (current()) accept(value);
    });
  }
  function targetExpiredAtRead() {
    if (!prepared || !source) return false;
    try { return renewalTargetWindow(prepared, source) === 'expired'; } catch { return false; }
  }
  const finalKnown = known && prepared && (publication !== null || decision?.decisionPayload.decision === 'rejected' || decision?.decisionPayload.decision === 'revoked');
  const p = prepared?.proposal, b = p?.sourceBudget ?? source?.sourceBudget;
  return <section className="card" aria-label="预算策略续期评审" style={{ padding: 18, marginTop: 16, minWidth: 0, overflowWrap: 'anywhere' }}>
    <h2>预算策略续期评审</h2>
    <p>续期保留原额度、负责人、模型和供应方，只调整明确的新窗口与审批引用。记录批准、发布策略都不代表模型或业务已经运行。</p>
    {invalid && <p role="alert">恢复地址不完整或不安全，已冻结新提交。请保留原请求并核对服务端记录。</p>}
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <label>策略 ID<input aria-label="续期策略 ID" maxLength={200} value={id} disabled={guard.busy} onChange={e => {
        setId(e.target.value); setSource(null); setStatus(null); clearChoices();
      }} /></label>
      <button type="button" className="btn" disabled={guard.busy || !id.trim()} onClick={() => void load()}>读取续期来源</button>
      <button type="button" className="btn" disabled={guard.busy || !ref} onClick={() => void query()}>查询续期原请求</button>
    </div>
    {source && <div aria-label="续期实际来源">
      <p>来源第 {source.sourcePolicy.revision} 版 · 当前头 {source.sourceHeadVersion} · 生命周期 {source.sourcePolicy.lifecycle} · 窗口 {source.sourceWindow}</p>
      <p>原窗口：{source.sourcePolicy.effectiveFrom} 至 {source.sourcePolicy.effectiveUntil}；原批准：{source.sourcePolicy.approvalRef}</p>
      <p>来源哈希：<code>{source.sourcePolicy.contentHash}</code></p>
      {source.blockers.length > 0 && <p role="alert">来源阻塞：{source.blockers.join('；')}</p>}
    </div>}
    {b && <div aria-label="续期额度与约束">
      <p>日上限 ¥{money(b.dailyLimitMinor)} · 月上限 ¥{money(b.monthlyLimitMinor)} · 币种 {b.currency} · 告警 {b.alertThresholdPct}%</p>
      <p>预算 {b.budgetId} · 第 {b.revision} 版 · 负责人 {b.owner} · 超预算审批人 {b.overBudgetApprover}</p>
      <p>预算窗口：{b.effectiveFrom} 至 {b.effectiveUntil}；环境 {b.environment}；未知用量和未知价格保持禁入，超限停止，不放开零价。</p>
      <p>模型：{(p?.sourcePolicy ?? source?.sourcePolicy)?.developmentCostAuthorization?.providerModelId ?? '待核对'}；Provider：{(p?.sourceProvider ?? source?.sourceProvider)?.providerInstanceId ?? '待核对'}</p>
    </div>}
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      <label>开始时间（含时区）<input aria-label="续期开始时间" placeholder="明确输入 ISO 时间及其时区" value={from} disabled={guard.busy || !!prepared} onChange={e => { setFrom(e.target.value); clearChoices(); }} /></label>
      <label>结束时间（含时区）<input aria-label="续期结束时间" placeholder="明确输入 ISO 时间及其时区" value={until} disabled={guard.busy || !!prepared} onChange={e => { setUntil(e.target.value); clearChoices(); }} /></label>
      <button type="button" className="btn" disabled={guard.busy || !canPrepare()} onClick={() => void prepare()}>准备续期提案</button>
    </div>
    {p && prepared && <div aria-label="完整续期待审内容">
      <h3>来源与候选差异</h3>
      {targetExpiredAtRead() && <p role="alert">候选续期窗口已过期（服务端读取时间：{source?.evaluatedAt}）。原记录保留，请只读查询，勿重复提交；任何审批或发布仍由服务端按当前时间和权限核验。</p>}
      <p>来源第 {p.sourcePolicy.revision} 版 → 候选第 {p.targetActive.revision} 版；负责人 {p.targetActive.owner}，金额、预算、模型、Provider 与安全边界保持原值。</p>
      <p>新窗口：{p.targetActive.effectiveFrom} 至 {p.targetActive.effectiveUntil}；新审批引用：{p.approvalSlot}</p>
      <p>租户 {p.tenant.orgId} / {p.tenant.projectId}；独立审核人 {p.checkerSubject}；机器提案者 {p.makerSubject}</p>
      <p>提案 {prepared.proposalId}；提案哈希 <code>{prepared.proposalHash}</code></p>
      <p>目标哈希 <code>{prepared.targetActiveHash}</code>；合同哈希 <code>{p.contractHash}</code></p>
      <details><summary>展开完整来源、预算、Provider、合同与目标内容</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxWidth: '100%' }}>{JSON.stringify(p, null, 2)}</pre></details>
      <label>复核选择<select aria-label="续期复核选择" value={choice} disabled={guard.busy || !available() || !aligned() || !!decision || ref?.kind !== 'operation' || ref.operation !== 'propose'} onChange={e => setChoice(e.target.value)}>
        <option value="">请明确选择</option><option value="approved">只批准此提案</option><option value="rejected">拒绝此提案</option><option value="approve-and-publish">批准并交由独立发布者有界发布</option>
      </select></label>
      <button type="button" className="btn btn-primary" disabled={guard.busy || !canDecide()} onClick={() => void decide()}>{choice === 'approve-and-publish' ? '批准并有界发布' : '提交续期复核'}</button>
    </div>}
    {approved && <div>
      <p>历史批准记录：{approved.decisionId}；当前是否仍可消费由服务端再次核验。</p>
      <label>发布确认<select aria-label="续期发布确认" value={publishChoice} disabled={guard.busy} onChange={e => setPublishChoice(e.target.value)}><option value="">请明确选择</option><option value="publish">发布此精确批准对应的续期</option></select></label>
      <button type="button" className="btn" disabled={guard.busy || !canPublish()} onClick={() => void publish()}>发布已批准续期</button>
      <label>撤销原因<select aria-label="续期撤销原因" value={reason} disabled={guard.busy} onChange={e => setReason(e.target.value)}><option value="">请明确选择</option><option value="approval_withdrawn">撤回批准</option><option value="scope_changed">范围变化</option><option value="dependency_changed">依赖变化</option></select></label>
      <button type="button" className="btn" disabled={guard.busy || !canRevoke()} onClick={() => void revoke()}>撤销续期批准</button>
      <p>撤销只记录批准撤回，不回滚已发布策略或已经发生的支出。</p>
    </div>}
    {chain && <div><p>组合请求阶段：{chain.state}</p>
      <label>继续确认<select aria-label="续期继续确认" value={continuation} disabled={guard.busy} onChange={e => setContinuation(e.target.value)}><option value="">请明确选择</option><option value="continue">继续原请求中已确认未尝试的阶段</option></select></label>
      <button type="button" className="btn" disabled={guard.busy || !canContinue()} onClick={() => void advance()}>继续原续期请求</button>
    </div>}
    {publication && <p>已发布策略：{publication.policy.policyId} · 第 {publication.policy.revision} 版 · 头 {publication.headVersionBefore} → {publication.headVersionAfter}；不代表当前运行准入。</p>}
    {finalKnown && <button type="button" className="btn" disabled={guard.busy} onClick={() => {
      try { clearRenewalReference(); clearVisible(); setRef(null); setId(''); setFrom(''); setUntil(''); setMessage('请重新读取另一份来源并明确填写窗口；原历史记录仍由服务端保留。'); }
      catch { setMessage('无法保存新的页面状态，继续保留原请求，未开始新的申请。'); }
    }}>开始另一份续期申请</button>}
    <p role="status">{message}</p>
    {result && <p>原请求观察：{result.state}；审批与运行准入仍分别核验。</p>}
  </section>;
}
