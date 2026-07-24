import { createElement, useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";

const getObject = vi.fn();
const listDrafts = vi.fn();

vi.mock("./ontologyClient", () => ({
  getOntologyClient: () => ({ getObject, listDrafts }),
}));

describe("ontologyHooks", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    getObject.mockReset();
    listDrafts.mockReset();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    host.remove();
  });

  it("useOntologyObject loads via SDK", async () => {
    getObject.mockResolvedValue({ id: "wo-1", title: "A" });
    const { useOntologyObject } = await import("./ontologyHooks");

    function Probe() {
      const { data, loading, err } = useOntologyObject("WorkOrder", "wo-1");
      useEffect(() => {
        host.dataset.loading = String(loading);
        host.dataset.err = err || "";
        host.dataset.id = data?.id ? String(data.id) : "";
      }, [data, loading, err]);
      return null;
    }

    await act(async () => {
      root.render(createElement(Probe));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(getObject).toHaveBeenCalledWith("WorkOrder", "wo-1");
    expect(host.dataset.id).toBe("wo-1");
    expect(host.dataset.loading).toBe("false");
  });

  it("useOntologyDrafts loads via SDK", async () => {
    listDrafts.mockResolvedValue({ items: [{ id: "dr-1", status: "proposed" }] });
    const { useOntologyDrafts } = await import("./ontologyHooks");

    function Probe() {
      const { data, loading } = useOntologyDrafts();
      useEffect(() => {
        host.dataset.loading = String(loading);
        host.dataset.id = data?.items?.[0]?.id ? String(data.items[0].id) : "";
      }, [data, loading]);
      return null;
    }

    await act(async () => {
      root.render(createElement(Probe));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(listDrafts).toHaveBeenCalled();
    expect(host.dataset.id).toBe("dr-1");
  });
});
