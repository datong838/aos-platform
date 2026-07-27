import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
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

// ── Pure functions ─────────────────────────────────────────────

export const PROVIDER_LABEL: Record<RepoProvider, string> = {
  github: "GitHub",
  gitlab: "GitLab",
  bitbucket: "Bitbucket",
  azuredevops: "Azure DevOps",
  ssh: "SSH",
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

export function sortRepos(
  repos: Repository[],
  sortBy: "name" | "lastSynced" | "commits",
): Repository[] {
  return [...repos].sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "commits") return b.commitCount - a.commitCount;
    return new Date(b.lastSyncedAt).getTime() - new Date(a.lastSyncedAt).getTime();
  });
}

export function filterFiles(files: RepoFile[], query: string): RepoFile[] {
  const q = query.trim().toLowerCase();
  if (!q) return files;
  return files.filter((f) => f.path.toLowerCase().includes(q));
}

export function countByProvider(repos: Repository[]): Record<RepoProvider, number> {
  const acc: Record<RepoProvider, number> = {
    github: 0,
    gitlab: 0,
    bitbucket: 0,
    azuredevops: 0,
    ssh: 0,
  };
  for (const r of repos) acc[r.provider]++;
  return acc;
}

export function countByStatus(repos: Repository[]): Record<RepoStatus, number> {
  const acc: Record<RepoStatus, number> = {
    synced: 0,
    syncing: 0,
    error: 0,
    disconnected: 0,
  };
  for (const r of repos) acc[r.status]++;
  return acc;
}

export function validateRepoUrl(url: string): string | null {
  if (!url.trim()) return "URL 不能为空";
  if (!/^https?:\/\/.+|^git@.+|^ssh:\/\//.test(url)) {
    return "URL 格式无效（需以 https:// / git@ / ssh:// 开头）";
  }
  if (url.length < 10) return "URL 过短";
  return null;
}

export function repoNameFromUrl(url: string): string {
  const clean = url.replace(/\.git$/, "").replace(/\/$/, "");
  const parts = clean.split("/");
  return parts[parts.length - 1] || clean;
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_REPOS: Repository[] = [
  {
    id: "repo-001",
    name: "aos-platform",
    url: "https://github.com/company/aos-platform",
    branch: "main",
    provider: "github",
    status: "synced",
    lastSyncedAt: new Date(Date.now() - 5 * 60000).toISOString(),
    commitCount: 3421,
    openPRs: 7,
    contributors: 12,
    readme: "# AOS Platform\n\n企业 AI 操作系统平台主仓库。",
    files: [
      { path: "src/", type: "dir" },
      { path: "src/main.ts", type: "file", size: 2048, lastCommit: "feat: add endpoint" },
      { path: "README.md", type: "file", size: 512, lastCommit: "docs: update readme" },
      { path: "pyproject.toml", type: "file", size: 1024, lastCommit: "build: bump version" },
    ],
  },
  {
    id: "repo-002",
    name: "data-pipelines",
    url: "https://gitlab.com/company/data-pipelines",
    branch: "develop",
    provider: "gitlab",
    status: "syncing",
    lastSyncedAt: new Date(Date.now() - 1 * 60000).toISOString(),
    commitCount: 894,
    openPRs: 3,
    contributors: 6,
    readme: "# Data Pipelines\n\nETL 管道和批处理作业集合。",
    files: [
      { path: "pipelines/", type: "dir" },
      { path: "pipelines/sync_orders.py", type: "file", size: 4096, lastCommit: "fix: null handling" },
      { path: "config.yaml", type: "file", size: 256, lastCommit: "chore: config update" },
    ],
  },
  {
    id: "repo-003",
    name: "ml-models",
    url: "https://bitbucket.org/company/ml-models",
    branch: "main",
    provider: "bitbucket",
    status: "error",
    lastSyncedAt: new Date(Date.now() - 240 * 60000).toISOString(),
    commitCount: 567,
    openPRs: 2,
    contributors: 4,
    readme: "# ML Models\n\n机器学习模型训练和部署。",
    files: [
      { path: "models/", type: "dir" },
      { path: "train.py", type: "file", size: 8192, lastCommit: "feat: new model" },
    ],
  },
  {
    id: "repo-004",
    name: "infra-config",
    url: "https://ssh://git@internal.company/infra-config",
    branch: "master",
    provider: "ssh",
    status: "disconnected",
    lastSyncedAt: "",
    commitCount: 128,
    openPRs: 0,
    contributors: 2,
    readme: "# Infra Config\n\n基础设施配置仓库。",
    files: [],
  },
];

const DEMO_DATA: RepositoryList = {
  repos: DEMO_REPOS,
  total: DEMO_REPOS.length,
};

// ── Page Component ─────────────────────────────────────────────

export function CodeRepositoriesPage() {
  const { data, err, loading } = useJsonGet<RepositoryList>("/v1/code-repositories");
  const rl = data ?? DEMO_DATA;

  const [selectedId, setSelectedId] = useState<string>(rl.repos[0]?.id ?? "");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<RepoProvider | "all">("all");
  const [statusFilter, setStatusFilter] = useState<RepoStatus | "all">("all");
  const [sortBy, setSortBy] = useState<"name" | "lastSynced" | "commits">("lastSynced");
  const [fileQuery, setFileQuery] = useState("");
  const [tab, setTab] = useState("files");
  const [msg, setMsg] = useState("");

  const filteredRepos = useMemo(
    () => sortRepos(filterRepos(rl.repos, query, provider, statusFilter), sortBy),
    [rl.repos, query, provider, statusFilter, sortBy],
  );

  const selected = useMemo(
    () => rl.repos.find((r) => r.id === selectedId) ?? filteredRepos[0],
    [rl.repos, selectedId, filteredRepos],
  );

  const filteredFiles = useMemo(
    () => (selected ? filterFiles(selected.files, fileQuery) : []),
    [selected, fileQuery],
  );

  const statusCounts = useMemo(() => countByStatus(rl.repos), [rl.repos]);

  async function handleClone() {
    if (!selected) return;
    setMsg("");
    try {
      await apiPost(`/v1/code-repositories/${selected.id}/clone`, {});
      setMsg(`已触发克隆 ${selected.name}`);
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function handlePull() {
    if (!selected) return;
    setMsg("");
    try {
      await apiPost(`/v1/code-repositories/${selected.id}/pull`, {});
      setMsg(`已拉取 ${selected.name}`);
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function handlePush() {
    if (!selected) return;
    setMsg("");
    try {
      await apiPost(`/v1/code-repositories/${selected.id}/push`, {});
      setMsg(`已推送 ${selected.name}`);
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="代码仓库" lede="管理代码仓库连接、分支和同步状态">
      <BpToolbar>
        <Link to="/data/code-repos/new" className="btn-primary">+ 新建仓库</Link>
        <span className="muted" style={{ marginLeft: "auto", fontSize: "0.75rem" }}>
          共 {rl.total} 个仓库
        </span>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "仓库总数", value: rl.total, tone: "muted" },
          { label: "已同步", value: statusCounts.synced, tone: "ok" },
          { label: "同步中", value: statusCounts.syncing, tone: "warn" },
          { label: "错误", value: statusCounts.error, tone: statusCounts.error > 0 ? "bad" : "ok" },
        ]}
      />

      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "0.75rem" }}>
        {/* Left: Repo list */}
        <div>
          <BpToolbar>
            <input
              type="search"
              placeholder="搜索仓库…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ minWidth: 120 }}
            />
          </BpToolbar>
          <div style={{ display: "flex", gap: 4, marginBottom: "0.5rem", flexWrap: "wrap" }}>
            <select value={provider} onChange={(e) => setProvider(e.target.value as RepoProvider | "all")}>
              <option value="all">全部供应商</option>
              {Object.entries(PROVIDER_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as RepoStatus | "all")}>
              <option value="all">全部状态</option>
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
              <option value="lastSynced">最近同步</option>
              <option value="name">名称</option>
              <option value="commits">提交数</option>
            </select>
          </div>
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
                  borderLeft: selected?.id === r.id ? "3px solid var(--p-accent, #2563eb)" : "3px solid transparent",
                  background: selected?.id === r.id ? "var(--p-hover, rgba(0,0,0,0.04))" : "transparent",
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
                <span className="mono">{selected.branch}</span> ·{" "}
                {formatTimestamp(selected.lastSyncedAt)}
              </p>

              <BpToolbar>
                <button type="button" className="btn-nav" onClick={() => void handleClone()}>
                  克隆
                </button>
                <button type="button" className="btn-nav" onClick={() => void handlePull()}>
                  拉取
                </button>
                <button type="button" className="btn-nav" onClick={() => void handlePush()}>
                  推送
                </button>
                <Link to={`/data/code-repos/${selected.id}/diff`} className="btn-nav">
                  查看差异
                </Link>
              </BpToolbar>

              <BpMetricGrid
                density="compact"
                items={[
                  { label: "提交数", value: selected.commitCount.toLocaleString(), tone: "muted" },
                  { label: "开放 PR", value: selected.openPRs, tone: selected.openPRs > 0 ? "warn" : "ok" },
                  { label: "贡献者", value: selected.contributors, tone: "muted" },
                ]}
              />

              <BpTabs
                tabs={[
                  { id: "files", label: "文件" },
                  { id: "readme", label: "README" },
                ]}
                active={tab}
                onChange={setTab}
              />

              {tab === "files" && (
                <div>
                  <input
                    type="search"
                    placeholder="搜索文件路径…"
                    value={fileQuery}
                    onChange={(e) => setFileQuery(e.target.value)}
                    style={{ width: "100%", marginBottom: "0.5rem" }}
                  />
                  <BpTable
                    columns={["路径", "类型", "大小", "最近提交"]}
                    rows={filteredFiles.map((f) => [
                      <span className="mono">{f.path}</span>,
                      f.type === "dir" ? "📁 目录" : "📄 文件",
                      f.size != null ? `${f.size} B` : "—",
                      f.lastCommit ?? "—",
                    ])}
                  />
                </div>
              )}

              {tab === "readme" && (
                <div className="bp-object-panel">
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>{selected.readme}</pre>
                </div>
              )}
            </div>
          ) : (
            <BpBanner tone="warn">请选择一个仓库</BpBanner>
          )}
        </div>
      </div>

      <BpBanner tone="info">
        对齐 <code>code-repositories.html</code> · 左侧列表 + 右侧详情 ·{" "}
        <Link to="/data/pipelines">管道</Link>
      </BpBanner>
    </S2Chrome>
  );
}
