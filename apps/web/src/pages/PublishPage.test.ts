// @vitest-environment jsdom

import { createElement } from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("../api/client", () => ({
  apiGet: (path: string) => apiMocks.get(path),
  apiPost: (path: string, body: unknown, headers?: HeadersInit) =>
    apiMocks.post(path, body, headers),
}));

import {
  PublishPage,
  PUBLISH_ENVS,
  assertDeploySucceeded,
  assertIdempotentReplay,
  assertPublishAccepted,
  envStepIndex,
  stepState,
  pickLatestByEnv,
  formatPublishResult,
  type DeploymentItem,
} from "./PublishPage";

async function flushEffects() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("PublishPage · PUBLISH_ENVS", () => {
  it("四环境顺序：开发→测试→预发布→生产", () => {
    expect(PUBLISH_ENVS.map((e) => e.id)).toEqual(["dev", "test", "staging", "prod"]);
    expect(PUBLISH_ENVS.map((e) => e.label)).toEqual(["开发", "测试", "预发布", "生产"]);
  });
});

describe("PublishPage · stepState", () => {
  it("current 之前为 done", () => {
    expect(stepState(0, "staging")).toBe("done");
    expect(stepState(1, "staging")).toBe("done");
  });

  it("当前环境为 current", () => {
    expect(stepState(2, "staging")).toBe("current");
    expect(envStepIndex("staging")).toBe(2);
  });

  it("之后为 pending", () => {
    expect(stepState(3, "staging")).toBe("pending");
  });
});

describe("PublishPage · pickLatestByEnv", () => {
  it("按 environment 取首条（列表已按时间倒序）", () => {
    const items: DeploymentItem[] = [
      { id: "d1", environment: "dev", status: "success", version: "1.0.1" },
      { id: "d0", environment: "dev", status: "success", version: "1.0.0" },
      { id: "s1", environment: "staging", status: "success", version: "1.0.0" },
    ];
    const map = pickLatestByEnv(items);
    expect(map.dev?.id).toBe("d1");
    expect(map.staging?.version).toBe("1.0.0");
    expect(map.prod).toBeUndefined();
  });
});

describe("PublishPage · formatPublishResult", () => {
  it("成功文案含 id/环境/状态", () => {
    const msg = formatPublishResult({
      ok: true,
      moduleId: "m1",
      env: "staging",
      status: "ACCEPTED",
      idempotent: true,
    });
    expect(msg).toContain("m1");
    expect(msg).toContain("staging");
    expect(msg).toContain("ACCEPTED");
    expect(msg).toContain("幂等");
  });

  it("失败文案", () => {
    expect(formatPublishResult({ ok: false, error: "boom" })).toContain("发布失败");
    expect(formatPublishResult({ ok: false, phase: "deploy", error: "boom" })).toContain(
      "发布已接受，但部署失败",
    );
    expect(formatPublishResult({ ok: false, phase: "idempotency", error: "boom" })).toContain(
      "发布已接受，但幂等校验失败",
    );
  });
});

describe("PublishPage · 真实发布与部署阶段", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path === "/v1/modules") {
        return { items: [{ id: "mod-canvas", name: "Canvas Module", status: "draft" }] };
      }
      if (path.includes("/deployments")) return { items: [] };
      throw new Error(`unexpected GET ${path}`);
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  async function renderPage() {
    await act(async () => {
      root.render(
        createElement(
          MemoryRouter,
          { initialEntries: ["/workshop/publish?moduleId=mod-canvas"] },
          createElement(PublishPage),
        ),
      );
    });
    await flushEffects();
  }

  it("发布、幂等重放与部署均确认后才显示全成功", async () => {
    let publishCalls = 0;
    apiMocks.post.mockImplementation(async (path: string) => {
      if (path.endsWith("/publish")) {
        publishCalls += 1;
        return {
          id: "mod-canvas",
          status: "published",
          publish: { status: "ACCEPTED", channel: "dev" },
          ...(publishCalls === 2 ? { idempotentReplay: true } : {}),
        };
      }
      if (path.endsWith("/deploy")) {
        return {
          ok: true,
          item: { id: "dep-1", environment: "staging", status: "success", version: "1.0.0" },
        };
      }
      throw new Error(`unexpected POST ${path}`);
    });
    await renderPage();

    const button = Array.from(host.querySelectorAll("button")).find((item) =>
      item.textContent?.includes("发布到预发布"),
    );
    await act(async () => button?.click());
    await flushEffects();

    expect(host.textContent).toContain("发布与部署成功");
    expect(host.textContent).toContain("发布：已接受");
    expect(host.textContent).toContain("部署：成功");
    expect(host.textContent).toContain("success · dep-1");
  });

  it("部署失败时保留发布已接受事实，但绝不显示全成功", async () => {
    let publishCalls = 0;
    apiMocks.post.mockImplementation(async (path: string) => {
      if (path.endsWith("/publish")) {
        publishCalls += 1;
        return {
          id: "mod-canvas",
          status: "published",
          publish: { status: "ACCEPTED", channel: "dev" },
          ...(publishCalls === 2 ? { idempotentReplay: true } : {}),
        };
      }
      if (path.endsWith("/deploy")) throw new Error("spoke unavailable");
      throw new Error(`unexpected POST ${path}`);
    });
    await renderPage();

    const button = Array.from(host.querySelectorAll("button")).find((item) =>
      item.textContent?.includes("发布到预发布"),
    );
    expect(button).toBeTruthy();
    await act(async () => button?.click());
    await flushEffects();

    expect(host.textContent).toContain("发布已接受，但部署失败");
    expect(host.textContent).toContain("发布：已接受");
    expect(host.textContent).toContain("部署：失败");
    expect(host.textContent).not.toContain("发布与部署成功");
  });

  it("幂等重放未被后端确认时 fail-closed，且不调用部署", async () => {
    apiMocks.post.mockImplementation(async (path: string) => {
      if (path.endsWith("/publish")) {
        return {
          id: "mod-canvas",
          status: "published",
          publish: { status: "ACCEPTED", channel: "dev" },
          idempotentReplay: false,
        };
      }
      throw new Error(`unexpected POST ${path}`);
    });
    await renderPage();

    const button = Array.from(host.querySelectorAll("button")).find((item) =>
      item.textContent?.includes("发布到预发布"),
    );
    await act(async () => button?.click());
    await flushEffects();

    expect(host.textContent).toContain("发布已接受，但幂等校验失败");
    expect(host.textContent).toContain("幂等重放校验失败");
    expect(host.textContent).toContain("发布：已接受·幂等失败");
    expect(apiMocks.post.mock.calls.some(([path]) => String(path).endsWith("/deploy"))).toBe(false);
  });

  it("部署历史加载失败时显式显示错误，而不是伪装成尚未部署", async () => {
    apiMocks.get.mockImplementation(async (path: string) => {
      if (path === "/v1/modules") {
        return { items: [{ id: "mod-canvas", name: "Canvas Module", status: "draft" }] };
      }
      if (path.includes("/deployments")) throw new Error("history offline");
      throw new Error(`unexpected GET ${path}`);
    });
    await renderPage();

    expect(host.querySelector('[data-testid="deployment-history-error"]')?.textContent).toContain(
      "部署历史加载失败",
    );
    expect(host.textContent).toContain("history offline");
  });
});

describe("PublishPage · 响应契约守卫", () => {
  it("拒绝未确认或 Module 不匹配的发布响应", () => {
    expect(() =>
      assertPublishAccepted(
        { id: "m1", status: "published", publish: { status: "QUEUED" } },
        "m1",
      ),
    ).toThrow("发布接口未返回 ACCEPTED 状态");
    expect(() =>
      assertPublishAccepted(
        { id: "m2", status: "published", publish: { status: "ACCEPTED" } },
        "m1",
      ),
    ).toThrow("发布响应 Module 不匹配");
  });

  it("拒绝未确认的幂等响应", () => {
    expect(() => assertIdempotentReplay({ id: "m1", status: "published" })).toThrow();
  });

  it("拒绝失败或环境不匹配的部署响应", () => {
    expect(() =>
      assertDeploySucceeded({ ok: true, item: { id: "d1", status: "failed" } }, "staging"),
    ).toThrow("部署接口未返回 success 记录");
    expect(() =>
      assertDeploySucceeded(
        { ok: true, item: { id: "d1", environment: "prod", status: "success" } },
        "staging",
      ),
    ).toThrow("部署响应环境不匹配");
  });
});
