import type { ReactNode } from "react";

/** T1.9 Widget Marking — no marking ⇒ widget not mounted. */
export function hasMarkingAccess(
  required: string[] | undefined,
  userMarkings: string[],
): boolean {
  if (!required || required.length === 0) return true;
  const set = new Set(userMarkings);
  return required.every((m) => set.has(m));
}

export function RestrictedWidget({
  requiredMarkings,
  userMarkings,
  children,
}: {
  requiredMarkings?: string[];
  userMarkings: string[];
  children: ReactNode;
}) {
  if (!hasMarkingAccess(requiredMarkings, userMarkings)) {
    return null;
  }
  return <>{children}</>;
}
