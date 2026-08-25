import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ThreeModuleClosureCard, unavailableThreeModuleClosure } from "./ThreeModuleClosureCard";

describe("ThreeModuleClosureCard", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("分开展示五轴并保持零副作用", () => { const value = unavailableThreeModuleClosure("customer", { orgId: "org-org", projectId: "dev-project" }, "2026-08-25T09:00:00Z"); act(() => root.render(<ThreeModuleClosureCard value={value} />)); expect(host.textContent).toContain("Item outcome"); expect(host.textContent).toContain("Usage settlement"); expect(host.textContent).toContain("Effect maturity"); expect(host.textContent).toContain("Handoff decision"); expect(host.textContent).toContain("unknown 不造 0"); expect(host.textContent).toContain("Memory promotion：0"); expect(host.querySelectorAll("button")).toHaveLength(0); });
});
