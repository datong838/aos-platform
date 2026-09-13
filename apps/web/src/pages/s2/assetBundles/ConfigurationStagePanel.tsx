import { useEffect, useRef, useState } from 'react';
import { assetControlClient } from '../../../api/assetControl/client';
import { createIdempotentCommand, type IdempotencyKey } from '../../../api/assetControl/idempotency';
import type { ConfigurationStageReceipt } from '../../../api/assetControl/configurationStaging';
import type { RuntimeInstallation } from '../../../api/assetControl/types';
import type { AssetReadState } from './model';
import { configurationIdentity, useConfigurationSources } from './readHooks';

type Attempt = { identity: string; installationId?: string; key: IdempotencyKey; receipt?: ConfigurationStageReceipt; message: string };
export function ConfigurationStagePanel({ state, offline, blocked, onRegistered }: {
  state: AssetReadState<RuntimeInstallation>; offline: boolean; blocked: boolean; onRegistered: () => void;
}) {
  const runtime = state.data;
  const sources = useConfigurationSources(runtime);
  const [role, setRole] = useState('');
  const [policy, setPolicy] = useState('');
  const [recoveryKey, setRecoveryKey] = useState('');
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [busy, setBusy] = useState(false);
  const [autoPaused, setAutoPaused] = useState(false);
  const pollBudget = useRef({ key: '', used: 0 });
  const lock = useRef(false);
  const currentAttempt = useRef<Attempt | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const identity = configurationIdentity();
  const visible = attempt?.identity === identity ? attempt : null;
  const catalog = sources.data;
  const ready = Boolean(runtime?.binding && state.status === 'ready' && !state.stale && !state.refreshing
    && sources.isCurrent() && !sources.stale && !sources.refreshing && catalog?.target
    && catalog.target.installationId === runtime.installationId && catalog.installationRevision === runtime.installationRevision
    && catalog.target.installationEtag === runtime.installationEtag && catalog.target.generation === runtime.binding.generation
    && catalog.target.bindingRevision === runtime.binding.revision);
  const selectedRole = ready ? catalog?.roles.find(item => JSON.stringify(item.ref) === role)?.ref : undefined;
  const selectedPolicy = ready ? catalog?.policies.find(item => JSON.stringify(item.ref) === policy)?.ref : undefined;
  const terminal = (value: Attempt | null) => Boolean(value?.receipt && value.receipt.state !== 'requested' && 'result' in value.receipt);
  const unresolved = Boolean(visible && !terminal(visible));
  const unavailable = offline || blocked || busy;
  useEffect(() => { setRole(''); setPolicy(''); setRecoveryKey(''); }, [identity, runtime?.installationId, runtime?.binding?.generation, runtime?.binding?.revision]);
  const publish = (value: Attempt) => {
    if (!mounted.current || value.identity !== configurationIdentity()) return;
    currentAttempt.current = value; setAttempt(value);
  };
  async function query(value: Attempt) {
    if (lock.current || offline || blocked || value.identity !== configurationIdentity()) return;
    lock.current = true; setBusy(true);
    try {
      const receipt = value.receipt?.requestId
        ? await assetControlClient.getConfigurationStage(value.receipt.requestId)
        : await assetControlClient.findConfigurationStage(value.key);
      if (value.receipt && receipt.requestHash !== value.receipt.requestHash) throw new Error('请求不匹配');
      publish({ ...value, receipt, message: receipt.state === 'succeeded' ? '配置已登记。请在配置列表中选择并完成绑定。' : receipt.state === 'rejected' ? '登记被拒绝，请检查当前来源和权限后重新准备。' : receipt.state === 'expired' ? '登记已过期，可以重新读取来源后准备新请求。' : '已受理，正在等待处理；稍后查询结果。' });
      if (mounted.current && value.identity === configurationIdentity() && receipt.state === 'succeeded') onRegistered();
    } catch {
      publish({ ...value, message: '暂时无法确认结果。请保留原请求键，稍后只读查询；不要重复登记。' });
    } finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function submit() {
    if (lock.current || unavailable || !ready || !sources.isCurrent() || !selectedRole || !selectedPolicy || !catalog?.target
      || (currentAttempt.current?.identity === identity && !terminal(currentAttempt.current))) return;
    const value: Attempt = { identity, installationId: runtime!.installationId, key: createIdempotentCommand().idempotencyKey, message: '正在提交登记请求…' };
    lock.current = true; setBusy(true); publish(value);
    try {
      const receipt = await assetControlClient.stageConfiguration({ schemaVersion: 'aos.runtime-configuration-stage/v1', action: 'stage-configuration',
        target: catalog.target, roleRefs: [selectedRole], policyRef: selectedPolicy, previousRef: null }, value.key);
      publish({ ...value, receipt, message: '已受理。请查询登记结果；登记完成后再绑定配置。' });
    } catch {
      publish({ ...value, message: '提交结果尚未确认。请保留原请求键并查询结果，不要重复登记。' });
    } finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  const queryRef = useRef(query);
  queryRef.current = query;
  useEffect(() => {
    if (!visible || !unresolved || offline || blocked) return;
    const budgetKey = JSON.stringify([identity, visible.key]);
    if (pollBudget.current.key !== budgetKey) pollBudget.current = { key: budgetKey, used: 0 };
    setAutoPaused(pollBudget.current.used >= 10);
    if (pollBudget.current.used >= 10) return;
    const timer = window.setInterval(() => {
      const value = currentAttempt.current;
      if (!value || value.identity !== configurationIdentity() || value.key !== visible.key) {
        window.clearInterval(timer); return;
      }
      pollBudget.current.used += 1;
      void queryRef.current(value);
      if (pollBudget.current.used >= 10) { window.clearInterval(timer); setAutoPaused(true); }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [visible?.key, identity, unresolved, offline, blocked]);
  if (!runtime?.binding && !visible) return null;
  return <section aria-label="登记运行配置">
    <h3>登记运行配置</h3>
    <p>选择职责计划与运行策略；系统校验其预算、数据范围和当前权限后登记配置。</p>
    {!ready && <p role="status">{sources.status === 'forbidden' ? '当前账号无权读取配置来源。' : (sources.status === 'error' || sources.status === 'not_visible_or_missing') ? '配置来源暂时不可用，请稍后刷新。' : '来源正在读取或已变化，请刷新后选择。'}</p>}
    {ready && (!catalog?.roles.length || !catalog.policies.length) && <p role="status">缺少可选的当前职责计划或运行策略，请先完成来源配置。</p>}
    <label>职责计划<select aria-label="职责计划" value={selectedRole ? role : ''} disabled={unavailable || unresolved || !ready} onChange={event => setRole(event.target.value)}>
      <option value="">请选择职责计划</option>{(ready ? catalog?.roles : [])?.map(item => <option key={item.ref.id} value={JSON.stringify(item.ref)}>{item.label} · 版本 {item.ref.revision} · {item.ref.id}</option>)}
    </select></label>
    <label>运行策略<select aria-label="运行策略" value={selectedPolicy ? policy : ''} disabled={unavailable || unresolved || !ready} onChange={event => setPolicy(event.target.value)}>
      <option value="">请选择运行策略</option>{(ready ? catalog?.policies : [])?.map(item => <option key={item.ref.id} value={JSON.stringify(item.ref)}>{item.label} · 版本 {item.ref.revision}</option>)}
    </select></label>
    {(catalog?.rolesHasMore || catalog?.policiesHasMore) && <p>当前仅显示前50项来源，未显示全部来源。</p>}
    <button type="button" className="btn" disabled={unavailable} onClick={sources.reload}>刷新配置来源</button>
    <button type="button" className="btn btn-primary" disabled={unavailable || unresolved || !selectedRole || !selectedPolicy} onClick={() => void submit()}>登记所选配置</button>
    {visible && <div><p>{visible.installationId ? `原登记安装：${visible.installationId}` : "找回的原请求，请按原登记记录核对所属安装。"}</p><p role="status">{visible.message}</p>{unresolved && <p>{autoPaused ? "自动查询已暂停；结果仍待确认，可使用原请求键手工查询。" : "正在自动跟踪登记结果，最多查询10轮。"}</p>}<p>原请求键：<code>{visible.key}</code>。离开页面前请保存，用于找回结果。</p>
      {visible.receipt?.failureCode && <details><summary>拒绝原因代码</summary>{visible.receipt.failureCode}</details>}
      <button type="button" className="btn" disabled={unavailable} onClick={() => void query(visible)}>查询原请求结果</button></div>}
    {!unresolved && <details><summary>找回已有登记请求</summary><label>原请求键<input aria-label="原请求键" value={recoveryKey} maxLength={160} onChange={event => setRecoveryKey(event.target.value)} /></label>
      <button type="button" className="btn" disabled={unavailable || !recoveryKey.trim()} onClick={() => {
        const value = { identity: configurationIdentity(), key: recoveryKey.trim() as IdempotencyKey, message: '正在只读找回原请求…' };
        publish(value); void query(value);
      }}>只读找回</button></details>}
  </section>;
}
