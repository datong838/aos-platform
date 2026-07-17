import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

type DemoStep = {
  id: string;
  title: string;
  uiPath: string;
  api: string;
  say: string;
};

type DemoStory = {
  storyId: string;
  title: string;
  deferred?: { apolloOps?: boolean; analyticsNotebook?: boolean; note?: string };
  snapshot?: {
    objectType?: string;
    objectCount?: number;
    objects?: { id: string; title?: string; status?: string }[];
    pendingDrafts?: number;
    modules?: number;
  };
  steps?: DemoStep[];
};

/** TB.8 hub — customer demo narrative driven by /v1/demo/story */
export function DemoPage() {
  const [story, setStory] = useState<DemoStory | null>(null);
  const [gov, setGov] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  async function load() {
    setErr(null);
    try {
      const s = await apiGet<DemoStory>("/v1/demo/story");
      setStory(s);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function ensureSeed() {
    setMsg("");
    try {
      await apiPost("/v1/demo/ensure-seed", {});
      setMsg("种子已确保 · WorkOrder");
      await load();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function runWriteback() {
    setMsg("");
    try {
      const r = await apiPost<{
        before?: { status?: string };
        after?: { status?: string };
        draftId?: string;
        lineageId?: string;
        objectId?: string;
      }>("/v1/demo/run-story", {});
      setMsg(
        `写回 OK · ${r.objectId} status ${r.before?.status} → ${r.after?.status} · draft=${r.draftId} · lineage=${r.lineageId}`,
      );
      await load();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function loadGovernance() {
    setMsg("");
    try {
      const r = await apiGet<{
        say?: string;
        asPublicViewer?: { redactedFields?: string[]; internalCost?: number };
        markingForbidden?: { code?: string };
        latestLineage?: { id?: string };
      }>("/v1/demo/governance");
      setGov(r);
      const red = (r.asPublicViewer?.redactedFields || []).join(",") || "(none)";
      setMsg(
        `治理 OK · 脱敏字段=${red} · FORBIDDEN=${r.markingForbidden?.code ?? "n/a"} · lineage=${r.latestLineage?.id ?? "暂无（先一键写回）"}`,
      );
    } catch (e) {
      setMsg(String((e as Error).message || e));
      setGov(null);
    }
  }

  async function runCapability() {
    setMsg("");
    try {
      const r = await apiPost<{
        job?: { jobId?: string; mediaRid?: string; status?: string };
        parser?: { ok?: boolean; parser?: string };
        ocrProbe?: { ok?: boolean; sidecar?: string };
      }>("/v1/demo/run-capability", {});
      setMsg(
        `Capability OK · job=${r.job?.jobId} media=${r.job?.mediaRid} · parse=${r.parser?.ok ? r.parser?.parser : "fail"} · ocr=${r.ocrProbe?.ok ? "sidecar" : r.ocrProbe?.sidecar || "unset"}`,
      );
      setGov(r);
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <PageChrome
      title="客户演示导航"
      lede="TB.* 业务平台本地演示 · Apollo 运维后置 · 不对标 Jupyter/1.3"
    >
      <button type="button" className="btn" onClick={() => void load()}>
        刷新故事
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void ensureSeed()}>
        确保种子
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void runWriteback()}>
        一键写回（TB.4）
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void loadGovernance()}>
        治理探针（TB.7）
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void runCapability()}>
        Capability/OCR 一镜（TB.9）
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      {story && (
        <>
          <p className="muted">
            {story.title} · {story.snapshot?.objectType} × {story.snapshot?.objectCount} · Drafts{" "}
            {story.snapshot?.pendingDrafts ?? 0} · Modules {story.snapshot?.modules ?? 0}
          </p>
          {story.deferred?.note && <p className="muted">{story.deferred.note}</p>}
          <ol className="card-list">
            {(story.steps || []).map((st) => (
              <li key={st.id} className="card">
                <strong>
                  {st.id} · {st.title}
                </strong>
                <p className="muted">{st.say}</p>
                <p className="muted">{st.api}</p>
                <Link to={st.uiPath}>打开 {st.uiPath}</Link>
              </li>
            ))}
          </ol>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            样例对象
          </h2>
          <ul className="card-list">
            {(story.snapshot?.objects || []).map((o) => (
              <li key={o.id} className="card">
                <strong>{o.id}</strong>{" "}
                <span className="muted">
                  {o.title} · {o.status}
                </span>
              </li>
            ))}
          </ul>
          {gov != null && (
            <>
              <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
                治理探针结果
              </h2>
              <pre className="aos-text" style={{ fontSize: "0.75rem", whiteSpace: "pre-wrap" }}>
                {JSON.stringify(gov, null, 2)}
              </pre>
            </>
          )}
        </>
      )}
    </PageChrome>
  );
}
