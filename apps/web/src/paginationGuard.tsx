import { useMemo } from "react";

/** T1.8 — Table >10k hint / force pagination banner. */
export const LARGE_TABLE_HINT_THRESHOLD = 10_000;

export function needsPaginationHint(total: number): boolean {
  return total > LARGE_TABLE_HINT_THRESHOLD;
}

/** 大结果护栏提示（真实 total）。模拟器已从产品页移除，见方案 75。 */
export function PaginationGuardBanner({ total }: { total: number }) {
  if (!needsPaginationHint(total)) return null;
  return (
    <div className="banner warn" role="status">
      结果约 {total.toLocaleString()} 行，超过 {LARGE_TABLE_HINT_THRESHOLD.toLocaleString()}{" "}
      行护栏：请缩小 Selection 或强制分页后再浏览。
    </div>
  );
}

export function useDisplayTotal(realTotal: number, override: number | null) {
  return useMemo(
    () => (override === null ? realTotal : override),
    [realTotal, override],
  );
}
