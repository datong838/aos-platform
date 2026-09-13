import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, expect, vi } from "vitest";
import { setAccessToken } from "../../../api/tenant";
import { assetControlClient } from "../../../api/assetControl/client";
import type { RuntimeConfigurationCatalog, RuntimeInstallation } from "../../../api/assetControl/types";
import { useRuntimeConfigurations, type ConfigurationReadState } from "./readHooks";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const runtime: RuntimeInstallation = { installationId: "22222222-2222-4222-8222-222222222222", installationRevision: 1, installationEtag: 1,
  installationState: "active", effectiveState: "configuration_required", currentOperation: null, ui: null, allowedActions: ["configure"], reasons: [],
  binding: { generation: "44444444-4444-4444-8444-444444444444", installationRevision: 1, profileRef: "python", configRef: null, executionEpoch: 1, desiredState: "disabled", observedState: "ready", enabled: false, operationFence: true, revision: 1 } };
const catalog: RuntimeConfigurationCatalog = { installationId: runtime.installationId, installationRevision: 1, installationEtag: 1,
  generation: runtime.binding!.generation, bindingRevision: 1, items: [], hasMore: false };

describe("configuration identity isolation", () => {
  it("drops old identity responses and hides old data when generation changes", async () => {
    const pending: ((value: RuntimeConfigurationCatalog) => void)[] = [];
    const mock = vi.spyOn(assetControlClient, "getRuntimeConfigurations").mockImplementation(() => new Promise(resolve => pending.push(resolve)));
    const node = document.createElement("div"); const root = createRoot(node);
    let latest!: ConfigurationReadState;
    function Harness({ value }: { value: RuntimeInstallation }) { latest = useRuntimeConfigurations(value); return null; }
    try {
      setAccessToken("configuration-test-a");
      await act(async () => root.render(<Harness value={runtime} />));
      expect(pending).toHaveLength(1);
      await act(async () => setAccessToken("configuration-test-b"));
      expect(pending).toHaveLength(2);
      await act(async () => pending[0]!(catalog));
      expect(latest.data).toBeNull();
      await act(async () => pending[1]!(catalog));
      expect(latest.data).toEqual(catalog); expect(latest.isCurrent()).toBe(true);
      const next = { ...runtime, binding: { ...runtime.binding!, revision: 2 } };
      await act(async () => root.render(<Harness value={next} />));
      expect(latest.data).toBeNull(); expect(latest.isCurrent()).toBe(false);
    } finally {
      await act(async () => root.unmount()); mock.mockRestore(); setAccessToken(null);
    }
  });
});
