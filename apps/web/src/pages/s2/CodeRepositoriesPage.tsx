import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BpBanner,
  BpMetricGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type RepoProvider = "github" | "gitlab" | "bitbucket" | "azuredevops" | "ssh";

export type RepoStatus = "synced" | "syncing" | "error" | "disconnected";

export type RepoFile = {
  path: string;
  type: "file" | "dir";
  size?: number;
  lastCommit?: string;
};

export type Repository = {
  id: string;
  name: string;
  url: string;
  branch: string;
  provider: RepoProvider;
  status: RepoStatus;
  lastSyncedAt: string;
  commitCount: number;
  openPRs: number;
  contributors: number;
  files: RepoFile[];
  readme: string;
};

export type RepositoryList = {
  repos: Repository[];
  total: number;
};

// ── Constants ──────────────────────────────────────────────────

export const PROVIDER_LABEL: Record<RepoProvider, string> = {
  github: "GitHub",
  gitlab: "GitLab",
  bitbucket: "Bitbucket",
  azuredevops: "Azure DevOps",
  ssh: "SSH / 本地",
};

export const STATUS_LABEL: Record<RepoStatus, string> = {
  synced: "已同步",
  syncing: "同步中",
  error: "错误",
  disconnected: "未连接",
};

export const STATUS_TONE: Record<RepoStatus, "ok" | "warn" | "bad" | "muted"> = {
  synced: "ok",
  syncing: "warn",
  error: "bad",
  disconnected: "muted",
};

// ── Pure functions ─────────────────────────────────────────────

export function formatTimestamp(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function filterRepos(
  repos: Repository[],
  query: string,
  provider: RepoProvider | "all",
  status: RepoStatus | "all",
): Repository[] {
  const q = query.trim().toLowerCase();
  return repos.filter((r) => {
    if (provider !== "all" && r.provider !== provider) return false;
    if (status !== "all" && r.status !== status) return false;
    if (!q) return true;
    return (
      r.name.toLowerCase().includes(q) ||
      r.url.toLowerCase().includes(q) ||
      r.branch.toLowerCase().includes(q)
    );
  });
}

// ── Page Component ─────────────────────────────────────────────

export function CodeRepositoriesPage() {
  const { data, err, loading } = useJsonGet<RepositoryList>("/v1/code-repositories");
  const rl = data;

  const [selectedId, setSelectedId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("readme");

  const repos = useMemo(() => rl?.repos ?? [], [rl]);

  const filteredRepos = useMemo(
    () => filterRepos(repos, query, "all", "all"),
    [repos, query],
  );

  const selected = useMemo(
    () => repos.find((r) => r.id === selectedId) ?? filteredRepos[0] ?? null,
    [repos, selectedId, filteredRepos],
  );

  const syncedCount = repos.filter((r) => r.status === "synced").length;

  return (
    <S2Chrome title="代码仓库" lede="工程代码目录 · 非 Git 主机">
      <BpToolbar>
        <input
          type="search"
          placeholder="搜索仓库…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: 180 }}
        />
        <span className="muted" style={{ marginLeft: "auto", fontSize: "0.75rem" }}>
          共 {rl?.total ?? 0} 个仓库
        </span>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {!loading && !err && repos.length === 0 && (
        <p className="muted">暂无仓库数据。</p>
      )}

      {repos.length > 0 && (
        <>
          <BpMetricGrid
            items={[
              { label: "仓库总数", value: rl?.total ?? 0, tone: "muted" },
              { label: "已同步", value: syncedCount, tone: "ok" },
              { label: "异常", value: repos.filter((r) => r.status === "error").length, tone: "bad" },
              { label: "未连接", value: repos.filter((r) => r.status === "disconnected").length, tone: "muted" },
            ]}
          />

          <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "0.75rem" }}>
            {/* Left: Repo list */}
            <div>
              <div className="bp-object-panel" style={{ maxHeight: 480, overflowY: "auto" }}>
                {filteredRepos.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setSelectedId(r.id)}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      padding: "0.5rem",
                      border: "none",
                      borderLeft: selected?.id === r.id ? "3px solid var(--aos-accent, #3b82f6)" : "3px solid transparent",
                      background: selected?.id === r.id ? "var(--aos-surface-hover, #f5f5f5)" : "transparent",
                      cursor: "pointer",
                      font: "inherit",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong className="mono">{r.name}</strong>
                      <span className={`bp-discover-badge bp-discover-badge-${STATUS_TONE[r.status]}`}>
                        {STATUS_LABEL[r.status]}
                      </span>
                    </div>
                    <div className="muted" style={{ fontSize: "0.7rem", marginTop: 2 }}>
                      {PROVIDER_LABEL[r.provider]} · {r.branch}
                    </div>
                    {r.commitCount > 0 && (
                      <div className="muted" style={{ fontSize: "0.65rem" }}>
                        {r.commitCount.toLocaleString()} 次提交
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Repo detail */}
            <div>
              {selected ? (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                    <h3 className="aos-text">{selected.name}</h3>
                    <span className={`bp-discover-badge bp-discover-badge-${STATUS_TONE[selected.status]}`}>
                      {STATUS_LABEL[selected.status]}
                    </span>
                  </div>
                  <p className="muted" style={{ fontSize: "0.75rem", marginBottom: "0.5rem" }}>
                    <span className="mono">{selected.url}</span> · 分支{" "}
                    <span className="mono">{selected.branch}</span>
                    {selected.lastSyncedAt && ` · ${formatTimestamp(selected.lastSyncedAt)}`}
                  </p>

                  <BpMetricGrid
                    density="compact"
                    items={[
                      { label: "提交数", value: selected.commitCount > 0 ? selected.commitCount.toLocaleString() : "—", tone: "muted" },
                      { label: "贡献者", value: selected.contributors, tone: "muted" },
                      { label: "供应商", value: PROVIDER_LABEL[selected.provider], tone: "ok" },
                    ]}
                  />

                  <BpTabs
                    tabs={[
                      { id: "readme", label: "README" },
                      { id: "files", label: "文件" },
                    ]}
                    active={tab}
                    onChange={setTab}
                  />

                  {tab === "readme" && (
                    <div className="bp-object-panel">
                      <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>{selected.readme}</pre>
                    </div>
                  )}

                  {tab === "files" && (
                    <div>
                      {selected.files.length > 0 ? (
                        <BpTable
                          columns={["路径", "类型", "大小", "最近提交"]}
                          rows={selected.files.map((f) => [
                            <span className="mono">{f.path}</span>,
                            f.type === "dir" ? "📁 目录" : "📄 文件",
                            f.size != null ? `${f.size} B` : "—",
                            f.lastCommit ?? "—",
                          ])}
                        />
                      ) : (
                        <p className="muted" style={{ fontSize: "0.75rem" }}>
                          当前 HEAD 快照没有可显示的顶层文件。
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <BpBanner tone="warn">请选择一个仓库</BpBanner>
              )}
            </div>
          </div>
        </>
      )}

      <BpBanner tone="info">
        代码仓库 · AOS Platform ·{" "}
        <Link to="/data/pipelines">管道</Link>
      </BpBanner>
    </S2Chrome>
  );
}
