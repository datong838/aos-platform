import { describe, expect, it } from "vitest";
import {
  agentReadinessLadderSummary,
  blockerDisplayName,
  capabilityDisplayName,
  definitionReadinessDisplayName,
  deriveAgentReadinessLadder,
  dimensionDisplayName,
  formatBlockers,
  instanceStatusDisplayName,
  logicDisplayName,
  responsibilityDisplayName,
  riskDisplayName,
  templateDisplayName,
  toolKindDisplayName,
  toolDisplayName,
  runtimeModeDisplayName,
  contractSectionDisplayName,
  statusDisplayName,
  businessDisplayName,
} from "./aipChineseLabels";

describe("aipChineseLabels", () => {
  it("把 logic 代号译为中文名", () => {
    expect(logicDisplayName("ecommerce.logic.S01")).toBe("意图与情绪识别");
    expect(logicDisplayName("D03")).toBe("增长方案生成");
    expect(logicDisplayName("ecommerce.logic.A01")).toBe("活动机会与目标");
  });

  it("把 Capability / 职责 / 阻断码译为中文", () => {
    expect(capabilityDisplayName("strategy.plan")).toBe("策略规划");
    expect(responsibilityDisplayName("service.escalation")).toBe("售后服务与升级");
    expect(blockerDisplayName("skill_binding_readiness_stale")).toContain("技能绑定");
    expect(blockerDisplayName("capabilities_not_fully_runnable")).toBe("当前方案所需专业能力尚未全部可派发");
    expect(blockerDisplayName("tools_not_fully_runnable")).toBe("当前方案所需工具尚未全部可派发");
    expect(blockerDisplayName("skill_revision_not_published:C01")).toContain("热点竞品");
    expect(formatBlockers(["capability_binding_readiness_stale", "skill_binding_readiness_stale"])).toContain("；");
  });

  it("实例状态与八维标签中文", () => {
    expect(instanceStatusDisplayName("active")).toBe("已启用");
    expect(riskDisplayName("high")).toBe("高");
    expect(definitionReadinessDisplayName("blocked")).toBe("定义未就绪");
    expect(dimensionDisplayName("providerRef")).toBe("供应商");
    expect(templateDisplayName("ecommerce.content_officer")).toBe("内容官");
  });

  it("W-L1 已安装不等于可派发", () => {
    const installedOnly = deriveAgentReadinessLadder({
      templatePublished: true,
      installed: true,
      hasActiveSkillBinding: false,
      skillsPublished: false,
      capabilityOperational: false,
      runtimeReadiness: "blocked",
    });
    expect(installedOnly.dispatchable).toBe(false);
    expect(installedOnly.stages.find((s) => s.id === "installed")?.done).toBe(true);
    expect(installedOnly.stages.find((s) => s.id === "runnable")?.done).toBe(false);
    expect(agentReadinessLadderSummary(installedOnly)).toContain("已安装未可派发");
    const runnable = deriveAgentReadinessLadder({
      templatePublished: true,
      installed: true,
      hasActiveSkillBinding: true,
      skillsPublished: true,
      capabilityOperational: true,
      runtimeReadiness: "runnable",
    });
    expect(runnable.dispatchable).toBe(true);
    expect(agentReadinessLadderSummary(runnable)).toContain("可派发");
  });

  it("工具主展示使用中文业务名称，内部 Function ID 只作为审计标识", () => {
    expect(toolKindDisplayName("Function")).toBe("业务逻辑工具");
    expect(toolKindDisplayName("Object Query")).toBe("业务对象查询");
    expect(toolDisplayName({ id: "fn.logic.ecommerce.logic.S05", kind: "Function" })).toBe("投诉与人工升级");
    expect(toolDisplayName({ id: "query.objects", kind: "Object Query" })).toBe("业务对象查询");
    expect(toolDisplayName({ id: "action.close", kind: "Action", nameZh: "关闭/写回（HITL）" })).toBe("关闭或写回（需人工确认）");
    expect(toolDisplayName({ id: "fn.echo", kind: "Function", nameZh: "Echo（演示）" })).toBe("连通性校验");
  });

  it("运行模式、生产契约和状态使用中文业务语义", () => {
    expect(runtimeModeDisplayName("native")).toBe("并行调用");
    expect(runtimeModeDisplayName("prompted")).toBe("逐项调用");
    expect(contractSectionDisplayName("Task Brief")).toBe("任务简报");
    expect(contractSectionDisplayName("Evidence Bundle")).toBe("证据包");
    expect(statusDisplayName("running")).toBe("运行中");
    expect(statusDisplayName("published")).toBe("已发布");
  });

  it("业务标题移除实施波次前缀且不改权威 ID", () => {
    expect(businessDisplayName("D3 · 内容策略助手")).toBe("内容策略助手");
    expect(businessDisplayName("W03-短视频制作")).toBe("短视频制作");
    expect(businessDisplayName("AIP-1C 权威运行验收")).toBe("权威运行验收");
    expect(businessDisplayName("C08 内容到成交归因与优化治理契约门 v1（隔离 dry-run）"))
      .toBe("内容到成交归因与优化治理契约门 v1（隔离试运行）");
    expect(businessDisplayName("电商增长方案包（D3：W03 客户与私域运营台 + L05 分润异常检测）"))
      .toBe("电商增长与客户运营方案包");
    expect(businessDisplayName("内容官")).toBe("内容官");
  });
});
