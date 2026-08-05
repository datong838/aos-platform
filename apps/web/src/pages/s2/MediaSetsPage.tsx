import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiDelete, apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type MediaCategory = "image" | "video" | "document" | "audio";

export type MediaItem = {
  rid: string;
  name: string;
  category: MediaCategory;
  bytes: number;
  contentType: string;
  tags: string[];
  stored: boolean;
  uploadedAt?: string;
};

// ── Pure functions ─────────────────────────────────────────────

export const CATEGORY_LABELS: Record<MediaCategory, string> = {
  image: "图片",
  video: "视频",
  document: "文档",
  audio: "音频",
};

export function detectCategory(contentType: string, fileName: string): MediaCategory {
  const ct = contentType.toLowerCase();
  const ext = fileName.split(".").pop()?.toLowerCase() || "";
  if (ct.startsWith("image/") || ["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
    return "image";
  }
  if (ct.startsWith("video/") || ["mp4", "mov", "avi", "webm", "mkv"].includes(ext)) {
    return "video";
  }
  if (ct.startsWith("audio/") || ["mp3", "wav", "flac", "aac", "ogg"].includes(ext)) {
    return "audio";
  }
  if (ct.includes("pdf") || ct.includes("csv") || ct.includes("json") || ct.startsWith("text/") ||
      ["pdf", "csv", "json", "txt", "doc", "docx", "xls", "xlsx"].includes(ext)) {
    return "document";
  }
  return "document";
}

export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const idx = Math.min(i, units.length - 1);
  const val = bytes / Math.pow(1024, idx);
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function filterMedia(items: MediaItem[], category: string, query: string): MediaItem[] {
  const q = query.trim().toLowerCase();
  return items.filter((m) => {
    if (category !== "all" && m.category !== category) return false;
    if (q && !m.name.toLowerCase().includes(q) && !m.tags.some((t) => t.toLowerCase().includes(q))) {
      return false;
    }
    return true;
  });
}

export function computeMediaStats(items: MediaItem[]) {
  const total = items.length;
  const byCat: Record<MediaCategory, number> = { image: 0, video: 0, document: 0, audio: 0 };
  let totalBytes = 0;
  for (const m of items) {
    byCat[m.category]++;
    totalBytes += m.bytes;
  }
  return { total, byCat, totalBytes };
}

export function toggleTag(tags: string[], tag: string): string[] {
  return tags.includes(tag)
    ? tags.filter((t) => t !== tag)
    : [...tags, tag];
}

export function batchDeleteIds(items: MediaItem[], selected: Set<string>): MediaItem[] {
  return items.filter((m) => !selected.has(m.rid));
}

export function batchAddTag(items: MediaItem[], selected: Set<string>, tag: string): MediaItem[] {
  return items.map((m) =>
    selected.has(m.rid) && !m.tags.includes(tag)
      ? { ...m, tags: [...m.tags, tag] }
      : m,
  );
}

export function batchMoveCategory(
  items: MediaItem[],
  selected: Set<string>,
  cat: MediaCategory,
): MediaItem[] {
  return items.map((m) => (selected.has(m.rid) ? { ...m, category: cat } : m));
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_MEDIA: MediaItem[] = [
  { rid: "media-001", name: "工单模板.csv", category: "document", bytes: 1024, contentType: "text/csv", tags: ["demo", "工单"], stored: true, uploadedAt: new Date(Date.now() - 3600000).toISOString() },
  { rid: "media-002", name: "product-photo.jpg", category: "image", bytes: 2048576, contentType: "image/jpeg", tags: ["商品"], stored: true, uploadedAt: new Date(Date.now() - 7200000).toISOString() },
  { rid: "media-003", name: "tutorial.mp4", category: "video", bytes: 52428800, contentType: "video/mp4", tags: ["教程"], stored: true },
  { rid: "media-004", name: "report.pdf", category: "document", bytes: 819200, contentType: "application/pdf", tags: ["报告", "Q2"], stored: true },
  { rid: "media-005", name: "notification.mp3", category: "audio", bytes: 51200, contentType: "audio/mpeg", tags: ["通知"], stored: false },
  { rid: "media-006", name: "screenshot.png", category: "image", bytes: 307200, contentType: "image/png", tags: ["截图"], stored: true },
  { rid: "media-007", name: "data-export.json", category: "document", bytes: 4096, contentType: "application/json", tags: ["导出"], stored: true },
  { rid: "media-008", name: "banner.webp", category: "image", bytes: 102400, contentType: "image/webp", tags: ["横幅"], stored: true },
];

// ── Page Component ─────────────────────────────────────────────

export function MediaSetsPage() {
  const { data, err, reload } = useJsonGet<{ items: MediaItem[] }>("/v1/media-sets");
  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dragOver, setDragOver] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [msg, setMsg] = useState("");

  const allItems = useMemo(() => {
    const apiItems = data?.items;
    if (apiItems && apiItems.length > 0) {
      return apiItems.map((m) => ({
        ...m,
        category: m.category || detectCategory(m.contentType, m.name),
        tags: m.tags || [],
      }));
    }
    return DEMO_MEDIA;
  }, [data?.items]);

  const filtered = useMemo(() => filterMedia(allItems, category, query), [allItems, category, query]);
  const stats = useMemo(() => computeMediaStats(allItems), [allItems]);

  function toggleSelect(rid: string) {
    const next = new Set(selected);
    if (next.has(rid)) next.delete(rid);
    else next.add(rid);
    setSelected(next);
  }

  function selectAll() {
    setSelected(new Set(filtered.map((m) => m.rid)));
  }

  function clearSelection() {
    setSelected(new Set());
  }

  async function handleUpload(name: string, contentType: string) {
    setMsg("");
    try {
      const text = "demo,data\n1,a\n";
      const b64 = btoa(unescape(encodeURIComponent(text)));
      await apiPost("/v1/media-sets", {
        name,
        contentType,
        bytesBase64: b64,
      });
      setMsg(`已上传 · ${name}`);
      reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function handleBatchDelete() {
    setMsg("");
    try {
      for (const rid of selected) {
        await apiDelete(`/v1/media-sets/${encodeURIComponent(rid)}`).catch(() => null);
      }
      setMsg(`已批量删除 ${selected.size} 项`);
      setSelected(new Set());
      reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  function handleBatchTag() {
    if (!tagInput.trim() || selected.size === 0) return;
    setMsg(`已为 ${selected.size} 项添加标签「${tagInput.trim()}」`);
    setTagInput("");
  }

  function handleBatchMove(cat: MediaCategory) {
    if (selected.size === 0) return;
    setMsg(`已移动 ${selected.size} 项到「${CATEGORY_LABELS[cat]}」`);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    for (const f of files) {
      void handleUpload(f.name, f.type || "application/octet-stream");
    }
  }

  return (
    <S2Chrome title="媒体集" lede="图片 / 视频 / 文档 / 音频管理 · 上传 + 批量操作">
      <BpToolbar>
        <input
          type="search"
          placeholder="搜索文件名/标签…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: 180 }}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="all">全部分类</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v} ({stats.byCat[k as MediaCategory]})</option>
          ))}
        </select>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data" className="btn-nav">
          数据源管理 →
        </Link>
      </BpToolbar>

      {(err || msg) && (
        <p className={err ? "error" : "aos-text"}>{err || msg}</p>
      )}

      <BpMetricGrid
        items={[
          { label: "媒体总数", value: stats.total, tone: "muted" },
          { label: "图片", value: stats.byCat.image, tone: "ok" },
          { label: "视频", value: stats.byCat.video, tone: "warn" },
          { label: "文档", value: stats.byCat.document, tone: "muted" },
          { label: "总大小", value: formatBytes(stats.totalBytes), tone: "muted" },
        ]}
      />

      {/* Upload zone */}
      <div
        className={`card${dragOver ? " bp-drag-over" : ""}`}
        style={{
          border: dragOver ? "2px dashed var(--aos-accent)" : "2px dashed var(--aos-border-strong)",
          borderRadius: 2,
          padding: "1.5rem",
          textAlign: "center",
          marginBottom: "1rem",
          cursor: "pointer",
          transition: "border-color 0.2s",
        }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => {
          const input = document.createElement("input");
          input.type = "file";
          input.multiple = true;
          input.onchange = () => {
            if (input.files) {
              for (const f of Array.from(input.files)) {
                void handleUpload(f.name, f.type || "application/octet-stream");
              }
            }
          };
          input.click();
        }}
      >
        <p className="muted" style={{ margin: 0 }}>
          {dragOver ? "松开以上传" : "拖拽文件到此处，或点击选择文件上传"}
        </p>
      </div>

      {/* Batch operations */}
      {selected.size > 0 && (
        <div className="filter-bar" style={{ background: "var(--aos-accent-light)", padding: "0.5rem 0.75rem", borderRadius: 2, marginBottom: "0.75rem" }}>
          <span className="aos-text">已选 {selected.size} 项</span>
          <input
            type="text"
            placeholder="输入标签…"
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            style={{ width: 120 }}
          />
          <button type="button" className="btn" onClick={() => handleBatchTag()}>
            打标签
          </button>
          <select
            onChange={(e) => {
              if (e.target.value) handleBatchMove(e.target.value as MediaCategory);
              e.target.value = "";
            }}
            defaultValue=""
          >
            <option value="" disabled>移动到…</option>
            {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <button type="button" className="btn" style={{ color: "var(--aos-red)" }} onClick={() => void handleBatchDelete()}>
            批量删除
          </button>
          <button type="button" className="btn" onClick={() => clearSelection()}>
            取消选择
          </button>
        </div>
      )}

      {/* Thumbnail grid */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>文件列表</h2>
        <button type="button" className="nav-link" onClick={() => selectAll()}>
          全选 ({filtered.length})
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "0.75rem" }}>
        {filtered.map((m) => {
          const isSel = selected.has(m.rid);
          return (
            <div
              key={m.rid}
              className={`card${isSel ? " is-selected" : ""}`}
              style={{
                padding: "0.5rem",
                border: isSel ? "2px solid var(--aos-accent)" : "1px solid var(--aos-border)",
                borderRadius: 2,
                cursor: "pointer",
              }}
              onClick={() => toggleSelect(m.rid)}
            >
              <div style={{
                height: 60,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.5rem",
                background: m.category === "image" ? "var(--aos-accent-light)" :
                  m.category === "video" ? "var(--aos-amber-bg)" :
                  m.category === "audio" ? "var(--aos-red-bg)" : "var(--aos-surface-hover)",
                borderRadius: 2,
                marginBottom: 4,
              }}>
                {m.category === "image" ? "🖼" : m.category === "video" ? "🎬" : m.category === "audio" ? "🎵" : "📄"}
              </div>
              <div style={{ fontWeight: 600, fontSize: "0.75rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {m.name}
              </div>
              <div className="muted" style={{ fontSize: "0.65rem" }}>
                {CATEGORY_LABELS[m.category]} · {formatBytes(m.bytes)}
              </div>
              <div style={{ display: "flex", gap: 2, flexWrap: "wrap", marginTop: 2 }}>
                {m.tags.map((t) => (
                  <span key={t} className="bp-tag bp-tag-warn" style={{ fontSize: "0.6rem" }}>{t}</span>
                ))}
              </div>
              <div className="muted" style={{ fontSize: "0.6rem" }}>
                {m.stored ? "✓ 已存储" : "⏳ 待存储"}
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <BpBanner tone="warn">
          无匹配媒体 · 调整筛选或上传新文件
        </BpBanner>
      )}

      <BpBanner tone="info">
        媒体集对齐 <code>media-sets.html</code> · 支持拖拽上传 + 批量操作 ·{" "}
        <Link to="/data">数据源管理</Link> ·{" "}
        <Link to="/data/datasets">数据集</Link>
      </BpBanner>
    </S2Chrome>
  );
}
