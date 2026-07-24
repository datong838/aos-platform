/** Selection dimension guard — T08 / T1.5 (≤10). */
export const SELECTION_LIMIT = 10;

export type SelectionFilter = { field: string; value: string };

export function canAddFilter(
  current: SelectionFilter[],
  next: SelectionFilter,
): { ok: true } | { ok: false; reason: string } {
  if (current.length >= SELECTION_LIMIT) {
    return { ok: false, reason: `Selection 维数上限 ${SELECTION_LIMIT}` };
  }
  if (current.some((f) => f.field === next.field && f.value === next.value)) {
    return { ok: false, reason: "重复筛选维" };
  }
  return { ok: true };
}

export function addFilter(
  current: SelectionFilter[],
  next: SelectionFilter,
): SelectionFilter[] {
  const gate = canAddFilter(current, next);
  if (!gate.ok) {
    throw new Error(gate.reason);
  }
  return [...current, next];
}
