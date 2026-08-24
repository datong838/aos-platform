import type { AgentRuntimeReadinessResponse, AssetRef, BindingReadiness } from "../aipAgentControl";

export type ProfessionalBindingView = {
  skillRef: AssetRef;
  logicRef: AssetRef | null;
  agentTemplateRef: AssetRef;
  agentInstanceRef: AssetRef | null;
  bindingId: string | null;
  bindingVersion: number | null;
  readiness: "available" | "degraded" | "blocked";
  blockerCodes: string[];
};

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

export function projectProfessionalBindings(source: AgentRuntimeReadinessResponse, observedAt = new Date()): ProfessionalBindingView[] {
  const results: ProfessionalBindingView[] = [];
  const identities = new Set<string>();
  for (const catalogItem of source.catalog.items) {
    for (const skill of catalogItem.skills) {
      const identity = `${skill.skillId}@${skill.revision}`;
      if (identities.has(identity)) throw new Error(`重复 Skill identity：${identity}`);
      identities.add(identity);
      const instance = catalogItem.instance;
      const binding = instance
        ? source.skillBindings.find((candidate) => candidate.instanceId === instance.instanceId && candidate.skill.assetId === skill.skillId && candidate.skill.revision === skill.revision && candidate.skill.contentHash === skill.contentHash)
        : undefined;
      const blockers = [...catalogItem.blockers];
      if (!skill.logicRevisionRef) blockers.push("LOGIC_REVISION_REF_MISSING");
      if (!instance) blockers.push("AGENT_INSTANCE_MISSING");
      if (!binding) blockers.push("SKILL_BINDING_MISSING");
      if (binding) {
        blockers.push(...binding.readinessReasons);
        if (binding.status !== "active") blockers.push(`SKILL_BINDING_${binding.status.toUpperCase()}`);
        if (binding.readinessExpiresAt && Date.parse(binding.readinessExpiresAt) <= observedAt.getTime()) blockers.push("SKILL_BINDING_STALE");
      }
      const bindingReadiness: BindingReadiness = binding?.readiness ?? "blocked";
      const stale = blockers.includes("SKILL_BINDING_STALE");
      const available = Boolean(instance && skill.logicRevisionRef && binding && binding.status === "active" && bindingReadiness === "available" && catalogItem.runtimeReadiness === "runnable" && !stale);
      const degraded = Boolean(!available && instance && skill.logicRevisionRef && binding && binding.status === "active" && bindingReadiness === "degraded" && !stale);
      results.push({
        skillRef: { assetType: "SkillTemplate", assetId: skill.skillId, revision: skill.revision, contentHash: skill.contentHash },
        logicRef: skill.logicRevisionRef,
        agentTemplateRef: { assetType: "AgentTemplate", assetId: catalogItem.template.templateId, revision: catalogItem.template.revision, contentHash: catalogItem.template.contentHash },
        agentInstanceRef: instance?.instanceRef ?? null,
        bindingId: binding?.bindingId ?? null,
        bindingVersion: binding?.version ?? null,
        readiness: available ? "available" : degraded ? "degraded" : "blocked",
        blockerCodes: unique(blockers.length ? blockers : available ? [] : ["RUNTIME_NOT_RUNNABLE"]),
      });
    }
  }
  return results;
}
