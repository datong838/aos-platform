import { useEffect, useMemo, useRef, useState } from "react";

import { ExtensionBridge, createExtensionNonce, type ExtensionBridgeHandlers, type ExtensionRuntimeIdentity } from "./extensionBridge";
import { ExtensionNavigation } from "./ExtensionNavigation";

export interface ExtensionHostSpec extends ExtensionRuntimeIdentity {
  title: string;
  initialRoute: string;
  routeClaims: readonly string[];
  readOperationClaims: readonly string[];
  commandOperationClaims: readonly string[];
  signedResourceUrl: string;
  resourceHash: `sha256:${string}`;
}

export interface ExtensionHostProps extends ExtensionBridgeHandlers {
  spec: ExtensionHostSpec | null;
  effectiveState: string;
  unavailableReason?: string | null;
}

function resourceUrlWithNonce(resourceUrl: string, resourceHash: string, nonce: string): string | null {
  try {
    const url = new URL(resourceUrl);
    if (url.protocol !== "https:" && !(url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname))) return null;
    const contentHashes = url.searchParams.getAll("contentHash");
    if (contentHashes.length !== 1 || contentHashes[0] !== resourceHash) return null;
    url.hash = `aosNonce=${encodeURIComponent(nonce)}`;
    return url.toString();
  } catch {
    return null;
  }
}

export function ExtensionHost({ spec, effectiveState, unavailableReason, ...handlers }: ExtensionHostProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;
  const [height, setHeight] = useState(720);
  const [closedReason, setClosedReason] = useState<string | null>(null);
  const securityFingerprint = spec ? JSON.stringify([
    spec.installationId, spec.generation, spec.executionEpoch, spec.signedResourceUrl,
    spec.resourceHash, spec.initialRoute, spec.routeClaims, spec.readOperationClaims, spec.commandOperationClaims,
  ]) : "none";
  const bridgeSpec = useMemo(() => spec, [securityFingerprint]);
  const nonce = useMemo(() => createExtensionNonce(), [securityFingerprint]);
  const src = spec ? resourceUrlWithNonce(spec.signedResourceUrl, spec.resourceHash, nonce) : null;
  const ready = spec !== null && effectiveState === "ready" && src !== null && /^sha256:[a-f0-9]{64}$/.test(spec.resourceHash);

  useEffect(() => {
    setClosedReason(null);
    if (!ready || !bridgeSpec || !iframeRef.current?.contentWindow) return;
    const bridge = new ExtensionBridge(
      iframeRef.current.contentWindow,
      nonce,
      bridgeSpec,
      bridgeSpec.routeClaims,
      { read: bridgeSpec.readOperationClaims, command: bridgeSpec.commandOperationClaims },
      {
        onRouteChanged: (route) => {
          if (!handlersRef.current.onRouteChanged) throw new Error("routeChanged handler unavailable");
          return handlersRef.current.onRouteChanged(route);
        },
        onNavigate: (route) => {
          if (!handlersRef.current.onNavigate) throw new Error("navigate handler unavailable");
          return handlersRef.current.onNavigate(route);
        },
        onResize: (nextHeight) => { setHeight(nextHeight); handlersRef.current.onResize?.(nextHeight); },
        onFocusRequest: () => {
          if (!handlersRef.current.onFocusRequest) throw new Error("focusRequest handler unavailable");
          return handlersRef.current.onFocusRequest();
        },
        onRead: (operationId, input) => {
          if (!handlersRef.current.onRead) throw new Error("read handler unavailable");
          return handlersRef.current.onRead(operationId, input);
        },
        onCommand: (operationId, input) => {
          if (!handlersRef.current.onCommand) throw new Error("command handler unavailable");
          return handlersRef.current.onCommand(operationId, input);
        },
        onArtifactDownload: (artifactRef) => {
          if (!handlersRef.current.onArtifactDownload) throw new Error("artifactDownload handler unavailable");
          return handlersRef.current.onArtifactDownload(artifactRef);
        },
      },
      setClosedReason,
    );
    bridge.start();
    return () => bridge.close("扩展页面已离开，旧通道已失效", false);
  }, [bridgeSpec, nonce, ready]);

  if (!ready || !spec || !src) {
    return <section aria-label="扩展运行区域" role="status" style={{ padding: 24 }}>{unavailableReason ?? "该扩展当前不能安全加载，请先在资产控制页完成运行准备。"}</section>;
  }
  return (
    <section aria-label={`${spec.title}扩展运行区域`} style={{ background: "#fff", minHeight: 480 }}>
      <ExtensionNavigation title={spec.title} route={spec.initialRoute} identity={spec} />
      {closedReason ? <div role="alert" style={{ background: "#fff7e6", color: "#9a6700", padding: "10px 16px" }}>{closedReason}</div> : null}
      <iframe
        key={`${securityFingerprint}:${nonce}`}
        ref={iframeRef}
        src={src}
        sandbox="allow-scripts"
        title={spec.title}
        style={{ border: 0, display: "block", height, minHeight: 480, width: "100%" }}
      />
    </section>
  );
}
