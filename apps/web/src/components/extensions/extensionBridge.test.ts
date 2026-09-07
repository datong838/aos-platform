import { describe, expect, it, vi } from "vitest";

import { ExtensionBridge, parseExtensionHandshake, parseExtensionRequest, routeIsClaimed, type MessagePortLike } from "./extensionBridge";

const identity = {
  installationId: "11111111-1111-4111-8111-111111111111",
  generation: "22222222-2222-4222-8222-222222222222",
  executionEpoch: 3,
};
const operationClaims = { read: ["read.orders"], command: ["command.content.create"] };

describe("extensionBridge contract", () => {
  it("只接受字段精确且代次完整的一次性握手", () => {
    expect(parseExtensionHandshake({ version: 1, type: "aos:hello", nonce: "n", ...identity })).not.toBeNull();
    expect(parseExtensionHandshake({ version: 1, type: "aos:hello", nonce: "n", ...identity, origin: "null" })).toBeNull();
    expect(parseExtensionHandshake({ version: 1, type: "aos:hello", nonce: "n", ...identity, generation: "2" })).toBeNull();
  });

  it("拒绝未知动作、额外字段和不完整 ArtifactRef", () => {
    const common = { version: 1, sequence: 1, requestId: "request-1", ...identity };
    expect(parseExtensionRequest({ ...common, type: "navigate", route: "/workshop/task" })).not.toBeNull();
    expect(parseExtensionRequest({ ...common, type: "eval", input: {} })).toBeNull();
    expect(parseExtensionRequest({ ...common, type: "focusRequest", token: "secret" })).toBeNull();
    expect(parseExtensionRequest({ ...common, type: "artifactDownload", artifactRef: { resourceType: "Artifact", resourceId: "a", revision: "1" } })).toBeNull();
  });

  it("导航只允许精确声明或显式子路径声明", () => {
    expect(routeIsClaimed("/workshop", ["/workshop"])).toBe(true);
    expect(routeIsClaimed("/workshop/task/1", ["/workshop/*"])).toBe(true);
    expect(routeIsClaimed("/admin", ["/workshop/*"])).toBe(false);
    expect(routeIsClaimed("/workshop/../admin", ["/workshop/*"])).toBe(false);
    expect(routeIsClaimed("/workshop/%2e%2e/admin", ["/workshop/*"])).toBe(false);
  });

  it("只消费精确 frameWindow 的 nonce，越界导航立即销毁旧 port", () => {
    const frameWindow = { postMessage: vi.fn() } as unknown as Window;
    const port: MessagePortLike = { onmessage: null, postMessage: vi.fn(), close: vi.fn() };
    const closed = vi.fn();
    const bridge = new ExtensionBridge(frameWindow, "nonce-1", identity, ["/workshop/*"], operationClaims, {}, closed, () => ({ port1: port, port2: {} as Transferable }));
    bridge.start(60_000);
    window.dispatchEvent(new MessageEvent("message", { data: { version: 1, type: "aos:hello", nonce: "nonce-1", ...identity }, source: window }));
    expect(frameWindow.postMessage).not.toHaveBeenCalled();
    window.dispatchEvent(new MessageEvent("message", { data: { version: 1, type: "aos:hello", nonce: "nonce-1", ...identity }, source: frameWindow }));
    expect(frameWindow.postMessage).toHaveBeenCalledTimes(1);
    port.onmessage?.(new MessageEvent("message", { data: { version: 1, type: "navigate", sequence: 1, requestId: "request-1", ...identity, route: "/admin" } }));
    expect(closed).toHaveBeenCalledWith("扩展导航超出授权范围");
    expect(port.close).toHaveBeenCalledTimes(1);
    expect(port.onmessage).toBeNull();
  });

  it("拒绝重复序号并把扩展高度限制在宿主边界内", () => {
    const frameWindow = { postMessage: vi.fn() } as unknown as Window;
    const port: MessagePortLike = { onmessage: null, postMessage: vi.fn(), close: vi.fn() };
    const resized = vi.fn();
    const closed = vi.fn();
    const bridge = new ExtensionBridge(frameWindow, "nonce-2", identity, ["/workshop/*"], operationClaims, { onResize: resized }, closed, () => ({ port1: port, port2: {} as Transferable }));
    bridge.start(60_000);
    window.dispatchEvent(new MessageEvent("message", { data: { version: 1, type: "aos:hello", nonce: "nonce-2", ...identity }, source: frameWindow }));
    port.onmessage?.(new MessageEvent("message", { data: { version: 1, type: "resize", sequence: 1, requestId: "request-1", ...identity, height: 9000 } }));
    expect(resized).toHaveBeenCalledWith(2400);
    port.onmessage?.(new MessageEvent("message", { data: { version: 1, type: "focusRequest", sequence: 1, requestId: "request-2", ...identity } }));
    expect(closed).toHaveBeenCalledWith("扩展消息校验失败");
    expect(port.onmessage).toBeNull();
  });

  it("read 与 command 只转发签名声明的精确 operationId", () => {
    const frameWindow = { postMessage: vi.fn() } as unknown as Window;
    const port: MessagePortLike = { onmessage: null, postMessage: vi.fn(), close: vi.fn() };
    const onRead = vi.fn();
    const closed = vi.fn();
    const bridge = new ExtensionBridge(frameWindow, "nonce-3", identity, ["/workshop/*"], operationClaims, { onRead }, closed, () => ({ port1: port, port2: {} as Transferable }));
    bridge.start(60_000);
    window.dispatchEvent(new MessageEvent("message", { data: { version: 1, type: "aos:hello", nonce: "nonce-3", ...identity }, source: frameWindow }));
    port.onmessage?.(new MessageEvent("message", { data: { version: 1, type: "read", sequence: 1, requestId: "request-1", ...identity, operationId: "read.secret", input: {} } }));
    expect(onRead).not.toHaveBeenCalled();
    expect(closed).toHaveBeenCalledWith("扩展操作超出授权范围");
  });

  it("声明内请求缺少宿主处理器时返回失败而不冒充成功", async () => {
    const frameWindow = { postMessage: vi.fn() } as unknown as Window;
    const port: MessagePortLike = { onmessage: null, postMessage: vi.fn(), close: vi.fn() };
    const bridge = new ExtensionBridge(frameWindow, "nonce-4", identity, ["/workshop/*"], operationClaims, {}, vi.fn(), () => ({ port1: port, port2: {} as Transferable }));
    bridge.start(60_000);
    window.dispatchEvent(new MessageEvent("message", { data: { version: 1, type: "aos:hello", nonce: "nonce-4", ...identity }, source: frameWindow }));
    port.onmessage?.(new MessageEvent("message", { data: { version: 1, type: "navigate", sequence: 1, requestId: "request-1", ...identity, route: "/workshop/task" } }));
    await vi.waitFor(() => expect(port.postMessage).toHaveBeenCalledWith({ version: 1, type: "response", requestId: "request-1", ok: false, error: "请求未完成，请在平台中查看详情" }));
  });
});
