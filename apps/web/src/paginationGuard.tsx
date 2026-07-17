import { useMemo, useState } from "react";

/** T1.8 — Table >10k hint / force pagination banner. */
export const LARGE_TABLE_HINT_THRESHOLD = 10_000;

export function needsPaginationHint(total: number): boolean {
  return total > LARGE_TABLE_HINT_THRESHOLD;
}

export function PaginationGuardBanner({ total }: { total: number }) {
  if (!needsPaginationHint(total)) return null;
  return (
    <div className="banner warn" role="status">
      结果约 {total.toLocaleString()} 行，超过 {LARGE_TABLE_HINT_THRESHOLD.toLocaleString()}{" "}
      行护栏：请缩小 Selection 或强制分页后再浏览。
    </div>
  );
}

/** Demo control to simulate large totals without huge payloads. */
export function LargeResultSimulator({
  onSimulate,
}: {
  onSimulate: (total: number) => void;
}) {
  const [n, setN] = useState(12_000);
  return (
    <div className="filter-bar">
      <label className="muted">
        模拟 total
        <input
          type="number"
          value={n}
          onChange={(e) => setN(Number(e.target.value))}
          aria-label="simulate-total"
        />
      </label>
      <button type="button" onClick={() => onSimulate(n)}>
        应用护栏演示
      </button>
    </div>
  );
}

export function useDisplayTotal(realTotal: number, override: number | null) {
  return useMemo(
    () => (override === null ? realTotal : override),
    [realTotal, override],
  );
}
