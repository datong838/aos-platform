import type { ReactNode } from "react";

/**
 * BpCard 的视觉变体。
 * - default: 默认（白底 + 细边框）
 * - outlined: 仅 1px 边框，无阴影
 * - elevated: 有 box-shadow（上浮）
 * - filled: 浅灰背景（无边框）
 */
export type BpCardVariant = "default" | "outlined" | "elevated" | "filled";

export type BpCardPadding = "none" | "sm" | "md" | "lg";

/**计算 Card 的完整 className（纯函数，便于测试）*/
export function getCardClassName(
  variant: BpCardVariant,
  padding: BpCardPadding,
  hover?: boolean,
  clickable?: boolean,
): string {
  const cls = ["bp-card", `bp-card-${variant}`, `bp-card-pad-${padding}`];
  if (hover) cls.push("bp-card-hover");
  if (clickable) cls.push("bp-card-clickable");
  return cls.join(" ");
}

/**
 * 卡片容器。
 *
 * 支持 4 种变体（default/outlined/elevated/filled）、4 种内边距（none/sm/md/lg）、
 * hover 上浮阴影、clickable 点击波纹（cursor:pointer），以及 header/footer slots。
 */
export function BpCard({
  variant = "default",
  padding = "md",
  hover = false,
  clickable = false,
  onClick,
  title,
  subtitle,
  actions,
  header,
  footer,
  children,
}: {
  variant?: BpCardVariant;
  padding?: BpCardPadding;
  /**hover 时上浮阴影效果（与 elevated 变体配合更佳）*/
  hover?: boolean;
  /**可点击：cursor:pointer + 点击波纹；需配合 onClick 使用*/
  clickable?: boolean;
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
  /**标题（便捷 slot，等价于 header 的标题部分）*/
  title?: ReactNode;
  /**副标题*/
  subtitle?: ReactNode;
  /**右上角动作区（便捷 slot）*/
  actions?: ReactNode;
  /**自定义头部（ReactNode slot，会覆盖 title/subtitle/actions）*/
  header?: ReactNode;
  /**自定义底部（ReactNode slot）*/
  footer?: ReactNode;
  children?: ReactNode;
}) {
  const className = getCardClassName(variant, padding, hover, clickable);
  const useCustomHeader = header !== undefined;
  const useSimpleHeader = !useCustomHeader && (title || subtitle || actions);

  return (
    <div
      className={className}
      role={clickable && onClick ? "button" : undefined}
      tabIndex={clickable && onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        clickable && onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                e.currentTarget.click();
              }
            }
          : undefined
      }
    >
      {useCustomHeader ? (
        <div className="bp-card-header">{header}</div>
      ) : useSimpleHeader ? (
        <div className="bp-card-header">
          <div>
            {title ? <h3 className="bp-card-title">{title}</h3> : null}
            {subtitle ? <p className="bp-card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="bp-card-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children ? <div className="bp-card-body">{children}</div> : null}
      {footer ? <div className="bp-card-footer">{footer}</div> : null}
    </div>
  );
}
