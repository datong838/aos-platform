import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";
import objects from "./mocks/objects.json";
import {
  AskResponse,
  ChatMessage,
  HealthState,
  aggregateHealth,
  appendAssistantFromAsk,
  appendUserMessage,
  buildAskBody,
  citationsForPanel,
} from "./lib/buddy";

const ASK_URL =
  import.meta.env.VITE_BUDDY_ASK_URL || "http://127.0.0.1:8090/v1/buddy/ask";
const HEALTH_URL =
  import.meta.env.VITE_BUDDY_HEALTH_URL || "http://127.0.0.1:8090/healthz";

type Obj = { object_id: string; display_name: string; type: string };

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function labelPart(p: "up" | "down" | "unknown") {
  if (p === "up") return "正常";
  if (p === "down") return "异常";
  return "未知";
}

function labelOverall(o: "green" | "red" | "yellow") {
  if (o === "green") return "正常";
  if (o === "red") return "异常";
  return "待检";
}

type HealthzJson = {
  status?: string;
  dify_reachable?: boolean;
  demo_mode?: boolean;
};

/** 只探 Adapter /healthz（含 dify_reachable），避免直连 Dify 根路径因无 CORS 假报 down */
async function fetchHealthFromAdapter(): Promise<{
  adapter: "up" | "down";
  dify: "up" | "down";
}> {
  try {
    const r = await fetch(HEALTH_URL, { method: "GET", mode: "cors" });
    if (!r.ok) {
      return { adapter: "down", dify: "down" };
    }
    const data = (await r.json()) as HealthzJson;
    return {
      adapter: "up",
      dify: data.dify_reachable ? "up" : "down",
    };
  } catch {
    return { adapter: "down", dify: "down" };
  }
}

export default function BuddyLegacyApp() {
  const list = objects as Obj[];
  const [selected, setSelected] = useState<string | null>(list[0]?.object_id ?? null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [health, setHealth] = useState<HealthState>({
    dify: "unknown",
    openocta: "unknown",
    adapter: "unknown",
  });

  const [showFix, setShowFix] = useState(false);

  const overall = useMemo(() => aggregateHealth(health), [health]);
  const cites = useMemo(() => citationsForPanel(messages), [messages]);
  const selectedObj = list.find((o) => o.object_id === selected);

  useEffect(() => {
    setShowFix(overall === "red");
  }, [overall]);

  const refreshHealth = useCallback(async () => {
    const { adapter, dify } = await fetchHealthFromAdapter();
    setHealth({
      dify,
      adapter,
      openocta: "unknown",
    });
  }, []);

  useEffect(() => {
    refreshHealth();
    const t = setInterval(refreshHealth, 15000);
    return () => clearInterval(t);
  }, [refreshHealth]);

  async function onSend(e?: FormEvent) {
    e?.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);
    setMessages((m) => appendUserMessage(m, q, uid()));
    try {
      const body = buildAskBody(q, selected);
      const r = await fetch(ASK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await r.json()) as AskResponse;
      setMessages((m) => appendAssistantFromAsk(m, data, uid()));
    } catch (err) {
      setMessages((m) =>
        appendAssistantFromAsk(
          m,
          {
            trace_id: "local-error",
            answer: "服务暂时不可用，请检查本机 Docker / 模型配置后重试。",
            citations: [],
            status: "error",
            refuse_reason: String(err),
          },
          uid()
        )
      );
    } finally {
      setLoading(false);
      refreshHealth();
    }
  }

  return (
    <div className="buddy-legacy-shell app-shell">
      <header className="topbar">
        <div className="brand">AOS 桌面 · Buddy 三栏（增量）</div>
        <div className="health" title="状态指示；点「刷新健康」重新探测">
          <span className="health-stat">
            <i className={`dot ${overall}`} />
            总览 {labelOverall(overall)}
          </span>
          <span className="health-stat">知识引擎 {labelPart(health.dify)}</span>
          <span className="health-stat">接入服务 {labelPart(health.adapter)}</span>
          <button
            type="button"
            className="health-refresh"
            onClick={() => void refreshHealth()}
          >
            刷新健康
          </button>
        </div>
      </header>

      {showFix && (
        <div className="empty" style={{ borderBottom: "1px solid var(--border)", padding: "10px 16px" }}>
          本机依赖不可用。请按顺序：1) 启动 Docker　2) 启动知识引擎　3) 启动接入服务；仍异常请联系交付同事。
          <button type="button" style={{ marginLeft: 12 }} onClick={() => setShowFix(false)}>
            知道了
          </button>
        </div>
      )}

      <div className="main">
        <aside className="panel">
          <h2>业务对象</h2>
          <div className="obj-list">
            {list.map((o) => (
              <div
                key={o.object_id}
                className={`obj-item ${selected === o.object_id ? "active" : ""}`}
                onClick={() => setSelected(o.object_id)}
              >
                <div className="name">{o.display_name}</div>
                <div className="meta">
                  {o.object_id} · {o.type}
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="chat panel" style={{ borderRight: "none" }}>
          <h2>Chat</h2>
          {selectedObj && (
            <div className="chip">context · {selectedObj.object_id}</div>
          )}
          <div className="messages">
            {messages.length === 0 && (
              <div className="empty">向企业知识库提问；右侧显示引用溯源。</div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`bubble ${m.role}`}>
                {m.content}
                {m.refuse_reason && m.status === "error" && (
                  <div style={{ marginTop: 8, fontSize: 11, color: "#fbbf24", wordBreak: "break-word" }}>
                    详情: {m.refuse_reason}
                  </div>
                )}
                {m.trace_id && (
                  <div style={{ marginTop: 6, fontSize: 11, color: "var(--text-muted)" }}>
                    trace: {m.trace_id}
                  </div>
                )}
              </div>
            ))}
          </div>
          <form className="composer" onSubmit={onSend}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入问题…"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              {loading ? "…" : "发送"}
            </button>
          </form>
        </section>

        <aside className="panel">
          <h2>溯源 Citations</h2>
          <div className="cite-list">
            {cites.length === 0 ? (
              <div className="empty">暂无引用。有命中时将显示文档片段。</div>
            ) : (
              cites.map((c, i) => (
                <div key={`${c.doc_name}-${i}`} className="cite-card">
                  <div className="doc">
                    {c.doc_name}
                    {c.page != null ? ` · p.${c.page}` : ""}
                    {c.score != null ? ` · ${c.score.toFixed(2)}` : ""}
                  </div>
                  <div className="snip">{c.snippet || ""}</div>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
