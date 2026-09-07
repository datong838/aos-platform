import { describe, expect, it } from "vitest";

import {
  parseRuntimeInstallation,
  parseRuntimeOperation,
  serializeRuntimeOperationRequest,
} from "./runtimeInstallations";

const INSTALLATION_ID = "22222222-2222-4222-8222-222222222222";
const OPERATION_ID = "33333333-3333-4333-8333-333333333333";
const GENERATION = "44444444-4444-4444-8444-444444444444";

const operation = {
  operationId: OPERATION_ID,
  installationId: INSTALLATION_ID,
  kind: "enable",
  phase: "accepted",
  status: "accepted",
  revision: 1,
  requestedBy: "operator@example.test",
  approvedBy: null,
  expectedInstallationEtag: 5,
  expectedBindingRevision: 2,
  deadline: "2026-09-07T10:05:00Z",
  failureCode: null,
  createdAt: "2026-09-07T10:00:00Z",
  events: [{ sequence: 1, type: "accepted", payloadHash: "sha256:" + "a".repeat(64), occurredAt: "2026-09-07T10:00:00Z" }],
} as const;

describe("runtime installation canonical contract", () => {
  it("parses installation, binding, operation and event without guessing fields", () => {
    const result = parseRuntimeInstallation({
      installationId: INSTALLATION_ID,
      installationRevision: 5,
      installationEtag: 5,
      installationState: "active",
      effectiveState: "disabled",
      binding: {
        generation: GENERATION,
        installationRevision: 5,
        profileRef: "runtime-profile/python-v1",
        configRef: null,
        executionEpoch: 2,
        desiredState: "disabled",
        observedState: "disabled",
        enabled: false,
        operationFence: false,
        revision: 2,
      },
      currentOperation: operation,
      ui: {
        title: "隔离测试扩展",
        signedResourceUrl: `http://127.0.0.1:18182/extensions/test/index.html?contentHash=${encodeURIComponent(`sha256:${"a".repeat(64)}`)}`,
        resourceHash: `sha256:${"a".repeat(64)}`,
        initialRoute: "/test",
        routeClaims: ["/test"],
        readOperationClaims: ["test.read"],
        commandOperationClaims: [],
      },
      allowedActions: ["configure", "enable"],
      reasons: ["运行实例已停用。"],
    });
    expect(result.binding?.generation).toBe(GENERATION);
    expect(result.currentOperation?.events[0]?.type).toBe("accepted");
    expect(result.allowedActions).toEqual(["configure", "enable"]);
    expect(result.ui?.readOperationClaims).toEqual(["test.read"]);
  });

  it("rejects extra fields and invalid action values", () => {
    expect(() => parseRuntimeOperation({ ...operation, secret: "must-not-pass" })).toThrow("keys mismatch");
    expect(() => parseRuntimeInstallation({
      installationId: INSTALLATION_ID,
      installationRevision: 5,
      installationEtag: 5,
      installationState: "active",
      effectiveState: "disabled",
      binding: null,
      currentOperation: null,
      ui: null,
      allowedActions: ["delete"],
      reasons: [],
    })).toThrow("allowedAction is invalid");
  });

  it("rejects duplicate UI claims and non-canonical resource hashes", () => {
    const base = {
      installationId: INSTALLATION_ID,
      installationRevision: 5,
      installationEtag: 5,
      installationState: "active",
      effectiveState: "ready",
      binding: null,
      currentOperation: null,
      allowedActions: ["disable"],
      reasons: [],
    };
    const ui = {
      title: "隔离测试扩展",
      signedResourceUrl: `http://127.0.0.1:18182/extensions/test/index.html?contentHash=${encodeURIComponent(`sha256:${"a".repeat(64)}`)}`,
      resourceHash: `sha256:${"a".repeat(64)}`,
      initialRoute: "/test",
      routeClaims: ["/test"],
      readOperationClaims: ["test.read"],
      commandOperationClaims: [],
    };
    expect(() => parseRuntimeInstallation({ ...base, ui: { ...ui, readOperationClaims: ["test.read", "test.read"] } })).toThrow("must be unique");
    expect(() => parseRuntimeInstallation({ ...base, ui: { ...ui, resourceHash: "sha256:ABC" } })).toThrow("canonical sha256");
  });

  it("serializes preparation without target and control with an exact target", () => {
    expect(serializeRuntimeOperationRequest({ kind: "runtime-apply" })).toEqual({ kind: "runtime-apply" });
    expect(serializeRuntimeOperationRequest({ kind: "disable", target: { generation: GENERATION, bindingRevision: 2 } })).toEqual({
      kind: "disable",
      target: { generation: GENERATION, bindingRevision: 2 },
    });
  });

  it("fails closed when target presence does not match the action", () => {
    expect(() => serializeRuntimeOperationRequest({ kind: "enable" })).toThrow("requires an exact target");
    expect(() => serializeRuntimeOperationRequest({ kind: "runtime-verify", target: {} })).toThrow("does not accept a target");
  });
});
