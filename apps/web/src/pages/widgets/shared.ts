/**
 * Widget 共享样式 / 工具
 * 复用项目 CSS 变量，保持视觉一致
 */
import type { CSSProperties } from "react";

export const COLOR_MAP: Record<string, string> = {
  blue: "#3B82F6",
  amber: "#F59E0B",
  green: "#10B981",
  indigo: "#6366F1",
  violet: "#8B5CF6",
  red: "#EF4444",
  pink: "#EC4899",
  cyan: "#06B6D4",
};

export const CARD_STYLE: CSSProperties = {
  padding: 16,
  borderRadius: 8,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
};

export const MUTED_TEXT: CSSProperties = {
  fontSize: 11,
  color: "var(--aos-text-muted)",
};

export const TITLE_TEXT: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: "var(--aos-text)",
};

export const VALUE_TEXT: CSSProperties = {
  fontSize: 22,
  fontWeight: 700,
  color: "var(--aos-text)",
};

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

export function formatCurrency(n: number): string {
  if (Math.abs(n) >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
  if (Math.abs(n) >= 1_000) return "$" + (n / 1_000).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}

// 生成确定性的伪随机数（基于 seed，避免每次渲染抖动）
export function seededRand(seed: number): number {
  const x = Math.sin(seed * 9999) * 10000;
  return x - Math.floor(x);
}
