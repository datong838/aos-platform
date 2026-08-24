import { useEffect, useRef, useState } from "react";

import { EcommerceWorkshopClientError, ecommerceWorkshopClient, type WorkshopSharedContextResponse } from "../../api/ecommerceWorkshop";

type Client = Pick<typeof ecommerceWorkshopClient, "getSharedContext">;
const TOKEN = /^[A-Za-z0-9_-]{32,128}$/;

function refLabel(ref: NonNullable<WorkshopSharedContextResponse["context"]["primaryRef"]>): string {
  return `${ref.resourceType} · ${ref.resourceId} · r${ref.revision}`;
}

export function EcommerceWorkshopSharedContext({ contextId, currentRoute = null, client = ecommerceWorkshopClient }: { contextId: string | null; currentRoute?: string | null; client?: Client }) {
  const request = useRef(0);
  const [response, setResponse] = useState<WorkshopSharedContextResponse | null>(null);
  const [phase, setPhase] = useState<"idle" | "loading" | "ready" | "blocked" | "failed">("idle");
  useEffect(() => {
    const id = ++request.current;
    setResponse(null);
    if (contextId === null) { setPhase("idle"); return; }
    if (!TOKEN.test(contextId)) { setPhase("blocked"); return; }
    setPhase("loading");
    void client.getSharedContext(contextId).then((value) => { if (id !== request.current) return; setResponse(value); setPhase(value.context.status === "ready" ? "ready" : "blocked"); }, (error: unknown) => { if (id !== request.current) return; setPhase(error instanceof EcommerceWorkshopClientError || error instanceof TypeError ? "blocked" : "failed"); });
  }, [client, contextId]);
  if (phase === "idle") return null;
  if (phase === "loading") return <aside className="ecommerce-workshop-context-refs" aria-label="共享上下文" aria-busy="true"><p>正在重建共享上下文…</p></aside>;
  if (phase !== "ready" || response === null) return <aside className="ecommerce-workshop-context-refs" aria-label="共享上下文"><p><strong>共享上下文不可用</strong></p><p>{response?.context.blockers[0]?.code ?? "SHARED_CONTEXT_INVALID_OR_UNAVAILABLE"}</p></aside>;
  const { context, timeline, navigationTargets } = response;
  const primaryRef = context.primaryRef;
  if (primaryRef === null) return <aside className="ecommerce-workshop-context-refs" aria-label="共享上下文"><p><strong>共享上下文不可用</strong></p><p>SHARED_CONTEXT_INVALID_OR_UNAVAILABLE</p></aside>;
  return <aside className="ecommerce-workshop-context-refs" aria-label="共享上下文">
    <section aria-label="对象与任务引用"><p><strong>共享对象</strong></p><p>{refLabel(primaryRef)}</p><p>用途：{context.purpose}</p><p>数据截止：{context.dataCutoff}</p><p>标记：{context.markings.join("、")}</p></section>
    <section aria-label="运行时间线"><p><strong>运行时间线</strong></p>{timeline.length === 0 ? <p>当前无可披露事件</p> : <ol>{timeline.map((event) => <li key={event.eventKey}><span>{event.eventType} · {event.status}</span><br /><span>{event.safeSummary}</span>{event.unknown ? <small> · unknown retained</small> : null}{event.reconciled ? <small> · reconciled</small> : null}</li>)}</ol>}</section>
    <nav aria-label="共享上下文导航"><p><strong>继续查看</strong></p>{navigationTargets.map((target) => target.status === "available" && target.route ? <a key={target.targetId} href={`${target.route}?context=${encodeURIComponent(context.contextId)}&target=${encodeURIComponent(target.targetId)}`} aria-current={target.route === currentRoute ? "page" : undefined}>{target.viewId}{target.filterSummary ? ` · ${target.filterSummary}` : ""}</a> : <span key={target.targetId} aria-disabled="true">目标不可用 · {target.status}</span>)}</nav>
  </aside>;
}
