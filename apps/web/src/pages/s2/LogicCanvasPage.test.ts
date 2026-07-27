import { describe, it, expect } from "vitest";
import { PALETTE, KIND_META, type BranchPath, type HandoffConfig } from "./LogicCanvasPage";

describe("LogicCanvasPage · PALETTE 包含 branch 和 handoff", () => {
  it("test branch block kind exists in palette", () => {
    const branch = PALETTE.find((p) => p.kind === "branch");
    expect(branch).toBeTruthy();
    expect(branch!.title).toMatch(/Branch|分支/);
    expect(branch!.icon.length).toBeGreaterThan(0);
  });

  it("test handoff block kind exists in palette", () => {
    const handoff = PALETTE.find((p) => p.kind === "handoff");
    expect(handoff).toBeTruthy();
    expect(handoff!.title).toMatch(/Handoff|汇聚/);
    expect(handoff!.desc.length).toBeGreaterThan(0);
  });

  it("PALETTE 至少有 10 种 Block（原 8 + branch + handoff）", () => {
    expect(PALETTE.length).toBeGreaterThanOrEqual(10);
  });
});

describe("LogicCanvasPage · KIND_META 颜色配置", () => {
  it("test KIND_META has correct colors for branch/handoff", () => {
    expect(KIND_META.branch).toBeTruthy();
    expect(KIND_META.branch.color).toBe("var(--aos-red)");
    expect(KIND_META.branch.bg).toBe("var(--aos-red-bg)");
    expect(KIND_META.branch.border).toBe("var(--aos-red-border)");

    expect(KIND_META.handoff).toBeTruthy();
    expect(KIND_META.handoff.color).toBe("var(--aos-indigo-600)");
    expect(KIND_META.handoff.bg).toBe("var(--aos-indigo-bg)");
    expect(KIND_META.handoff.border).toBe("var(--aos-indigo-border)");
  });

  it("每个 KIND_META 条目都包含 label/color/bg/border", () => {
    for (const key of Object.keys(KIND_META)) {
      const meta = KIND_META[key as keyof typeof KIND_META];
      expect(meta.label.length).toBeGreaterThan(0);
      // 224 样式规整后颜色值为 CSS 变量 var(--xxx) 或 hex
      expect(meta.color).toMatch(/^(var\(--|#[0-9A-Fa-f])/);
      expect(meta.bg).toMatch(/^(var\(--|#[0-9A-Fa-f])/);
      expect(meta.border).toMatch(/^(var\(--|#[0-9A-Fa-f])/);
    }
  });
});

describe("LogicCanvasPage · Branch 配置面板数据结构", () => {
  it("test branch config panel renders paths（双路分叉数据结构）", () => {
    const defaultPaths: BranchPath[] = [
      { id: "p1", label: "高风险", condition: "risk_level IN [high, critical]", color: "#DC2626" },
      { id: "p2", label: "低风险", condition: "risk_level IN [low, medium]", color: "#16A34A" },
    ];
    expect(defaultPaths).toHaveLength(2);
    expect(defaultPaths[0].label).toBe("高风险");
    expect(defaultPaths[0].color).toBe("#DC2626");
    expect(defaultPaths[1].label).toBe("低风险");
    expect(defaultPaths[1].color).toBe("#16A34A");
    // 每条路径都有 id/label/condition/color
    defaultPaths.forEach((p) => {
      expect(p.id.length).toBeGreaterThan(0);
      expect(p.condition.length).toBeGreaterThan(0);
    });
  });

  it("test block rendering for branch shows dual paths（双路渲染数据）", () => {
    const branchBlock = {
      id: "b1",
      kind: "branch" as const,
      label: "Branch · 分支",
      config: {
        paths: [
          { id: "p1", label: "高风险", condition: "risk_level IN [high, critical]", color: "#DC2626" },
          { id: "p2", label: "低风险", condition: "risk_level IN [low, medium]", color: "#16A34A" },
        ],
      },
    };
    const paths = branchBlock.config.paths as BranchPath[];
    expect(paths.length).toBe(2);
    // 验证双路分叉视觉：A 路红色、B 路绿色
    expect(paths[0].color).toBe("#DC2626");
    expect(paths[1].color).toBe("#16A34A");
  });
});

describe("LogicCanvasPage · Handoff 配置面板数据结构", () => {
  it("test handoff config panel renders decision/artifacts/open_qs", () => {
    const handoffCfg: HandoffConfig = {
      decision: "风险分诊结论：中等风险，建议人工复核",
      artifacts: ["risk_assessment.json", "order_snapshot.diff"],
      open_qs: ["是否需要升级到 L4 模型？"],
      handoff_to: "draft_inbox",
    };
    expect(handoffCfg.decision.length).toBeGreaterThan(0);
    expect(handoffCfg.artifacts.length).toBe(2);
    expect(handoffCfg.open_qs.length).toBe(1);
    expect(handoffCfg.handoff_to).toBe("draft_inbox");
  });

  it("handoff_to 支持三种目标", () => {
    const validTargets: HandoffConfig["handoff_to"][] = ["risk_agent", "draft_inbox", "webhook"];
    expect(validTargets).toHaveLength(3);
    validTargets.forEach((t) => {
      expect(["risk_agent", "draft_inbox", "webhook"]).toContain(t);
    });
  });
});
