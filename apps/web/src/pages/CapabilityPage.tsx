import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpBanner,
  BpDebugPanel,
  BpDiscoverCard,
  BpLinkRow,
  BpMetricGrid,
  BpToolbar,
} from "./s2/blueprintUi";

type CapItem = { id: string; kind?: string; endpoint?: string };

const BLUEPRINT_CAPS = [
  { id: "video-job", title: "短视频生成", kind: "job", desc: "C1 Job · GPU · → MediaSet", tone: "ok" as const },
  { id: "live-script", title: "直播稿引擎", kind: "sync", desc: "C0 sync / 可升 C1 · → LiveScript", tone: "ok" as const },
  { id: "avatar-commerce", title: "电商可交互数字人", kind: "session", desc: "C2 Session · AV 外置 · AvatarSession", tone: "warn" as const },
  { id: "avatar-edu", title: "教育可交互数字人", kind: "session", desc: "C2 Session · 课纲 Wiki · CourseSession", tone: "muted" as const },
];

/** 83 · 对齐 aip-capabilities · 能力卡片 + Session + Job */
export function CapabilityPage() {
  const [items, setItems] = useState<CapItem[]>([]);
  const [mediaRid, setMediaRid] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [lastPayload, setLastPayload] = useState<unknown>(null);

  async function reloadCaps() {
    try {
      const r = await apiGet<{ items: CapItem[] }>("/v1/aip/capabilities");
      setItems(r.items || []);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    void reloadCaps();
  }, []);

  const registered = useMemo(() => new Set(items.map((c) => c.id)), [items]);

  async function runJob() {
    setErr(null);
    setMsg("");
    try {
      await apiPost("/v1/aip/capabilities", { id: "video-job", kind: "job" });
      const job = await apiPost<{
        jobId: string;
        artifact?: { mediaRid?: string; rid?: string };
      }>("/v1/aip/capabilities/video-job/invoke", {
        kind: "job",
        input: { clip: "demo" },
      });
      const rid = job.artifact?.mediaRid || job.artifact?.rid || null;
      setMediaRid(rid);
      setMsg(`Job ${job.jobId} 完成`);
      setLastPayload(job);
      await reloadCaps();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function openSession() {
    setErr(null);
    try {
      const r = await apiPost<{ sessionId?: string; status?: string }>(
        "/v1/aip/capabilities/session/open",
        { avatar: "commerce", objectType: "AvatarSession" },
      );
      setSessionId(r.sessionId || null);
      setMsg(`Session ${r.sessionId} · ${r.status}`);
      setLastPayload(r);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  return (
    <PageChrome
      title="重能力接入（Capability）"
      lede="Studio 编剧本，重代码出肌肉。运行时走 Facade，写回经 Action；UI 不直连厂商 SDK。"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void runJob()}>
          登记并提交 Job
        </button>
        <button type="button" className="btn" onClick={() => void openSession()}>
          打开 C2 Session
        </button>
        <button type="button" className="btn" onClick={() => void reloadCaps()}>
          刷新
        </button>
      </BpToolbar>

      <BpBanner tone="warn">
        <strong>大脑 vs 肌肉</strong> · C0 同步轻能力可进 Function；C1 Job / C2 Session 外置 Adapter，超 FUNC-03 禁止塞进沙箱。
      </BpBanner>

      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      {mediaRid && (
        <p className="aos-text">
          产物 MediaSet：<code>{mediaRid}</code> · <Link to="/data/media-sets">媒体集</Link>
        </p>
      )}
      {sessionId && (
        <BpMetricGrid
          items={[
            { label: "Session ID", value: sessionId, tone: "ok" },
            { label: "AV 外置", value: "是", tone: "ok" },
            { label: "Draft 门控", value: "默认", tone: "warn" },
          ]}
        />
      )}

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        已接入
      </div>
      <div className="bp-discover-grid">
        {BLUEPRINT_CAPS.map((c, i) => {
          const live = registered.has(c.id);
          const badgeLabel = live
            ? "已登记"
            : c.tone === "muted"
              ? "停用"
              : c.kind === "session" && sessionId
                ? "会话中"
                : "就绪";
          const badgeTone: "ok" | "warn" | "bad" =
            live ? "ok" : c.tone === "muted" ? "warn" : c.tone === "warn" ? "warn" : "ok";
          return (
            <BpDiscoverCard
              key={c.id}
              accent={i % 2 === 0 ? "violet" : "muted"}
              title={c.title}
              badge={{ label: badgeLabel, tone: badgeTone }}
              meta={c.desc}
              cta={`${c.kind?.toUpperCase()} · ${c.id}`}
              onClick={() => setMsg(`配置 ${c.id} · ${live ? "已登记" : "就绪"}`)}
            />
          );
        })}
      </div>

      {items.length > 0 && (
        <>
          <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            API 登记 ({items.length})
          </div>
          <ul className="card-list">
            {items.map((c) => (
              <li key={c.id} className="card">
                <strong>{c.id}</strong> · {c.kind || "sync"}{" "}
                <span className="muted">{c.endpoint || ""}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {lastPayload != null && <BpDebugPanel value={lastPayload} title="Invoke 原始 JSON" />}

      <BpLinkRow
        links={[
          { to: "/aip/tools", label: "工具面板" },
          { to: "/data/media-sets", label: "MediaSet" },
          { to: "/aip/drafts", label: "Draft 审批" },
        ]}
      />
    </PageChrome>
  );
}
