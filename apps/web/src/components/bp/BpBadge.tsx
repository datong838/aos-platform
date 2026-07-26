import type { ReactNode } from "react";

/**
 * BpBadge 的颜色变体。
 * - default: 灰色（中性）
 * - success: 绿色（成功）
 * - warning: 橙色（警告）
 * - danger: 红色（危险/错误）
 * - info: 蓝色（信息）
 * - purple: 紫色
 * - teal: 青色
 */
export type BpBadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "purple"
  | "teal";

/**旧版 tone 别名（向后兼容，映射到新 variant）*/
export type BpBadgeTone = BpBadgeVariant;

export type BpBadgeSize = "sm" | "md" | "lg";

/**计算 Badge 的完整 className（纯函数，便于测试）*/
export function getBadgeClassName(
  variant: BpBadgeVariant,
  size: BpBadgeSize,
  dot?: boolean,
): string {
  const cls = ["bp-badge", `bp-badge-${variant}`];
  cls.push(`bp-badge-${size}`);
  if (dot) cls.push("bp-badge-dot");
  return cls.join(" ");
}

/**内部圆点（dot 模式下渲染）*/
function Dot({ variant }: { variant: BpBadgeVariant }) {
  return (
    <span
      className={`bp-badge-dot-mark bp-badge-dot-mark-${variant}`}
      aria-hidden="true"
    />
  );
}

/**
 * 胶囊形徽章（圆角 999px）。
 *
 * 支持 7 种颜色变体、3 种尺寸、可选前置圆点（dot）或自定义图标（icon）。
 */
export function BpBadge({
  variant = "default",
  tone,
  size = "md",
  dot = false,
  icon,
  children,
}: {
  /**颜色变体（推荐用 variant）*/
  variant?: BpBadgeVariant;
  /**旧版 tone（向后兼容，与 variant 等价；variant 优先）*/
  tone?: BpBadgeVariant;
  /**尺寸：sm(12px) / md(13px) / lg(14px)*/
  size?: BpBadgeSize;
  /**是否显示前缀小圆点（与 icon 互斥，icon 优先）*/
  dot?: boolean;
  /**自定义前缀图标（ReactNode）*/
  icon?: ReactNode;
  children: ReactNode;
}) {
  const actualVariant = variant ?? tone ?? "default";
  const className = getBadgeClassName(actualVariant, size, dot && !icon);
  return (
    <span className={className} role="status">
      {icon ? (
        <span className="bp-badge-icon" aria-hidden="true">
          {icon}
        </span>
      ) : dot ? (
        <Dot variant={actualVariant} />
      ) : null}
      <span className="bp-badge-text">{children}</span>
    </span>
  );
}
