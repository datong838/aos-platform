import { describe, expect, it } from "vitest";
import {
  PROVIDER_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  formatTimestamp,
  filterRepos,
  type Repository,
} from "./CodeRepositoriesPage";

const MOCK_REPOS: Repository[] = [
  { id: "r1", name: "aos-platform", url: "https://github.com/co/aos-platform", branch: "main", provider: "github", status: "synced", lastSyncedAt: new Date(Date.now() - 5 * 60000).toISOString(), commitCount: 1000, openPRs: 3, contributors: 8, readme: "# AOS", files: [] },
  { id: "r2", name: "data-pipes", url: "https://gitlab.com/co/data-pipes", branch: "dev", provider: "gitlab", status: "syncing", lastSyncedAt: new Date(Date.now() - 60000).toISOString(), commitCount: 500, openPRs: 1, contributors: 4, readme: "# Pipes", files: [] },
  { id: "r3", name: "ml-models", url: "https://bitbucket.org/co/ml-models", branch: "main", provider: "bitbucket", status: "error", lastSyncedAt: new Date(Date.now() - 300 * 60000).toISOString(), commitCount: 200, openPRs: 0, contributors: 2, readme: "# ML", files: [] },
  { id: "r4", name: "infra", url: "ssh://git@internal/infra", branch: "master", provider: "ssh", status: "disconnected", lastSyncedAt: "", commitCount: 50, openPRs: 0, contributors: 1, readme: "", files: [] },
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
  it("no match", () => {
    expect(filterRepos(MOCK_REPOS, "xyz", "all", "all")).toHaveLength(0);
  });
});
