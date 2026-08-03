import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  integrationCaseClient,
  type IntegrationCaseListQuery,
  type IntegrationCaseTimelineQuery,
} from "../../../api/integrationCases/client";
import {
  normalizeIntegrationCaseError,
  type IntegrationCaseError,
} from "../../../api/integrationCases/errors";
import type {
  IntegrationCaseDetail,
  IntegrationCaseListResponse,
  IntegrationCaseScope,
  IntegrationCaseTimelineResponse,
} from "../../../api/integrationCases/types";
import {
  filterIntegrationCaseItems,
  normalizeIntegrationCaseFilter,
  type IntegrationCaseReadState,
  type IntegrationCaseReadStatus,
  type IntegrationCasesReadModel,
} from "./integrationCaseViewModel";

export interface IntegrationCasesReadClient {
  listCases(query: IntegrationCaseListQuery): Promise<IntegrationCaseListResponse>;
  getCase(caseId: string): Promise<IntegrationCaseDetail>;
  listTimeline(
    caseId: string,
    query?: IntegrationCaseTimelineQuery,
  ): Promise<IntegrationCaseTimelineResponse>;
}

export interface UseIntegrationCasesReadModelOptions {
  tenantKey: string;
  scope: IntegrationCaseScope;
  filter?: string;
  limit?: number;
  offset?: number;
  timelineLimit?: number;
  timelineOffset?: number;
  client?: IntegrationCasesReadClient;
}

interface ReadResource<T> extends IntegrationCaseReadState<T> {
  reload: () => void;
  clearStale: () => void;
}

interface KeyedReadState<T> extends IntegrationCaseReadState<T> {
  requestKey: string | null;
}

function idleState<T>(): KeyedReadState<T> {
  return { requestKey: null, data: null, status: "idle", error: null };
}

function successfulStatus<T>(
  data: T,
  isEmpty: (value: T) => boolean,
): IntegrationCaseReadStatus {
  return isEmpty(data) ? "empty" : "ready";
}

function initialFailureStatus(error: IntegrationCaseError): IntegrationCaseReadStatus {
  if (error.kind === "forbidden") return "forbidden";
  if (error.kind === "not_visible_or_missing") return "not_visible_or_missing";
  return "error";
}

function clearsPriorFacts(error: IntegrationCaseError): boolean {
  return (
    error.kind === "unauthenticated" ||
    error.kind === "forbidden" ||
    error.kind === "not_visible_or_missing"
  );
}

function useReadResource<T>(
  requestKey: string | null,
  read: () => Promise<T>,
  isEmpty: (value: T) => boolean,
): ReadResource<T> {
  const [state, setState] = useState<KeyedReadState<T>>(() => idleState<T>());
  const [reloadSequence, setReloadSequence] = useState(0);
  const generation = useRef(0);
  const previousKey = useRef<string | null>(null);
  const readRef = useRef(read);
  const emptyRef = useRef(isEmpty);
  readRef.current = read;
  emptyRef.current = isEmpty;

  const reload = useCallback(() => {
    if (requestKey !== null) setReloadSequence((value) => value + 1);
  }, [requestKey]);
  const clearStale = useCallback(() => {
    setState((current) => {
      if (
        current.requestKey !== requestKey ||
        current.status !== "stale" ||
        current.data === null
      ) {
        return current;
      }
      return {
        ...current,
        status: successfulStatus(current.data, emptyRef.current),
        error: null,
      };
    });
  }, [requestKey]);

  useEffect(() => {
    const keyChanged = previousKey.current !== requestKey;
    previousKey.current = requestKey;
    const requestGeneration = ++generation.current;
    let active = true;

    if (requestKey === null) {
      setState(idleState<T>());
      return () => {
        active = false;
      };
    }

    setState((current) => {
      if (keyChanged || current.data === null) {
        return { requestKey, data: null, status: "loading", error: null };
      }
      return {
        requestKey,
        data: current.data,
        status: "refreshing",
        error: null,
      };
    });

    void Promise.resolve()
      .then(() => readRef.current())
      .then((data) => {
        if (!active || generation.current !== requestGeneration) return;
        setState({
          requestKey,
          data,
          status: successfulStatus(data, emptyRef.current),
          error: null,
        });
      })
      .catch((cause: unknown) => {
        if (!active || generation.current !== requestGeneration) return;
        const error = normalizeIntegrationCaseError(cause);
        setState((current) => {
          if (current.data !== null && !clearsPriorFacts(error)) {
            return { requestKey, data: current.data, status: "stale", error };
          }
          return {
            requestKey,
            data: null,
            status: initialFailureStatus(error),
            error,
          };
        });
      });

    return () => {
      active = false;
    };
  }, [requestKey, reloadSequence]);

  if (state.requestKey !== requestKey) {
    return {
      data: null,
      status: requestKey === null ? "idle" : "loading",
      error: null,
      reload,
      clearStale,
    };
  }
  return {
    data: state.data,
    status: state.status,
    error: state.error,
    reload,
    clearStale,
  };
}

const listIsEmpty = (response: IntegrationCaseListResponse) =>
  response.items.length === 0;
const timelineIsEmpty = (response: IntegrationCaseTimelineResponse) =>
  response.items.length === 0;
const detailIsNeverEmpty = () => false;

function requireTenantKey(value: string): string {
  if (
    typeof value !== "string" ||
    !value ||
    value !== value.trim() ||
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw new TypeError("tenantKey must be normalized non-empty text");
  }
  return value;
}

function requireScope(value: IntegrationCaseScope): IntegrationCaseScope {
  if (value !== "current" && value !== "reference") {
    throw new TypeError("scope must be current or reference");
  }
  return value;
}

export function useIntegrationCasesReadModel(
  options: UseIntegrationCasesReadModelOptions,
): IntegrationCasesReadModel {
  const tenantKey = requireTenantKey(options.tenantKey);
  const scope = requireScope(options.scope);
  const filter = options.filter ?? "";
  const limit = options.limit ?? 50;
  const offset = options.offset ?? 0;
  const timelineLimit = options.timelineLimit ?? 50;
  const timelineOffset = options.timelineOffset ?? 0;
  const client = options.client ?? integrationCaseClient;
  const normalizedFilter = normalizeIntegrationCaseFilter(filter);
  const listRequestKey = `${tenantKey}\u001f${scope}\u001f${limit}\u001f${offset}`;
  const selectionContextKey = `${listRequestKey}\u001f${normalizedFilter}`;
  const [selection, setSelection] = useState<{
    contextKey: string;
    caseId: string | null;
  }>(() => ({ contextKey: selectionContextKey, caseId: null }));
  const selectedCaseId =
    selection.contextKey === selectionContextKey ? selection.caseId : null;

  useEffect(() => {
    setSelection((current) =>
      current.contextKey === selectionContextKey
        ? current
        : { contextKey: selectionContextKey, caseId: null },
    );
  }, [selectionContextKey]);

  const listResource = useReadResource(
    `integration-cases:${listRequestKey}`,
    () => client.listCases({ scope, limit, offset }),
    listIsEmpty,
  );
  const previousSelectionContext = useRef(selectionContextKey);
  useEffect(() => {
    if (previousSelectionContext.current !== selectionContextKey) {
      previousSelectionContext.current = selectionContextKey;
      listResource.clearStale();
    }
  }, [listResource.clearStale, selectionContextKey]);
  const detailResource = useReadResource(
    selectedCaseId
      ? `integration-case-detail:${tenantKey}:${scope}:${selectedCaseId}`
      : null,
    async () => {
      if (!selectedCaseId) throw new Error("case selection is required");
      const detail = await client.getCase(selectedCaseId);
      if (detail.scope !== scope) {
        throw new Error("detail response scope does not match current selection");
      }
      return detail;
    },
    detailIsNeverEmpty,
  );
  const timelineResource = useReadResource(
    selectedCaseId
      ? `integration-case-timeline:${tenantKey}:${scope}:${selectedCaseId}:${timelineLimit}:${timelineOffset}`
      : null,
    async () => {
      if (!selectedCaseId) throw new Error("case selection is required");
      const timeline = await client.listTimeline(selectedCaseId, {
        limit: timelineLimit,
        offset: timelineOffset,
      });
      if (timeline.scope !== scope) {
        throw new Error("timeline response scope does not match current selection");
      }
      return timeline;
    },
    timelineIsEmpty,
  );

  const visibleItems = useMemo(
    () => filterIntegrationCaseItems(listResource.data?.items ?? [], filter),
    [filter, listResource.data],
  );

  useEffect(() => {
    if (
      selectedCaseId !== null &&
      listResource.data !== null &&
      !visibleItems.some((item) => item.caseId === selectedCaseId)
    ) {
      setSelection({ contextKey: selectionContextKey, caseId: null });
    }
  }, [listResource.data, selectedCaseId, selectionContextKey, visibleItems]);

  const selectCase = useCallback(
    (caseId: string | null) => {
      if (
        caseId !== null &&
        !visibleItems.some((item) => item.caseId === caseId)
      ) {
        throw new TypeError("selected case must be visible in the current list");
      }
      setSelection({ contextKey: selectionContextKey, caseId });
    },
    [selectionContextKey, visibleItems],
  );

  const refreshAll = useCallback(() => {
    listResource.reload();
    detailResource.reload();
    timelineResource.reload();
  }, [detailResource.reload, listResource.reload, timelineResource.reload]);

  return {
    scope,
    selectedCaseId,
    selectCase,
    list: {
      data: listResource.data,
      status: listResource.status,
      error: listResource.error,
    },
    detail: {
      data: detailResource.data,
      status: detailResource.status,
      error: detailResource.error,
    },
    timeline: {
      data: timelineResource.data,
      status: timelineResource.status,
      error: timelineResource.error,
    },
    visibleItems,
    refreshList: listResource.reload,
    refreshDetail: detailResource.reload,
    refreshTimeline: timelineResource.reload,
    refreshAll,
  };
}
