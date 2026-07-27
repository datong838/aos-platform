import { describe, expect, it } from "vitest";
import {
  PROVIDER_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  formatTimestamp,
  filterRepos,
  sortRepos,
  filterFiles,
  countByProvider,
  countByStatus,
  validateRepoUrl,
  repoNameFromUrl,
  type Repository,
  type RepoFile,
} from "./CodeRepositoriesPage";

const MOCK_REPOS: Repository[] = [
  { id: "r1", name: "aos-platform", url: "https://github.com/co/aos-platform", branch: "main", provider: "github", status: "synced", lastSyncedAt: new Date(Date.now() - 5 * 60000).toISOString(), commitCount: 1000, openPRs: 3, contributors: 8, readme: "# AOS", files: [] },
  { id: "r2", name: "data-pipes", url: "https://gitlab.com/co/data-pipes", branch: "dev", provider: "gitlab", status: "syncing", lastSyncedAt: new Date(Date.now() - 60000).toISOString(), commitCount: 500, openPRs: 1, contributors: 4, readme: "# Pipes", files: [] },
  { id: "r3", name: "ml-models", url: "https://bitbucket.org/co/ml-models", branch: "main", provider: "bitbucket", status: "error", lastSyncedAt: new Date(Date.now() - 300 * 60000).toISOString(), commitCount: 200, openPRs: 0, contributors: 2, readme: "# ML", files: [] },
  { id: "r4", name: "infra", url: "ssh://git@internal/infra", branch: "master", provider: "ssh", status: "disconnected", lastSyncedAt: "", commitCount: 50, openPRs: 0, contributors: 1, readme: "", files: [] },
];

const MOCK_FILES: RepoFile[] = [
  { path: "src/", type: "dir" },
  { path: "src/main.ts", type: "file", size: 1024, lastCommit: "init" },
  { path: "README.md", type: "file", size: 512 },
];

// ── Labels ────────────────────────────────────────────
describe("CodeRepositoriesPage · PROVIDER_LABEL", () => {
  it("github → GitHub", () => {
    expect(PROVIDER_LABEL.github).toBe("GitHub");
  });
  it("has 5 providers", () => {
    expect(Object.keys(PROVIDER_LABEL)).toHaveLength(5);
  });
});

describe("CodeRepositoriesPage · STATUS_LABEL", () => {
  it("synced → 已同步", () => {
    expect(STATUS_LABEL.synced).toBe("已同步");
  });
  it("error → 错误", () => {
    expect(STATUS_LABEL.error).toBe("错误");
  });
});

describe("CodeRepositoriesPage · STATUS_TONE", () => {
  it("synced → ok", () => {
    expect(STATUS_TONE.synced).toBe("ok");
  });
  it("error → bad", () => {
    expect(STATUS_TONE.error).toBe("bad");
  });
  it("disconnected → muted", () => {
    expect(STATUS_TONE.disconnected).toBe("muted");
  });
});

// ── formatTimestamp ───────────────────────────────────
describe("CodeRepositoriesPage · formatTimestamp", () => {
  it("empty → —", () => {
    expect(formatTimestamp("")).toBe("—");
  });
  it("recent", () => {
    expect(formatTimestamp(new Date().toISOString())).toBe("刚刚");
  });
});

// ── filterRepos ───────────────────────────────────────
describe("CodeRepositoriesPage · filterRepos", () => {
  it("no filter → all", () => {
    expect(filterRepos(MOCK_REPOS, "", "all", "all")).toHaveLength(4);
  });
  it("filter by github", () => {
    expect(filterRepos(MOCK_REPOS, "", "github", "all")).toHaveLength(1);
  });
  it("filter by synced status", () => {
    expect(filterRepos(MOCK_REPOS, "", "all", "synced")).toHaveLength(1);
  });
  it("filter by name query", () => {
    expect(filterRepos(MOCK_REPOS, "aos", "all", "all")).toHaveLength(1);
  });
  it("combined filters", () => {
    expect(filterRepos(MOCK_REPOS, "", "gitlab", "syncing")).toHaveLength(1);
  });
  it("no match", () => {
    expect(filterRepos(MOCK_REPOS, "xyz", "all", "all")).toHaveLength(0);
  });
});

// ── sortRepos ─────────────────────────────────────────
describe("CodeRepositoriesPage · sortRepos", () => {
  it("sort by name asc", () => {
    const sorted = sortRepos(MOCK_REPOS, "name");
    expect(sorted[0].name).toBe("aos-platform");
  });
  it("sort by commits desc", () => {
    const sorted = sortRepos(MOCK_REPOS, "commits");
    expect(sorted[0].commitCount).toBe(1000);
    expect(sorted[3].commitCount).toBe(50);
  });
  it("sort by lastSynced desc", () => {
    const sorted = sortRepos([...MOCK_REPOS], "lastSynced");
    // r4 has empty lastSyncedAt, should be last
    expect(sorted[3].id).toBe("r4");
  });
});

// ── filterFiles ───────────────────────────────────────
describe("CodeRepositoriesPage · filterFiles", () => {
  it("empty query → all", () => {
    expect(filterFiles(MOCK_FILES, "")).toHaveLength(3);
  });
  it("match by path", () => {
    expect(filterFiles(MOCK_FILES, "main")).toHaveLength(1);
  });
  it("no match", () => {
    expect(filterFiles(MOCK_FILES, "xyz")).toHaveLength(0);
  });
});

// ── countByProvider ───────────────────────────────────
describe("CodeRepositoriesPage · countByProvider", () => {
  it("counts each provider", () => {
    const counts = countByProvider(MOCK_REPOS);
    expect(counts.github).toBe(1);
    expect(counts.gitlab).toBe(1);
    expect(counts.bitbucket).toBe(1);
    expect(counts.ssh).toBe(1);
    expect(counts.azuredevops).toBe(0);
  });
});

// ── countByStatus ─────────────────────────────────────
describe("CodeRepositoriesPage · countByStatus", () => {
  it("counts each status", () => {
    const counts = countByStatus(MOCK_REPOS);
    expect(counts.synced).toBe(1);
    expect(counts.syncing).toBe(1);
    expect(counts.error).toBe(1);
    expect(counts.disconnected).toBe(1);
  });
});

// ── validateRepoUrl ───────────────────────────────────
describe("CodeRepositoriesPage · validateRepoUrl", () => {
  it("empty → error", () => {
    expect(validateRepoUrl("")).not.toBeNull();
  });
  it("invalid format → error", () => {
    expect(validateRepoUrl("ftp://example.com")).not.toBeNull();
  });
  it("valid https → null", () => {
    expect(validateRepoUrl("https://github.com/co/repo")).toBeNull();
  });
  it("valid git@ → null", () => {
    expect(validateRepoUrl("git@github.com:co/repo.git")).toBeNull();
  });
  it("valid ssh:// → null", () => {
    expect(validateRepoUrl("ssh://git@host/repo")).toBeNull();
  });
  it("too short → error", () => {
    expect(validateRepoUrl("https:/")).not.toBeNull();
  });
});

// ── repoNameFromUrl ───────────────────────────────────
describe("CodeRepositoriesPage · repoNameFromUrl", () => {
  it("https URL", () => {
    expect(repoNameFromUrl("https://github.com/co/my-repo")).toBe("my-repo");
  });
  it("trailing slash", () => {
    expect(repoNameFromUrl("https://github.com/co/my-repo/")).toBe("my-repo");
  });
  it(".git suffix removed", () => {
    expect(repoNameFromUrl("https://github.com/co/my-repo.git")).toBe("my-repo");
  });
  it("ssh URL", () => {
    expect(repoNameFromUrl("git@github.com:co/my-repo.git")).toBe("my-repo");
  });
});
