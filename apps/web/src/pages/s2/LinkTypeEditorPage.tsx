import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiDelete, apiGet, apiPost, apiPut } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpBanner, BpToolbar } from "./blueprintUi";

type LinkType = {
  id: string;
  name: string;
  srcType: string;
  dstType: string;
  rel: string;
  cardinality: string;
  expectedEdges: number;
  mdoApproved: boolean;
  published: boolean;
  description: string;
};

const emptyForm = (id = ""): LinkType => ({
  id,
  name: "",
  srcType: "WorkOrder",
  dstType: "WorkOrder",
  rel: "related_to",
  cardinality: "MANY_TO_MANY",
  expectedEdges: 0,
  mdoApproved: false,
  published: false,
  description: "",
});

/** 94 · Link Type 轻量编辑器 · 接已有 CRUD */
export function LinkTypeEditorPage() {
  const { linkId = "new" } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const isNew = linkId === "new";
  const [form, setForm] = useState<LinkType>(() =>
    emptyForm(isNew ? "" : linkId),
  );
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (isNew) {
      setForm(
        emptyForm(
          "",
        ),
      );
      const src = sp.get("src") || "WorkOrder";
      const dst = sp.get("dst") || src;
      setForm((f) => ({ ...f, srcType: src, dstType: dst }));
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const row = await apiGet<LinkType>(`/v1/ontology/link-types/${encodeURIComponent(linkId)}`);
        if (!cancelled) setForm(row);
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [linkId, isNew, sp]);

  function patch<K extends keyof LinkType>(key: K, value: LinkType[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save() {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const id = form.id.trim();
      if (!id) throw new Error("请填写 id");
      if (!form.name.trim()) throw new Error("请填写 name");
      const body = { ...form, id, name: form.name.trim() };
      if (isNew) {
        await apiPost("/v1/ontology/link-types", body);
        setMsg(`已创建 ${id}`);
        navigate(`/ontology/link-types/${encodeURIComponent(id)}`, { replace: true });
      } else {
        await apiPut(`/v1/ontology/link-types/${encodeURIComponent(id)}`, body);
        setMsg("已保存");
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (isNew) return;
    if (!window.confirm(`删除 Link Type ${form.id}？不级联删除 graph_edge。`)) return;
    setBusy(true);
    setErr("");
    try {
      await apiDelete(`/v1/ontology/link-types/${encodeURIComponent(form.id)}`);
      navigate("/ontology");
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const scaleWarn = form.expectedEdges > 100_000 && !form.mdoApproved;

  return (
    <S2Chrome
      title={isNew ? "新建 Link Type" : `Link Type · ${form.id}`}
      lede="元数据编辑 · 规模红线需 MDO 批准 · 不级联实例边"
    >
      <div className="ont-page">
        <BpToolbar>
          <Link to="/ontology" className="btn-nav">
            ← 发现
          </Link>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>
            {busy ? "保存中…" : isNew ? "创建" : "保存"}
          </button>
          {!isNew && (
            <button type="button" className="btn" disabled={busy} onClick={() => void remove()}>
              删除
            </button>
          )}
        </BpToolbar>
        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}
        {scaleWarn && (
          <BpBanner tone="warn">
            expectedEdges &gt; 100k 且未勾选 MDO 批准时，保存会被服务端拒绝（LINK_SCALE_BLOCKED）。
          </BpBanner>
        )}
        <div className="ont-form-grid" style={{ marginTop: "0.75rem" }}>
          <label className="ont-form-field">
            <span>id</span>
            <input
              className="aos-input"
              value={form.id}
              disabled={!isNew}
              onChange={(e) => patch("id", e.target.value)}
              placeholder="lt-related-to"
            />
          </label>
          <label className="ont-form-field">
            <span>name</span>
            <input className="aos-input" value={form.name} onChange={(e) => patch("name", e.target.value)} />
          </label>
          <label className="ont-form-field">
            <span>srcType</span>
            <input className="aos-input" value={form.srcType} onChange={(e) => patch("srcType", e.target.value)} />
          </label>
          <label className="ont-form-field">
            <span>dstType</span>
            <input className="aos-input" value={form.dstType} onChange={(e) => patch("dstType", e.target.value)} />
          </label>
          <label className="ont-form-field">
            <span>rel</span>
            <input className="aos-input" value={form.rel} onChange={(e) => patch("rel", e.target.value)} />
          </label>
          <label className="ont-form-field">
            <span>cardinality</span>
            <select
              className="aos-input"
              value={form.cardinality}
              onChange={(e) => patch("cardinality", e.target.value)}
            >
              <option value="MANY_TO_MANY">MANY_TO_MANY</option>
              <option value="ONE_TO_MANY">ONE_TO_MANY</option>
              <option value="MANY_TO_ONE">MANY_TO_ONE</option>
              <option value="ONE_TO_ONE">ONE_TO_ONE</option>
            </select>
          </label>
          <label className="ont-form-field">
            <span>expectedEdges</span>
            <input
              className="aos-input"
              type="number"
              value={form.expectedEdges}
              onChange={(e) => patch("expectedEdges", Number(e.target.value) || 0)}
            />
          </label>
          <label className="ont-form-field ont-form-span">
            <span>description</span>
            <input
              className="aos-input"
              value={form.description}
              onChange={(e) => patch("description", e.target.value)}
            />
          </label>
        </div>
        <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
          <label className="ont-form-check">
            <input
              type="checkbox"
              checked={form.mdoApproved}
              onChange={(e) => patch("mdoApproved", e.target.checked)}
            />
            MDO 批准（大规模边）
          </label>
          <label className="ont-form-check">
            <input
              type="checkbox"
              checked={form.published}
              onChange={(e) => patch("published", e.target.checked)}
            />
            已发布
          </label>
        </div>
      </div>
    </S2Chrome>
  );
}
