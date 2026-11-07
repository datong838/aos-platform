import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { clearAccessToken, setAccessToken, setTenant } from "../../api/tenant";
import { AnalystSelectionProvider, useAnalystSelection, usePublishAnalystSelection, type AnalystSelection } from "./AnalystSelectionContext";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const tenant = { orgId: "org-org", projectId: "dev-project" };
const value: AnalystSelection = { tenant, channelId: "niushop:1", entityId: "store-a", channelLabel: "栖月汇微商城", sourceCutoffAt: null };
const clientA = {}, clientB = {};
function Publisher({ data, client = clientA }: { data: AnalystSelection | null; client?: object }) {
  usePublishAnalystSelection(data, client);
  return null;
}
function Probe() {
  const selection = useAnalystSelection();
  return <output data-testid="selection">{selection ? `${selection.channelId}/${selection.entityId}` : "unknown"}</output>;
}

describe("AnalystSelectionContext readonly lifecycle", () => {
  let container: HTMLDivElement, root: Root;
  beforeEach(() => {
    setTenant(tenant); clearAccessToken();
    container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); clearAccessToken(); setTenant(tenant); });
  const selected = () => container.querySelector("output")?.textContent;
  it("optional provider keeps standalone existing pages working", async () => {
    await act(async () => root.render(<><Publisher data={value} /><Probe /></>));
    expect(selected()).toBe("unknown");
  });
  it("publishes only a current tenant readonly selection and clears null", async () => {
    const render = (data: AnalystSelection | null) => <AnalystSelectionProvider active><Publisher data={data} /><Probe /></AnalystSelectionProvider>;
    await act(async () => root.render(render(value)));
    expect(selected()).toBe("niushop:1/store-a");
    await act(async () => root.render(render(null)));
    expect(selected()).toBe("unknown");
  });
  it("new owner wins; old late publication and old cleanup cannot overwrite it", async () => {
    const newer = { ...value, entityId: "store-b" };
    const render = (old: AnalystSelection | null, showOld: boolean) => <AnalystSelectionProvider active>
      {showOld && <Publisher key="old" data={old} client={clientA} />}
      <Publisher key="new" data={newer} client={clientB} /><Probe />
    </AnalystSelectionProvider>;
    await act(async () => root.render(render(value, true)));
    expect(selected()).toBe("niushop:1/store-b");
    await act(async () => root.render(render({ ...value, entityId: "late-old" }, true)));
    expect(selected()).toBe("niushop:1/store-b");
    await act(async () => root.render(render(null, false)));
    expect(selected()).toBe("niushop:1/store-b");
  });
  it("auth change invalidates cached value until a new source value arrives", async () => {
    const render = (data: AnalystSelection) => <AnalystSelectionProvider active><Publisher data={data} /><Probe /></AnalystSelectionProvider>;
    await act(async () => root.render(render(value)));
    await act(async () => setAccessToken("unit-session-change"));
    expect(selected()).toBe("unknown");
    await act(async () => root.render(render(value)));
    expect(selected()).toBe("unknown");
    await act(async () => root.render(render({ ...value })));
    expect(selected()).toBe("niushop:1/store-a");
  });
  it("tenant change hides old values and returning does not revive cached data", async () => {
    const render = (data: AnalystSelection) => <AnalystSelectionProvider active><Publisher data={data} /><Probe /></AnalystSelectionProvider>;
    await act(async () => root.render(render(value)));
    await act(async () => setTenant({ orgId: "dev-org", projectId: "dev-project" }));
    expect(selected()).toBe("unknown");
    await act(async () => root.render(render({ ...value })));
    expect(selected()).toBe("unknown");
    await act(async () => setTenant(tenant));
    expect(selected()).toBe("unknown");
    await act(async () => root.render(render({ ...value })));
    expect(selected()).toBe("niushop:1/store-a");
  });
  it("leaving and returning to analyst requires a fresh value", async () => {
    const render = (active: boolean, data: AnalystSelection) => <AnalystSelectionProvider active={active}><Publisher data={data} /><Probe /></AnalystSelectionProvider>;
    await act(async () => root.render(render(true, value)));
    await act(async () => root.render(render(false, value)));
    expect(selected()).toBe("unknown");
    await act(async () => root.render(render(true, value)));
    expect(selected()).toBe("unknown");
    await act(async () => root.render(render(true, { ...value })));
    expect(selected()).toBe("niushop:1/store-a");
  });
});
