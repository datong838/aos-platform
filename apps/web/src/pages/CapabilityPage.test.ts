import { beforeEach, describe, expect, it } from "vitest";
import {
  cfgTypeFromCard,
  defaultConfigFor,
  formToConfig,
  formatSaveMsg,
  formatTestMsg,
  loadLocalConfig,
  mergeLiveItem,
  normalizeListItems,
  pathLabel,
  resolveEndpoint,
  saveLocalConfig,
  simulateConnectivity,
} from "./CapabilityPage";

describe("CapabilityPage · W4-B5 pathLabel", () => {
  it("live / demo", () => {
    expect(pathLabel(false)).toBe("真 API");
    expect(pathLabel(true)).toBe("演示路径");
  });
});

describe("CapabilityPage · defaultConfig / formToConfig", () => {
  it("job 配置含 endpoint 与 concurrency", () => {
    const f = defaultConfigFor("job");
    const c = formToConfig("job", f);
    expect(c.kind).toBe("job");
    expect(c.endpoint).toContain("video");
    expect(c.concurrency).toBe(4);
  });

  it("session 用 gateway 作 endpoint", () => {
    const f = defaultConfigFor("session");
    expect(resolveEndpoint("session", f)).toBe(f.gateway);
    expect(formToConfig("session", f).endpoint).toBe(f.gateway);
  });

  it("cfgTypeFromCard", () => {
    expect(
      cfgTypeFromCard({
        id: "video-job",
        title: "短视频生成",
        kindLabel: "C1 Job · GPU",
        desc: "",
        status: "ready",
      }),
    ).toBe("job");
    expect(
      cfgTypeFromCard({
        id: "avatar-commerce",
        title: "电商",
        kindLabel: "C2 Session · AV",
        desc: "",
        status: "session",
      }),
    ).toBe("session");
  });
});

describe("CapabilityPage · mergeLiveItem / normalize", () => {
  it("合并 live config", () => {
    const base = defaultConfigFor("job");
    const merged = mergeLiveItem(base, {
      id: "video-job",
      config: { endpoint: "https://live/v1", concurrency: 9 },
    });
    expect(merged.endpoint).toBe("https://live/v1");
    expect(merged.concurrency).toBe("9");
  });

  it("normalizeListItems 兼容 wave_ext 与 phase3", () => {
    const items = normalizeListItems({
      items: [
        { id: "a", kind: "job", endpoint: "mock://a" },
        { id: "b", name: "B", category: "ai", config: { endpoint: "https://b" }, enabled: true },
        { noId: true },
      ],
    });
    expect(items).toHaveLength(2);
    expect(items[0].endpoint).toBe("mock://a");
    expect(items[1].name).toBe("B");
  });
});

describe("CapabilityPage · localStorage 演示路径", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("save/load", () => {
    const f = defaultConfigFor("http");
    f.baseUrl = "https://saved.example";
    saveLocalConfig("http-adapter", f);
    expect(loadLocalConfig("http-adapter")?.baseUrl).toBe("https://saved.example");
    expect(loadLocalConfig("missing")).toBeNull();
  });
});

describe("CapabilityPage · connectivity / messages", () => {
  it("simulateConnectivity", () => {
    const ok = simulateConnectivity("video-job", "https://x");
    expect(ok.ok).toBe(true);
    expect(ok.status).toBe("healthy");
    const bad = simulateConnectivity("x", "");
    expect(bad.ok).toBe(false);
  });

  it("formatSaveMsg / formatTestMsg", () => {
    expect(formatSaveMsg(false, "video-job")).toContain("已保存并启用");
    expect(formatSaveMsg(true, "video-job", "404")).toContain("演示路径");
    expect(formatTestMsg(false, true, 12)).toContain("连通正常");
    expect(formatTestMsg(true, true, 12)).toContain("演示路径");
  });
});
