import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type {
  JsonValue,
  RuntimeAction,
  RuntimeInstallation,
  RuntimeConfigurationCandidates,
  RuntimeOperationAccepted,
} from "../../../api/assetControl/types";
import type { AssetControlError } from "../../../api/assetControl/errors";
import { ExtensionHost, type ExtensionHostSpec } from "../../../components/extensions/ExtensionHost";
import type { AssetReadState } from "./model";
import type { ConfigurationReadState } from "./readHooks";

const LABELS: Record<RuntimeAction, string> = {
  "runtime-apply": "准备运行资源",
  "runtime-verify": "验证运行资源",
  configure: "更新运行配置",
  enable: "启用运行实例",
  disable: "停用运行实例",
};

const FAILURE_LABELS: Readonly<Record<string, string>> = {
  PREPARATION_VALIDATION_FAILED: "运行资源未通过准入校验，请核对签名、权限和安装版本后重新准备。",
  PREPARATION_EXECUTION_FAILED: "运行资源准备失败，请先查看审计事件并确认资源已安全回收。",
  PREPARATION_STOPPED: "运行资源准备已停止，请刷新状态后按服务端允许动作重新发起。",
  PREPARATION_EXPIRED: "运行资源准备已超过有效期，请刷新后发起新命令。",
  RESOURCE_CLEANUP_UNCERTAIN: "运行资源清理结果尚未确认，恢复完成前不能继续操作。",
};

const CANDIDATES = [
  { key: "responsibility_plans", label: "职责计划", href: "/aip/production-contracts" },
  { key: "runtime_policies", label: "运行策略", href: null },
  { key: "data_policies", label: "数据分类策略", href: "/aip/model-runtime" },
  { key: "egress_policies", label: "出站策略", href: "/aip/model-runtime" },
  { key: "network_policies", label: "网络策略", href: null },
  { key: "quota_policies", label: "模型配额", href: "/aip/capacity" },
  { key: "budget_policies", label: "预算策略", href: null },
  { key: "budgets", label: "预算修订", href: null },
] as const;

function failureMessage(code: string): string {
  return FAILURE_LABELS[code] ?? "运行操作未完成，请查看审计事件并按服务端允许动作处理。";
}

function eventLabel(type: string): string {
  if (type.endsWith("_accepted")) return "命令已受理";
  if (type.endsWith("_committed")) return "结果已提交";
  if (type.endsWith("_failed")) return "操作失败";
  if (type === "accepted") return "命令已受理";
  return "运行状态已更新";
}

export interface RuntimeInstallationPanelProps {
  state: AssetReadState<RuntimeInstallation>;
  configurations?: ConfigurationReadState;
  candidates?: AssetReadState<RuntimeConfigurationCandidates> & { isCurrent: () => boolean };
  offline: boolean;
  pending: RuntimeAction | null;
  error: AssetControlError | null;
  receipt: RuntimeOperationAccepted | null;
  preparationExecutable?: boolean;
  hasRetrySameCommand: boolean;
  canRetrySameCommand: boolean;
  onRetrySameCommand: () => void;
  onExecute: (kind: RuntimeAction, target?: Record<string, JsonValue>) => void;
}

const panelStyle = { border: "1px solid var(--aos-border)", borderRadius: 3, padding: 12 } as const;

export function RuntimeInstallationPanel({ state, configurations, candidates, offline, pending, error, receipt, preparationExecutable = false, hasRetrySameCommand, onExecute }: RuntimeInstallationPanelProps) {
  const runtime = state.data;
  const [selected, setSelected] = useState<RuntimeAction | null>(null);
  const [configurationChoice, setConfigurationChoice] = useState("");
  const catalog = configurations?.data;
  const candidateData = candidates?.data;
  const candidatesCurrent = Boolean(runtime && candidateData && candidates?.status === "ready" && candidates.isCurrent()
    && !candidates.stale && !candidates.refreshing && candidateData.installationId === runtime.installationId
    && candidateData.installationRevision === runtime.installationRevision
    && candidateData.installationEtag === runtime.installationEtag);
  const configurationReady = Boolean(runtime?.binding && catalog && configurations?.isCurrent()
    && !configurations.stale && !configurations.refreshing && configurations.status === "ready"
    && catalog.installationId === runtime.installationId && catalog.installationRevision === runtime.installationRevision
    && catalog.installationEtag === runtime.installationEtag && catalog.generation === runtime.binding.generation
    && catalog.bindingRevision === runtime.binding.revision);
  const selectedConfiguration = configurationReady ? catalog?.items.find(item => JSON.stringify(item.ref) === configurationChoice)?.ref : undefined;
  useEffect(() => { if (!configurationReady || !selectedConfiguration) { if (configurationChoice && selected === "configure") setSelected(null); setConfigurationChoice(""); } }, [configurationReady, selectedConfiguration, configurationChoice, selected]);
  const hostSpec = useMemo<ExtensionHostSpec | null>(() => {
    if (!runtime?.ui || !runtime.binding) return null;
    return {
      installationId: runtime.installationId,
      generation: runtime.binding.generation,
      executionEpoch: runtime.binding.executionEpoch,
      ...runtime.ui,
    };
  }, [runtime]);

  const interactionBlocked = offline || pending !== null || state.stale || state.refreshing || hasRetrySameCommand;
  const preparationBlocked = (action: RuntimeAction) =>
    (action === "runtime-apply" || action === "runtime-verify") && !preparationExecutable;
  const allowedActionKey = runtime?.allowedActions.join("\u0000") ?? "";
  const bindingIdentityKey = runtime?.binding
    ? `${runtime.binding.generation}\u0000${runtime.binding.revision}\u0000${runtime.binding.executionEpoch}`
    : "";
  useEffect(() => setSelected(null), [runtime?.installationId, runtime?.installationRevision, bindingIdentityKey]);
  useEffect(() => {
    if (selected && (interactionBlocked || preparationBlocked(selected) || !runtime?.allowedActions.includes(selected))) setSelected(null);
  }, [allowedActionKey, interactionBlocked, preparationExecutable, runtime?.allowedActions, selected]);

  function target(kind: RuntimeAction): Record<string, JsonValue> | undefined {
    if (kind === "runtime-apply" || kind === "runtime-verify") return undefined;
    if (!runtime?.binding) return undefined;
    if (kind === "disable") return { generation: runtime.binding.generation, bindingRevision: runtime.binding.revision };
    const existing = runtime.binding.configRef;
    const configRef = kind === "enable" && existing
      ? existing
      : selectedConfiguration ? { ...selectedConfiguration } : undefined;
    if (!configRef) return undefined;
    return { generation: runtime.binding.generation, bindingRevision: runtime.binding.revision, configRef };
  }

  const selectedTarget = selected ? target(selected) : undefined;
  const configureValid = selected !== "configure" || Boolean(selectedConfiguration);
  const targetValid = selected === null || selected === "runtime-apply" || selected === "runtime-verify" || Boolean(selectedTarget);

  return (
    <section aria-label="运行实例控制" style={panelStyle}>
      <header>
        <h3 style={{ margin: 0 }}>运行实例</h3>
        <p>安装生命周期与运行实例分别展示；按钮来自服务端允许动作，操作先形成可审计回执，再由运行工作进程执行。</p>
      </header>
      {state.status === "idle" && <p role="status">请选择一条安装记录。</p>}
      {state.status === "loading" && <p role="status">正在读取运行状态…</p>}
      {(state.status === "forbidden" || state.status === "not_visible_or_missing") && <p role="alert">当前运行实例不可见或不存在。</p>}
      {state.status === "error" && <p role="alert">运行状态读取失败：{state.error?.message ?? "未知错误"} <button className="btn" onClick={state.reload}>重试读取</button></p>}
      {state.refreshing && <p role="status">正在刷新运行状态…</p>}
      {state.stale && <p role="alert">当前运行状态已过期；刷新成功前禁止操作。</p>}

      {runtime && (
        <div>
          <dl aria-label="服务端运行状态">
            <div><dt>有效状态</dt><dd>{runtime.effectiveState}</dd></div>
            <div><dt>安装状态 / revision</dt><dd>{runtime.installationState} / {runtime.installationRevision}</dd></div>
            <div><dt>运行代次</dt><dd>{runtime.binding?.generation ?? "尚未建立"}</dd></div>
            <div><dt>期望 / 观测</dt><dd>{runtime.binding ? `${runtime.binding.desiredState} / ${runtime.binding.observedState}` : "尚无运行绑定"}</dd></div>
            <div><dt>执行纪元 / binding revision</dt><dd>{runtime.binding ? `${runtime.binding.executionEpoch} / ${runtime.binding.revision}` : "—"}</dd></div>
          </dl>
          {runtime.reasons.map((reason) => <p role="status" key={reason}>{reason}</p>)}
          {!preparationExecutable && runtime.allowedActions.some(action => action === "runtime-apply" || action === "runtime-verify") && <p role="alert">当前 Host 或租户 Owner 尚未核验为可执行；运行准备/验证已禁入，请先完成正式运行准入。</p>}
          <section aria-label="当前配置权威候选" style={{ margin: "10px 0" }}>
            <h4>当前配置权威候选</h4>
            <p>以下是当前租户的正式候选数，不代表已绑定本安装，也不代表可以启用。运行准入仍由服务端逐项复验。</p>
            {!candidatesCurrent && <p role="status">配置权威未核验或读回已过期；不会把未知当作缺失或就绪。</p>}
            {candidatesCurrent && <ul>{CANDIDATES.map(item => {
              const count = candidateData!.counts[item.key];
              return <li key={item.key}>{item.label}：{count === 0 ? "缺少当前候选" : `${count} 个当前候选，尚需安装绑定核验`} · {item.href ? <Link to={item.href}>进入正式配置入口</Link> : "产品配置入口待建"}</li>;
            })}</ul>}
            <button type="button" className="btn" disabled={offline || pending !== null || !candidates} onClick={candidates?.reload}>刷新权威候选</button>
          </section>
          <section aria-label="已登记配置">
            <h4>已登记配置</h4>
            {configurationReady ? <ul>{catalog?.items.map((item, index) => <li key={JSON.stringify(item.ref)}>配置 {index + 1} · 版本 {item.ref.revision}{item.isCurrent ? " · 当前绑定" : ""}</li>)}</ul>
              : <p role="status">{configurations?.status === "forbidden" ? "当前账号无权查看配置列表。" : configurations?.status === "empty" ? "当前代际尚未登记配置。" : "配置列表正在读取或需要刷新。"}</p>}
            {catalog?.hasMore && <p>当前显示前50条配置。</p>}
            <button type="button" className="btn" disabled={offline || pending !== null || !configurations} onClick={configurations?.reload}>刷新配置列表</button>
          </section>
          {runtime.currentOperation && (
            <section aria-label="最近运行操作" style={{ margin: "10px 0" }}>
              <p role="status">最近操作：{LABELS[runtime.currentOperation.kind]} · {runtime.currentOperation.phase} / {runtime.currentOperation.status} · revision {runtime.currentOperation.revision}</p>
              {runtime.currentOperation.failureCode && (
                <p role="alert">{failureMessage(runtime.currentOperation.failureCode)} 合法下一步以服务端允许动作区为准。</p>
              )}
              {runtime.currentOperation.events.length > 0 && (
                <details>
                  <summary>查看运行审计事件（{runtime.currentOperation.events.length}）</summary>
                  <ol>{runtime.currentOperation.events.map((event) => (
                    <li key={event.sequence}>第 {event.sequence} 步 · {eventLabel(event.type)} · <time dateTime={event.occurredAt}>{event.occurredAt}</time></li>
                  ))}</ol>
                </details>
              )}
            </section>
          )}

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {runtime.allowedActions.map((action) => (
              <button key={action} type="button" className={action === "disable" ? "btn" : "btn btn-primary"} disabled={interactionBlocked || preparationBlocked(action)} onClick={() => setSelected(action)}>{LABELS[action]}</button>
            ))}
          </div>
          {runtime.allowedActions.length === 0 && !runtime.currentOperation && <p role="status">当前状态没有可执行的运行动作。</p>}

          {selected && (
            <section role="dialog" aria-modal="true" aria-label={`${LABELS[selected]}确认`} style={{ marginTop: 12, padding: 12, border: "1px solid var(--aos-border)" }}>
              <h4>{LABELS[selected]}确认</h4>
              {selected === "configure" && (
                <div style={{ display: "grid", gap: 8 }}>
                  <label>选择已登记配置<select aria-label="选择已登记配置" value={configurationChoice} disabled={!configurationReady || interactionBlocked} onChange={event => setConfigurationChoice(event.target.value)}>
                    <option value="">请选择配置</option>
                    {(configurationReady ? catalog?.items ?? [] : []).map((item, index) => <option key={JSON.stringify(item.ref)} value={JSON.stringify(item.ref)}>配置 {index + 1} · 版本 {item.ref.revision}{item.isCurrent ? " · 当前绑定" : ""}</option>)}
                  </select></label>
                  <p>提交时会重新校验配置来源和当前权限。</p>
                  {!configurationReady && <p role="status">{configurations?.status === "empty" ? "当前代际尚未登记配置，请先完成配置登记。" : "配置列表尚未就绪或已失效，请重新读取。"}</p>}
                  {catalog?.hasMore && <p role="status">当前显示前50条配置；列表尚未全部展示。</p>}
                  <button className="btn" type="button" disabled={offline || pending !== null || !configurations} onClick={configurations?.reload}>重新读取配置</button>
                </div>
              )}
              {(selected === "enable" || selected === "disable") && <p>目标代次与 binding revision 已锁定为当前服务端值；状态变化时服务端会拒绝执行。</p>}
              {(selected === "runtime-apply" || selected === "runtime-verify") && <p>该操作只提交运行准备回执，不会由浏览器直接执行外部副作用。</p>}
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn" type="button" disabled={pending !== null} onClick={() => setSelected(null)}>取消</button>
                <button className="btn btn-primary" type="button" disabled={interactionBlocked || preparationBlocked(selected) || !runtime.allowedActions.includes(selected) || !configureValid || !targetValid} onClick={() => { if (preparationBlocked(selected) || (selected === "configure" && (!selectedConfiguration || !configurations?.isCurrent()))) return; onExecute(selected, selectedTarget); setSelected(null); }}>确认{LABELS[selected]}</button>
              </div>
            </section>
          )}
          {receipt && <p role="status">运行操作已受理 · {receipt.phase} / {receipt.status} · 回执 {receipt.operationId}</p>}
          {error && <p role="alert">运行操作失败：{error.message}</p>}
          {hasRetrySameCommand && <p role="alert">运行命令结果未知：已冻结重发，请只读核对服务端操作与回执；不要更换幂等键或再次提交。</p>}
          {hostSpec && (
            <ExtensionHost
              spec={hostSpec}
              effectiveState={runtime.effectiveState}
              unavailableReason={runtime.reasons[0] ?? null}
              onRead={() => Promise.reject(new Error("资产控制页未声明业务读取处理器"))}
              onCommand={() => Promise.reject(new Error("资产控制页未声明业务命令处理器"))}
            />
          )}
        </div>
      )}
    </section>
  );
}
