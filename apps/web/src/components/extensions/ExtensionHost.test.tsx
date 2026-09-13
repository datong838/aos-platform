import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ExtensionHost, type ExtensionHostSpec } from "./ExtensionHost";
import { parseExtensionHandshake } from "./extensionBridge";

const spec: ExtensionHostSpec = {
  installationId: "11111111-1111-4111-8111-111111111111",
  generation: "22222222-2222-4222-8222-222222222222",
  executionEpoch: 3,
  title: "隔离测试扩展",
  initialRoute: "/workshop",
  routeClaims: ["/workshop/*"],
  readOperationClaims: ["read.orders"],
  commandOperationClaims: ["command.content.create"],
  signedResourceUrl: `http://127.0.0.1:18182/extensions/test/index.html?contentHash=${encodeURIComponent(`sha256:${"a".repeat(64)}`)}`,
  resourceHash: `sha256:${"a".repeat(64)}`,
};

describe("ExtensionHost", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("只以 allow-scripts 沙箱加载签名资源并保留父级导航", () => {
    act(() => root.render(<ExtensionHost spec={spec} effectiveState="ready" />));
    const iframe = host.querySelector("iframe") as HTMLIFrameElement;
    expect(iframe.getAttribute("sandbox")).toBe("allow-scripts");
    expect(iframe.src).toContain("#aosNonce=");
    expect(host.textContent).toContain("运行代次 22222222-2222-4222-8222-222222222222");
  });

  it("未 ready、摘要错误或非安全远端资源时不加载领域脚本", () => {
    act(() => root.render(<ExtensionHost spec={spec} effectiveState="disabled" unavailableReason="扩展已停用" />));
    expect(host.querySelector("iframe")).toBeNull();
    expect(host.textContent).toContain("扩展已停用");
    act(() => root.render(<ExtensionHost spec={{ ...spec, resourceHash: "sha256:bad" }} effectiveState="ready" />));
    expect(host.querySelector("iframe")).toBeNull();
    act(() => root.render(<ExtensionHost spec={{ ...spec, signedResourceUrl: "http://example.com/index.html" }} effectiveState="ready" />));
    expect(host.querySelector("iframe")).toBeNull();
    act(() => root.render(<ExtensionHost spec={{ ...spec, signedResourceUrl: "http://127.0.0.1:18182/extensions/test/index.html?contentHash=sha256%3Abad" }} effectiveState="ready" />));
    expect(host.querySelector("iframe")).toBeNull();
    act(() => root.render(<ExtensionHost spec={{ ...spec, signedResourceUrl: `${spec.signedResourceUrl}&contentHash=${encodeURIComponent(spec.resourceHash)}` }} effectiveState="ready" />));
    expect(host.querySelector("iframe")).toBeNull();
  });

  it("签名子页面仅凭公开启动片段可组成合法握手，资源请求不携带身份", () => {
    act(() => root.render(<ExtensionHost spec={{ ...spec, signedResourceUrl: `${spec.signedResourceUrl}#obsolete=discard` }} effectiveState="ready" />));
    const url = new URL((host.querySelector("iframe") as HTMLIFrameElement).src);
    const bootstrap = new URLSearchParams(url.hash.slice(1));
    expect([...bootstrap.keys()].sort()).toEqual(["aosNonce", "executionEpoch", "generation", "initialRoute", "installationId"]);
    expect(url.search).toBe(new URL(spec.signedResourceUrl).search);
    expect(bootstrap.get("initialRoute")).toBe(spec.initialRoute);
    expect(parseExtensionHandshake({
      version: 1, type: "aos:hello", nonce: bootstrap.get("aosNonce"),
      installationId: bootstrap.get("installationId"), generation: bootstrap.get("generation"),
      executionEpoch: Number(bootstrap.get("executionEpoch")),
    })).toMatchObject({ installationId: spec.installationId, generation: spec.generation, executionEpoch: spec.executionEpoch });
  });

  it("运行身份更新后新页面只收到新代次且nonce轮换", () => {
    act(() => root.render(<ExtensionHost spec={spec} effectiveState="ready" />));
    const oldFrame = host.querySelector("iframe") as HTMLIFrameElement;
    const oldBootstrap = new URLSearchParams(new URL(oldFrame.src).hash.slice(1));
    const next = { ...spec, generation: "33333333-3333-4333-8333-333333333333", executionEpoch: 4 };
    act(() => root.render(<ExtensionHost spec={next} effectiveState="ready" />));
    const newFrame = host.querySelector("iframe") as HTMLIFrameElement;
    const bootstrap = new URLSearchParams(new URL(newFrame.src).hash.slice(1));
    expect(newFrame).not.toBe(oldFrame);
    expect(bootstrap.get("generation")).toBe(next.generation);
    expect(bootstrap.get("executionEpoch")).toBe("4");
    expect(bootstrap.get("aosNonce")).not.toBe(oldBootstrap.get("aosNonce"));
  });

  it("任一安全元数据变化都会废弃旧通道并重建隔离页面", () => {
    act(() => root.render(<ExtensionHost spec={spec} effectiveState="ready" />));
    const firstIframe = host.querySelector("iframe") as HTMLIFrameElement;
    const firstSrc = firstIframe.src;

    act(() => root.render(<ExtensionHost spec={{ ...spec, initialRoute: "/workshop/tasks" }} effectiveState="ready" />));
    const routeChangedIframe = host.querySelector("iframe") as HTMLIFrameElement;
    expect(routeChangedIframe).not.toBe(firstIframe);
    expect(routeChangedIframe.src).not.toBe(firstSrc);
    expect(new URLSearchParams(new URL(routeChangedIframe.src).hash.slice(1)).get("initialRoute")).toBe("/workshop/tasks");

    act(() => root.render(<ExtensionHost spec={{ ...spec, readOperationClaims: ["read.orders", "read.products"] }} effectiveState="ready" />));
    const claimsChangedIframe = host.querySelector("iframe") as HTMLIFrameElement;
    expect(claimsChangedIframe).not.toBe(routeChangedIframe);
    expect(claimsChangedIframe.src).not.toBe(routeChangedIframe.src);
  });
});
