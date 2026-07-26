import type { ReactNode } from "react";

export type BpBadgeTone = "neutral" | "green" | "amber" | "red" | "blue";

export function BpBadge({
  tone = "neutral",
  size = "md",
  children,
}: {
  tone?: BpBadgeTone;
  size?: "sm" | "md";
  children: ReactNode;
}) {
  const cls = ["bp-badge", `bp-badge-${tone}`];
  if (size === "sm") cls.push("bp-badge-sm");
  return <span className={cls.join(" ")}>{children}</span>;
}
