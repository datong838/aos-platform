import { useEffect, useRef, useState } from 'react';
import type { RuntimeWorkshopEntry } from '../../api/runtimeWorkshop';
import { RuntimeWorkshopRead } from '../../api/runtimeWorkshopRead';
import { getAuthRevision, getTenant } from '../../api/tenant';
import { ExtensionHost, type ExtensionHostSpec } from './ExtensionHost';

export type RuntimeReadPort = Pick<RuntimeWorkshopRead, 'submit' | 'wait' | 'requestId'>;
type Limits = { caseLimit: number; runLimit: number };
type Props = {
  entry: RuntimeWorkshopEntry; isCurrent: () => boolean; navigate: (route: string) => void;
  createRead?: (entry: RuntimeWorkshopEntry, options: { isCurrent: () => boolean; signal: AbortSignal }, limits: Limits) => RuntimeReadPort;
};
const createRead: NonNullable<Props['createRead']> = (entry, options, limits) => new RuntimeWorkshopRead(entry, options, limits);

export function RuntimeWorkshopHost(props: Props) {
  const tenant = getTenant();
  // Revisions participate in remounting even if generation/resource bytes match.
  const key = JSON.stringify([props.entry, tenant.orgId, tenant.projectId, tenant.subject, tenant.roles, getAuthRevision()]);
  return <MountedRuntimeWorkshopHost key={key} {...props} />;
}

function MountedRuntimeWorkshopHost({ entry, isCurrent, navigate, createRead: factory = createRead }: Props) {
  const [controller] = useState(() => new AbortController());
  const [closed, setClosed] = useState(false);
  const [notice, setNotice] = useState('');
  const root = useRef<HTMLElement>(null);
  const currentRef = useRef(isCurrent); currentRef.current = isCurrent;
  const busy = useRef(false);
  const session = useRef<{ read: RuntimeReadPort; limits: string; terminal: boolean } | null>(null);
  const current = () => !controller.signal.aborted && currentRef.current();

  useEffect(() => {
    const stop = () => { controller.abort(); setClosed(true); };
    const events = ['aos-auth-updated', 'aos-tenant-updated', 'aos-workspace-changed'];
    events.forEach(event => window.addEventListener(event, stop));
    return () => { controller.abort(); events.forEach(event => window.removeEventListener(event, stop)); };
  }, [controller]);
  const available = isCurrent();
  useEffect(() => { if (!available) controller.abort(); }, [available, controller]);

  async function onRead(operationId: string, input: unknown) {
    if (!current() || busy.current || operationId !== 'analyst_workspace_view_v1'
        || !entry.ui.readOperationClaims.includes(operationId)) throw new Error('当前读取不可用。');
    const raw = input === null || input === undefined ? {} : input;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)
        || Object.keys(raw).some(key => !['caseLimit', 'runLimit'].includes(key))) throw new Error('读取参数无效。');
    const values = raw as Record<string, unknown>;
    const limits = { caseLimit: values.caseLimit ?? 20, runLimit: values.runLimit ?? 5 };
    if (!Number.isSafeInteger(limits.caseLimit) || Number(limits.caseLimit) < 1 || Number(limits.caseLimit) > 50
        || !Number.isSafeInteger(limits.runLimit) || Number(limits.runLimit) < 1 || Number(limits.runLimit) > 10) throw new Error('读取范围无效。');
    const limitsKey = JSON.stringify(limits);
    if (session.current && !session.current.terminal && session.current.limits !== limitsKey) throw new Error('请先查看原读取请求。');
    busy.current = true;
    setNotice('正在读取当前工作台数据…');
    try {
      if (!session.current || session.current.terminal) {
        const read = factory(entry, { isCurrent: current, signal: controller.signal }, limits as Limits);
        // Retain the consumed session even when submit confirmation is unknown.
        session.current = { read, limits: limitsKey, terminal: false };
        await read.submit();
      } else if (!session.current.read.requestId) {
        throw new Error('原提交尚未确认，不重复提交。');
      }
      const result = await session.current.read.wait();
      if (!current()) throw new Error('旧页面读取已停止。');
      session.current.terminal = result.state !== 'requested' && result.state !== 'claimed';
      setNotice(result.state === 'succeeded' ? '已取得当前工作台数据。' : '本次读取未完成，请检查工作台状态。');
      return result;
    } catch (error) {
      if (!controller.signal.aborted) setNotice(session.current?.read.requestId
        ? '尚未取得结果，可在页面内继续查看本次读取。' : '提交尚未确认，本次不会自动重复提交。');
      throw error;
    } finally { busy.current = false; }
  }
  function onNavigate(route: string) {
    if (!current() || !entry.ui.routeClaims.includes(route)) throw new Error('该工作台路径未声明。');
    navigate(route);
  }
  const spec: ExtensionHostSpec = {
    installationId: entry.installationId, generation: entry.generation, executionEpoch: entry.executionEpoch,
    title: entry.module.displayName, initialRoute: entry.module.route,
    routeClaims: entry.ui.routeClaims, readOperationClaims: entry.ui.readOperationClaims,
    commandOperationClaims: entry.ui.commandOperationClaims,
    signedResourceUrl: entry.ui.signedResourceUrl, resourceHash: entry.ui.resourceHash as `sha256:${string}`,
  };
  return <section ref={root} tabIndex={-1} aria-label="已安装工作台页面">
    {notice ? <p role="status">{notice}</p> : null}
    <ExtensionHost spec={closed || !available ? null : spec} effectiveState={closed || !available ? 'unavailable' : 'ready'}
      unavailableReason="当前账号或工作台已变化，请重新读取目录。"
      onRead={onRead} onNavigate={onNavigate} onRouteChanged={onNavigate}
      onFocusRequest={() => { if (current()) root.current?.focus(); }} />
  </section>;
}
