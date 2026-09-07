export const EXTENSION_PROTOCOL_VERSION = 1 as const;

export interface ExtensionRuntimeIdentity {
  installationId: string;
  generation: string;
  executionEpoch: number;
}

export type ExtensionRequest =
  | { version: 1; type: "routeChanged"; sequence: number; requestId: string; installationId: string; generation: string; executionEpoch: number; route: string }
  | { version: 1; type: "navigate"; sequence: number; requestId: string; installationId: string; generation: string; executionEpoch: number; route: string }
  | { version: 1; type: "resize"; sequence: number; requestId: string; installationId: string; generation: string; executionEpoch: number; height: number }
  | { version: 1; type: "focusRequest"; sequence: number; requestId: string; installationId: string; generation: string; executionEpoch: number }
  | { version: 1; type: "read" | "command"; sequence: number; requestId: string; installationId: string; generation: string; executionEpoch: number; operationId: string; input: unknown }
  | { version: 1; type: "artifactDownload"; sequence: number; requestId: string; installationId: string; generation: string; executionEpoch: number; artifactRef: { resourceType: string; resourceId: string; revision: string; authority: string } };

export interface ExtensionHandshake {
  version: 1;
  type: "aos:hello";
  nonce: string;
  installationId: string;
  generation: string;
  executionEpoch: number;
}

export interface ExtensionBridgeHandlers {
  onRouteChanged?: (route: string) => void;
  onNavigate?: (route: string) => void;
  onResize?: (height: number) => void;
  onFocusRequest?: () => void;
  onRead?: (operationId: string, input: unknown) => unknown | Promise<unknown>;
  onCommand?: (operationId: string, input: unknown) => unknown | Promise<unknown>;
  onArtifactDownload?: (artifactRef: ExtensionArtifactRef) => unknown | Promise<unknown>;
}

export interface ExtensionArtifactRef {
  resourceType: string;
  resourceId: string;
  revision: string;
  authority: string;
}

export interface MessagePortLike {
  onmessage: ((event: MessageEvent) => void) | null;
  postMessage(message: unknown): void;
  start?(): void;
  close(): void;
}

interface ChannelLike {
  port1: MessagePortLike;
  port2: Transferable;
}

const COMMON_KEYS = ["version", "type", "sequence", "requestId", "installationId", "generation", "executionEpoch"];
const ACTION_KEYS: Record<ExtensionRequest["type"], readonly string[]> = {
  routeChanged: ["route"],
  navigate: ["route"],
  resize: ["height"],
  focusRequest: [],
  read: ["operationId", "input"],
  command: ["operationId", "input"],
  artifactDownload: ["artifactRef"],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function canonicalUuid(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
}

function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

export function parseExtensionHandshake(value: unknown): ExtensionHandshake | null {
  if (!isRecord(value) || !exactKeys(value, ["version", "type", "nonce", "installationId", "generation", "executionEpoch"])) return null;
  if (value.version !== 1 || value.type !== "aos:hello" || !nonEmpty(value.nonce) || !canonicalUuid(value.installationId)) return null;
  if (!canonicalUuid(value.generation) || !positiveInteger(value.executionEpoch)) return null;
  return value as unknown as ExtensionHandshake;
}

export function parseExtensionRequest(value: unknown): ExtensionRequest | null {
  if (!isRecord(value) || typeof value.type !== "string" || !(value.type in ACTION_KEYS)) return null;
  const type = value.type as ExtensionRequest["type"];
  if (!exactKeys(value, [...COMMON_KEYS, ...ACTION_KEYS[type]])) return null;
  if (value.version !== 1 || !positiveInteger(value.sequence) || !nonEmpty(value.requestId) || !canonicalUuid(value.installationId)) return null;
  if (!canonicalUuid(value.generation) || !positiveInteger(value.executionEpoch)) return null;
  if ((type === "routeChanged" || type === "navigate") && (!nonEmpty(value.route) || canonicalRoute(value.route) === null)) return null;
  if (type === "resize" && (typeof value.height !== "number" || !Number.isFinite(value.height))) return null;
  if ((type === "read" || type === "command") && !nonEmpty(value.operationId)) return null;
  if (type === "artifactDownload") {
    const ref = value.artifactRef;
    if (!isRecord(ref) || !exactKeys(ref, ["resourceType", "resourceId", "revision", "authority"]) || !Object.values(ref).every(nonEmpty)) return null;
  }
  return value as unknown as ExtensionRequest;
}

function canonicalRoute(value: string): string | null {
  if (!value.startsWith("/") || value.includes("\\") || value.includes("%") || value.includes("?") || value.includes("#") || value.includes("//")) return null;
  if (value === "/") return value;
  const segments = value.slice(1).split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) return null;
  return value;
}

export function routeIsClaimed(route: string, claims: readonly string[]): boolean {
  const checkedRoute = canonicalRoute(route);
  if (checkedRoute === null) return false;
  return claims.some((claim) => {
    if (claim.endsWith("/*")) {
      const base = canonicalRoute(claim.slice(0, -2));
      return base !== null && checkedRoute.startsWith(`${base}/`);
    }
    return canonicalRoute(claim) === checkedRoute;
  });
}

export function createExtensionNonce(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

export class ExtensionBridge {
  private port: MessagePortLike | null = null;
  private lastSequence = 0;
  private consumed = false;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly frameWindow: Window,
    private readonly nonce: string,
    private readonly identity: ExtensionRuntimeIdentity,
    private readonly routeClaims: readonly string[],
    private readonly operationClaims: Readonly<{ read: readonly string[]; command: readonly string[] }>,
    private readonly handlers: ExtensionBridgeHandlers,
    private readonly onClosed: (reason: string) => void,
    private readonly channelFactory: () => ChannelLike = () => new MessageChannel() as unknown as ChannelLike,
  ) {}

  start(timeoutMs = 10_000): void {
    window.addEventListener("message", this.onWindowMessage);
    this.timer = setTimeout(() => this.close("扩展握手超时"), timeoutMs);
  }

  close(reason = "扩展通道已关闭", notify = true): void {
    window.removeEventListener("message", this.onWindowMessage);
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    if (this.port) this.port.onmessage = null;
    this.port?.close();
    this.port = null;
    if (notify) this.onClosed(reason);
  }

  private identityMatches(value: ExtensionRuntimeIdentity): boolean {
    return value.installationId === this.identity.installationId && value.generation === this.identity.generation && value.executionEpoch === this.identity.executionEpoch;
  }

  private onWindowMessage = (event: MessageEvent): void => {
    if (event.source !== this.frameWindow || this.consumed) return;
    const hello = parseExtensionHandshake(event.data);
    if (!hello || hello.nonce !== this.nonce || !this.identityMatches(hello)) {
      this.close("扩展握手校验失败");
      return;
    }
    this.consumed = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    const channel = this.channelFactory();
    this.port = channel.port1;
    this.port.onmessage = this.onPortMessage;
    this.port.start?.();
    this.frameWindow.postMessage({ version: 1, type: "aos:connected", nonce: this.nonce, ...this.identity }, "*", [channel.port2]);
    window.removeEventListener("message", this.onWindowMessage);
  };

  private onPortMessage = (event: MessageEvent): void => {
    const request = parseExtensionRequest(event.data);
    if (!request || !this.identityMatches(request) || request.sequence <= this.lastSequence) {
      this.close("扩展消息校验失败");
      return;
    }
    this.lastSequence = request.sequence;
    if ((request.type === "navigate" || request.type === "routeChanged") && !routeIsClaimed(request.route, this.routeClaims)) {
      this.close("扩展导航超出授权范围");
      return;
    }
    if ((request.type === "read" || request.type === "command") && !this.operationClaims[request.type].includes(request.operationId)) {
      this.close("扩展操作超出授权范围");
      return;
    }
    void this.dispatch(request);
  };

  private async dispatch(request: ExtensionRequest): Promise<void> {
    try {
      let result: unknown = null;
      if (request.type === "routeChanged") result = await this.requiredHandler("routeChanged", this.handlers.onRouteChanged)(request.route);
      if (request.type === "navigate") result = await this.requiredHandler("navigate", this.handlers.onNavigate)(request.route);
      if (request.type === "resize") result = await this.requiredHandler("resize", this.handlers.onResize)(Math.max(320, Math.min(2400, Math.round(request.height))));
      if (request.type === "focusRequest") result = await this.requiredHandler("focusRequest", this.handlers.onFocusRequest)();
      if (request.type === "read") result = await this.requiredHandler("read", this.handlers.onRead)(request.operationId, request.input);
      if (request.type === "command") result = await this.requiredHandler("command", this.handlers.onCommand)(request.operationId, request.input);
      if (request.type === "artifactDownload") result = await this.requiredHandler("artifactDownload", this.handlers.onArtifactDownload)(request.artifactRef);
      this.port?.postMessage({ version: 1, type: "response", requestId: request.requestId, ok: true, result: result ?? null });
    } catch {
      this.port?.postMessage({ version: 1, type: "response", requestId: request.requestId, ok: false, error: "请求未完成，请在平台中查看详情" });
    }
  }

  private requiredHandler<T extends (...args: never[]) => unknown>(type: string, handler: T | undefined): T {
    if (!handler) throw new Error(`${type} handler unavailable`);
    return handler;
  }
}
