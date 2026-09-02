import type { AsyncState } from "./AsyncStateBoundary";

export type WorkshopViewStatus = "ready" | "blocked" | "conflict" | "unknown";

export function deriveWorkshopViewState<T extends { status: WorkshopViewStatus }>(
  views: readonly T[],
  itemCount: number,
): AsyncState {
  const readyCount = views.filter((view) => view.status === "ready").length;
  if (readyCount > 0 && readyCount < views.length) return "partial";
  if (readyCount === views.length && views.length > 0) return itemCount === 0 ? "empty" : "ready";
  if (views.some((view) => view.status === "conflict")) return "conflict";
  return "blocked";
}

export function pickPreferredWorkshopView<T extends { status: WorkshopViewStatus }>(
  views: readonly T[],
  hasUsableData: (view: T) => boolean,
): T | undefined {
  return views.find((view) => view.status === "ready" && hasUsableData(view))
    ?? views.find((view) => view.status === "ready")
    ?? views.find((view) => view.status === "conflict")
    ?? views[0];
}
