import type { AnalystRoleQueryTemplate } from "./contracts";

export function templateBlockingReason(template: AnalystRoleQueryTemplate | null): string | null {
  if (!template || template.readiness === "ready") return null;
  return template.blockers.map((item) => `${item.code}: ${item.message}`).join("；");
}

export function templateRoleShortName(roleId: string): string {
  return roleId.replace(/^ecommerce\./, "");
}
