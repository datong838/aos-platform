import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  IntegrationCaseDetail,
  IntegrationCaseListResponse,
  IntegrationCaseScope,
  IntegrationCaseTimelineResponse,
} from "../../../api/integrationCases/types";
import {
  CASE_ID,
  CURRENT_CASE_DETAIL_FIXTURE,
  CURRENT_CASE_LIST_FIXTURE,
  REFERENCE_CASE_DETAIL_FIXTURE,
  REFERENCE_CASE_ID,
  REFERENCE_CASE_LIST_FIXTURE,
  TIMELINE_FIXTURE,
} from "../../../api/integrationCases/fixtures";
import type {
  IntegrationCaseReadState,
  IntegrationCasesReadModel,
} from "./integrationCaseViewModel";
import {
  useIntegrationCasesReadModel,
  type IntegrationCasesReadClient,
  type UseIntegrationCasesReadModelOptions,
} from "./useIntegrationCasesReadModel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const SECOND_CASE_ID = "00000000-0000-4000-8000-000000000201";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

function apiError(status: number, code: string): Error {
  return Object.assign(new Error(code), {
    status,
    body: { code, message: code, details: null, traceId: `trace-${status}` },
  });
}

function timelineFor(
  caseId: string,
  scope: IntegrationCaseScope = "current",
): IntegrationCaseTimelineResponse {
  return { ...TIMELINE_FIXTURE, caseId, scope };
}

function secondCurrentList(): IntegrationCaseListResponse {
  return {
    ...CURRENT_CASE_LIST_FIXTURE,
    items: [
      ...CURRENT_CASE_LIST_FIXTURE.items,
      {
        ...CURRENT_CASE_LIST_FIXTURE.items[0],
        caseId: SECOND_CASE_ID,
        displayName: "Douyin creator operations",
      },
    ],
    total: 27,
  };
}

function secondDetail(): IntegrationCaseDetail {
  return {
    ...CURRENT_CASE_DETAIL_FIXTURE,
    caseId: SECOND_CASE_ID,
    displayName: "Douyin creator operations",
  };
}

function mockClient(): IntegrationCasesReadClient & {
  listCases: ReturnType<typeof vi.fn>;
  getCase: ReturnType<typeof vi.fn>;
  listTimeline: ReturnType<typeof vi.fn>;
} {
  return {
    listCases: vi.fn(),
    getCase: vi.fn(),
    listTimeline: vi.fn(),
  };
}

describe("M4-3 integration cases read model", () => {
  let host: HTMLDivElement;
  let root: Root;
  let latest: IntegrationCasesReadModel;

  async function flush() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  function Probe({ options }: { options: UseIntegrationCasesReadModelOptions }) {
    latest = useIntegrationCasesReadModel(options);
    return null;
  }

  function render(options: UseIntegrationCasesReadModelOptions) {
    act(() => root.render(<Probe options={options} />));
  }

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.restoreAllMocks();
  });

  it("loads the real list and keeps server totals/stats while filtering presentation", async () => {
    const client = mockClient();
    const response = secondCurrentList();
    client.listCases.mockResolvedValue(response);
    render({
      tenantKey: "org-a/project-a",
      scope: "current",
      filter: " creator ",
      limit: 20,
      offset: 5,
      client,
    });
    expect(latest.list.status).toBe("loading");
    await flush();

    expect(client.listCases).toHaveBeenCalledWith({
      scope: "current",
      limit: 20,
      offset: 5,
    });
    expect(latest.list).toMatchObject({
      data: response,
      status: "ready",
      error: null,
    });
    expect(latest.visibleItems.map((item) => item.caseId)).toEqual([
      SECOND_CASE_ID,
    ]);
    expect(latest.list.data?.total).toBe(27);
    expect(latest.list.data?.stats).toBe(CURRENT_CASE_LIST_FIXTURE.stats);
  });

  it("uses empty only for a successful list or timeline with no items", async () => {
    const client = mockClient();
    client.listCases.mockResolvedValue({
      ...CURRENT_CASE_LIST_FIXTURE,
      items: [],
      total: 0,
    });
    render({ tenantKey: "tenant-a", scope: "current", client });
    await flush();
    expect(latest.list.status).toBe("empty");
    expect(latest.list.data?.items).toEqual([]);
    expect(latest.visibleItems).toEqual([]);

    client.listCases.mockResolvedValue(CURRENT_CASE_LIST_FIXTURE);
    client.getCase.mockResolvedValue(CURRENT_CASE_DETAIL_FIXTURE);
    client.listTimeline.mockResolvedValue({ ...TIMELINE_FIXTURE, items: [], total: 0 });
    render({ tenantKey: "tenant-b", scope: "current", client });
    await flush();
    act(() => latest.selectCase(CASE_ID));
    await flush();
    expect(latest.timeline.status).toBe("empty");
    expect(latest.detail.status).toBe("ready");
  });

  it.each([
    [401, "AUTH_REQUIRED", "error"],
    [403, "MARKING_ACCESS_DENIED", "forbidden"],
    [404, "NOT_FOUND", "not_visible_or_missing"],
  ] as const)(
    "maps an initial list HTTP %i failure without fallback facts",
    async (status, code, expectedStatus) => {
      const client = mockClient();
      client.listCases.mockRejectedValue(apiError(status, code));
      render({ tenantKey: "tenant-a", scope: "current", client });
      await flush();
      expect(latest.list).toMatchObject({
        data: null,
        status: expectedStatus,
      });
      expect(latest.visibleItems).toEqual([]);
    },
  );

  it("loads detail and timeline independently after selecting a visible case", async () => {
    const client = mockClient();
    client.listCases.mockResolvedValue(CURRENT_CASE_LIST_FIXTURE);
    client.getCase.mockResolvedValue(CURRENT_CASE_DETAIL_FIXTURE);
    client.listTimeline.mockResolvedValue(TIMELINE_FIXTURE);
    render({ tenantKey: "tenant-a", scope: "current", client });
    await flush();

    act(() => latest.selectCase(CASE_ID));
    expect(latest.selectedCaseId).toBe(CASE_ID);
    expect(latest.detail.status).toBe("loading");
    expect(latest.timeline.status).toBe("loading");
    await flush();

    expect(client.getCase).toHaveBeenCalledWith(CASE_ID);
    expect(client.listTimeline).toHaveBeenCalledWith(CASE_ID, {
      limit: 50,
      offset: 0,
    });
    expect(latest.detail).toMatchObject({
      data: CURRENT_CASE_DETAIL_FIXTURE,
      status: "ready",
    });
    expect(latest.timeline).toMatchObject({
      data: TIMELINE_FIXTURE,
      status: "ready",
    });
  });

  it("does not let a detail failure destroy the usable list or timeline", async () => {
    const client = mockClient();
    client.listCases.mockResolvedValue(CURRENT_CASE_LIST_FIXTURE);
    client.getCase.mockRejectedValue(apiError(500, "EVIDENCE_INTEGRITY_CORRUPT"));
    client.listTimeline.mockResolvedValue(TIMELINE_FIXTURE);
    render({ tenantKey: "tenant-a", scope: "current", client });
    await flush();
    act(() => latest.selectCase(CASE_ID));
    await flush();

    expect(latest.list.status).toBe("ready");
    expect(latest.detail).toMatchObject({ data: null, status: "error" });
    expect(latest.detail.error?.failureClosed).toBe(true);
    expect(latest.timeline).toMatchObject({
      data: TIMELINE_FIXTURE,
      status: "ready",
    });
  });

  it("marks all retained server facts stale when a manual refresh fails", async () => {
    const client = mockClient();
    const listRefresh = deferred<IntegrationCaseListResponse>();
    const detailRefresh = deferred<IntegrationCaseDetail>();
    const timelineRefresh = deferred<IntegrationCaseTimelineResponse>();
    client.listCases
      .mockResolvedValueOnce(CURRENT_CASE_LIST_FIXTURE)
      .mockReturnValueOnce(listRefresh.promise);
    client.getCase
      .mockResolvedValueOnce(CURRENT_CASE_DETAIL_FIXTURE)
      .mockReturnValueOnce(detailRefresh.promise);
    client.listTimeline
      .mockResolvedValueOnce(TIMELINE_FIXTURE)
      .mockReturnValueOnce(timelineRefresh.promise);
    render({ tenantKey: "tenant-a", scope: "current", client });
    await flush();
    act(() => latest.selectCase(CASE_ID));
    await flush();

    act(() => latest.refreshAll());
    expect(latest.list.status).toBe("refreshing");
    expect(latest.detail.status).toBe("refreshing");
    expect(latest.timeline.status).toBe("refreshing");
    listRefresh.reject(apiError(0, "NETWORK"));
    detailRefresh.reject(apiError(500, "EVIDENCE_INTEGRITY_CORRUPT"));
    timelineRefresh.reject(apiError(500, "INTERNAL_ERROR"));
    await flush();

    for (const state of [latest.list, latest.detail, latest.timeline]) {
      expect(state.status).toBe("stale");
      expect(state.data).not.toBeNull();
      expect(state.error?.failureClosed).toBe(true);
    }
  });

  it.each([
    [401, "AUTH_REQUIRED", "error"],
    [403, "MARKING_ACCESS_DENIED", "forbidden"],
    [404, "NOT_FOUND", "not_visible_or_missing"],
  ] as const)(
    "clears retained detail facts after HTTP %i",
    async (status, code, expectedStatus) => {
      const client = mockClient();
      client.listCases.mockResolvedValue(CURRENT_CASE_LIST_FIXTURE);
      client.getCase
        .mockResolvedValueOnce(CURRENT_CASE_DETAIL_FIXTURE)
        .mockRejectedValueOnce(apiError(status, code));
      client.listTimeline.mockResolvedValue(TIMELINE_FIXTURE);
      render({ tenantKey: "tenant-a", scope: "current", client });
      await flush();
      act(() => latest.selectCase(CASE_ID));
      await flush();
      act(() => latest.refreshDetail());
      await flush();

      expect(latest.detail).toMatchObject({
        data: null,
        status: expectedStatus,
      });
      expect(latest.detail.error?.status).toBe(status);
    },
  );

  it("isolates an old scope list response and clears selection immediately", async () => {
    const client = mockClient();
    const currentRefresh = deferred<IntegrationCaseListResponse>();
    const reference = deferred<IntegrationCaseListResponse>();
    let currentReads = 0;
    client.listCases.mockImplementation(
      ({ scope }: { scope: IntegrationCaseScope }) =>
        scope === "current"
          ? currentReads++ === 0
            ? Promise.resolve(CURRENT_CASE_LIST_FIXTURE)
            : currentRefresh.promise
          : reference.promise,
    );
    const base = { tenantKey: "tenant-a", filter: "", client };
    render({ ...base, scope: "current" });
    await flush();
    act(() => latest.selectCase(CASE_ID));
    expect(latest.selectedCaseId).toBe(CASE_ID);
    act(() => latest.refreshList());
    await flush();
    expect(latest.list.status).toBe("refreshing");

    render({ ...base, scope: "reference" });
    expect(latest.scope).toBe("reference");
    expect(latest.selectedCaseId).toBeNull();
    expect(latest.list).toMatchObject({ data: null, status: "loading" });
    expect(latest.detail.status).toBe("idle");
    expect(latest.timeline.status).toBe("idle");
    reference.resolve(REFERENCE_CASE_LIST_FIXTURE);
    await flush();
    expect(latest.list.data).toBe(REFERENCE_CASE_LIST_FIXTURE);

    currentRefresh.resolve(CURRENT_CASE_LIST_FIXTURE);
    await flush();
    expect(latest.list.data).toBe(REFERENCE_CASE_LIST_FIXTURE);
  });

  it("isolates late detail and timeline responses from an old selection", async () => {
    const client = mockClient();
    const list = secondCurrentList();
    const oldDetail = deferred<IntegrationCaseDetail>();
    const newDetail = deferred<IntegrationCaseDetail>();
    const oldTimeline = deferred<IntegrationCaseTimelineResponse>();
    const newTimeline = deferred<IntegrationCaseTimelineResponse>();
    client.listCases.mockResolvedValue(list);
    client.getCase.mockImplementation((caseId: string) =>
      caseId === CASE_ID ? oldDetail.promise : newDetail.promise,
    );
    client.listTimeline.mockImplementation((caseId: string) =>
      caseId === CASE_ID ? oldTimeline.promise : newTimeline.promise,
    );
    render({ tenantKey: "tenant-a", scope: "current", client });
    await flush();
    act(() => latest.selectCase(CASE_ID));
    await flush();
    act(() => latest.selectCase(SECOND_CASE_ID));
    await flush();

    newDetail.resolve(secondDetail());
    newTimeline.resolve(timelineFor(SECOND_CASE_ID));
    await flush();
    expect(latest.detail.data?.caseId).toBe(SECOND_CASE_ID);
    expect(latest.timeline.data?.caseId).toBe(SECOND_CASE_ID);

    oldDetail.resolve(CURRENT_CASE_DETAIL_FIXTURE);
    oldTimeline.resolve(TIMELINE_FIXTURE);
    await flush();
    expect(latest.detail.data?.caseId).toBe(SECOND_CASE_ID);
    expect(latest.timeline.data?.caseId).toBe(SECOND_CASE_ID);
  });

  it("tenant and filter changes clear selection without filter-driven API reads", async () => {
    const client = mockClient();
    client.listCases.mockResolvedValue(secondCurrentList());
    client.getCase.mockResolvedValue(CURRENT_CASE_DETAIL_FIXTURE);
    client.listTimeline.mockResolvedValue(TIMELINE_FIXTURE);
    const base = { scope: "current" as const, client };
    render({ ...base, tenantKey: "tenant-a", filter: "" });
    await flush();
    act(() => latest.selectCase(CASE_ID));
    await flush();

    render({ ...base, tenantKey: "tenant-a", filter: "creator" });
    expect(latest.selectedCaseId).toBeNull();
    expect(latest.detail.status).toBe("idle");
    expect(client.listCases).toHaveBeenCalledTimes(1);
    expect(latest.visibleItems.map((item) => item.caseId)).toEqual([
      SECOND_CASE_ID,
    ]);

    render({ ...base, tenantKey: "tenant-b", filter: "creator" });
    expect(latest.selectedCaseId).toBeNull();
    expect(latest.list).toMatchObject({ data: null, status: "loading" });
    await flush();
    expect(client.listCases).toHaveBeenCalledTimes(2);
  });

  it("clears a stale list error when the presentation filter changes", async () => {
    const client = mockClient();
    client.listCases
      .mockResolvedValueOnce(secondCurrentList())
      .mockRejectedValueOnce(apiError(500, "INTERNAL_ERROR"));
    const base = { tenantKey: "tenant-a", scope: "current" as const, client };
    render({ ...base, filter: "" });
    await flush();
    act(() => latest.refreshList());
    await flush();
    expect(latest.list.status).toBe("stale");
    expect(latest.list.error).not.toBeNull();

    render({ ...base, filter: "creator" });
    await flush();
    expect(client.listCases).toHaveBeenCalledTimes(2);
    expect(latest.list).toMatchObject({ status: "ready", error: null });
    expect(latest.visibleItems.map((item) => item.caseId)).toEqual([
      SECOND_CASE_ID,
    ]);
  });

  it("preserves reference privacy fields and never manufactures current stats", async () => {
    const client = mockClient();
    client.listCases.mockResolvedValue(REFERENCE_CASE_LIST_FIXTURE);
    client.getCase.mockResolvedValue(REFERENCE_CASE_DETAIL_FIXTURE);
    client.listTimeline.mockResolvedValue(
      timelineFor(REFERENCE_CASE_ID, "reference"),
    );
    render({ tenantKey: "tenant-a", scope: "reference", client });
    await flush();
    act(() => latest.selectCase(REFERENCE_CASE_ID));
    await flush();

    expect(latest.list.data?.stats).toBeNull();
    expect(latest.detail.data).toMatchObject({
      scope: "reference",
      owner: null,
      installationId: null,
      overlayRevision: null,
      compositionId: null,
      lockHash: null,
      metrics: null,
    });
  });

  it("rejects selecting facts outside the currently visible service list", async () => {
    const client = mockClient();
    client.listCases.mockResolvedValue(CURRENT_CASE_LIST_FIXTURE);
    render({ tenantKey: "tenant-a", scope: "current", client });
    await flush();
    expect(() => latest.selectCase(SECOND_CASE_ID)).toThrow(/visible/);
    expect(client.getCase).not.toHaveBeenCalled();
    expect(client.listTimeline).not.toHaveBeenCalled();
  });

  it("keeps state types independently consumable by detail and timeline components", () => {
    const detail: IntegrationCaseReadState<IntegrationCaseDetail> = {
      data: null,
      status: "idle",
      error: null,
    };
    const timeline: IntegrationCaseReadState<IntegrationCaseTimelineResponse> = {
      data: null,
      status: "not_visible_or_missing",
      error: null,
    };
    expect(detail.status).toBe("idle");
    expect(timeline.status).toBe("not_visible_or_missing");
  });
});
