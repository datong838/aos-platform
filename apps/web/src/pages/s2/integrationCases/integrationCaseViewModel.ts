import type { IntegrationCaseError } from "../../../api/integrationCases/errors";
import type {
  IntegrationCaseDetail,
  IntegrationCaseListItem,
  IntegrationCaseListResponse,
  IntegrationCaseScope,
  IntegrationCaseTimelineResponse,
} from "../../../api/integrationCases/types";

export const INTEGRATION_CASE_READ_STATUSES = [
  "idle",
  "loading",
  "ready",
  "empty",
  "forbidden",
  "not_visible_or_missing",
  "error",
  "stale",
  "refreshing",
] as const;

export type IntegrationCaseReadStatus =
  (typeof INTEGRATION_CASE_READ_STATUSES)[number];

export interface IntegrationCaseReadState<T> {
  data: T | null;
  status: IntegrationCaseReadStatus;
  error: IntegrationCaseError | null;
}
export interface IntegrationCasesReadModel {
  scope: IntegrationCaseScope;
  selectedCaseId: string | null;
  selectCase: (caseId: string | null) => void;
  list: IntegrationCaseReadState<IntegrationCaseListResponse>;
  detail: IntegrationCaseReadState<IntegrationCaseDetail>;
  timeline: IntegrationCaseReadState<IntegrationCaseTimelineResponse>;
  visibleItems: IntegrationCaseListItem[];
  refreshList: () => void;
  refreshDetail: () => void;
  refreshTimeline: () => void;
  refreshAll: () => void;
}

export function normalizeIntegrationCaseFilter(value: string): string {
  return value.trim().toLocaleLowerCase();
}

/**
 * Presentation-only filtering. Server totals, statistics, stages, blockers,
 * metrics, and evidence remain untouched and must be rendered from `list.data`.
 */
export function filterIntegrationCaseItems(
  items: readonly IntegrationCaseListItem[],
  filter: string,
): IntegrationCaseListItem[] {
  const query = normalizeIntegrationCaseFilter(filter);
  if (!query) return [...items];
  return items.filter((item) =>
    [
      item.displayName,
      item.caseId,
      item.owner,
      item.installationId,
      item.overlayRevision,
    ].some((value) => value?.toLocaleLowerCase().includes(query)),
  );
}
