import { describe, expect, it } from "vitest";
import {
  STATS,
  PLATFORM_CASES,
  BLOCKERS,
  E2E_STEPS,
  STATUS_META,
  PRIORITY_VARIANT,
  renderStars,
  type PlatformCase,
  type Blocker,
} from "./IntegrationCasesPage";

/* ============================================================
 * 测试 1: 统计指标栏 — 6 个指标卡
 * ============================================================ */
describe("IntegrationCasesPage · STATS", () => {
  it("包含 6 个统计指标", () => {
    expect(STATS).toHaveLength(6);
  });

  it("每个指标包含完整字段（code/label/value/trend/hint）", () => {
    for (const s of STATS) {
      expect(s.code.length).toBeGreaterThan(0);
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.value.length).toBeGreaterThan(0);
      expect(s.trend.length).toBeGreaterThan(0);
      expect(typeof s.trendUp).toBe("boolean");
      expect(s.hint.length).toBeGreaterThan(0);
    }
  });

  it("包含「接入平台」「活跃连接器」「平均延迟」等关键指标", () => {
    const labels = STATS.map((s) => s.label);
    expect(labels).toContain("接入平台");
    expect(labels).toContain("活跃连接器");
    expect(labels).toContain("平均延迟");
    expect(labels).toContain("今日同步记录");
  });
});

/* ============================================================
 * 测试 2: 9 大平台案例卡片
 * ============================================================ */
describe("IntegrationCasesPage · PLATFORM_CASES", () => {
  it("包含 9 个平台案例", () => {
    expect(PLATFORM_CASES).toHaveLength(9);
  });

  it("包含微商城/淘宝/拼多多/京东/抖音/Shopify/Amazon 等核心平台", () => {
    const ids = PLATFORM_CASES.map((p) => p.id);
    expect(ids).toContain("weishop");
    expect(ids).toContain("taobao");
    expect(ids).toContain("pdd");
    expect(ids).toContain("jd");
    expect(ids).toContain("douyin");
    expect(ids).toContain("shopify");
    expect(ids).toContain("amazon");
  });

  it("每个案例有完整字段（id/name/protocol/stars/status/desc）", () => {
    for (const pc of PLATFORM_CASES) {
      expect(pc.id.length).toBeGreaterThan(0);
      expect(pc.name.length).toBeGreaterThan(0);
      expect(pc.protocol.length).toBeGreaterThan(0);
      expect(pc.stars).toBeGreaterThanOrEqual(1);
      expect(pc.stars).toBeLessThanOrEqual(5);
      expect(["live", "ref", "wip"]).toContain(pc.status);
      expect(pc.desc.length).toBeGreaterThan(0);
    }
  });

  it("7 个 live 状态平台", () => {
    const live = PLATFORM_CASES.filter((p) => p.status === "live");
    expect(live.length).toBe(7);
  });

  it("2 个 ref 状态平台（天猫/跨境Shopify）", () => {
    const refs = PLATFORM_CASES.filter((p) => p.status === "ref");
    expect(refs.length).toBe(2);
    expect(refs.map((r) => r.id).sort()).toEqual(["shopify-cross", "tmall"]);
  });

  it("Amazon 难度为 5 星", () => {
    const amazon = PLATFORM_CASES.find((p) => p.id === "amazon");
    expect(amazon?.stars).toBe(5);
  });
});

/* ============================================================
 * 测试 3: 10 个阻塞项看板
 * ============================================================ */
describe("IntegrationCasesPage · BLOCKERS", () => {
  it("包含 10 个阻塞项（G1-G10）", () => {
    expect(BLOCKERS).toHaveLength(10);
    const ids = BLOCKERS.map((b) => b.id);
    for (let i = 1; i <= 10; i++) {
      expect(ids).toContain(`G${i}`);
    }
  });

  it("每个阻塞项有完整字段（id/title/impact/priority/solution/eta）", () => {
    for (const b of BLOCKERS) {
      expect(b.id.length).toBeGreaterThan(0);
      expect(b.title.length).toBeGreaterThan(0);
      expect(b.impact.length).toBeGreaterThan(0);
      expect(["P0", "P1", "P2"]).toContain(b.priority);
      expect(b.solution.length).toBeGreaterThan(0);
      expect(b.eta.length).toBeGreaterThan(0);
    }
  });

  it("G1 和 G2 为 P0 优先级", () => {
    const g1 = BLOCKERS.find((b) => b.id === "G1");
    const g2 = BLOCKERS.find((b) => b.id === "G2");
    expect(g1?.priority).toBe("P0");
    expect(g2?.priority).toBe("P0");
  });

  it("PRIORITY_VARIANT 映射正确（P0→danger, P1→warning, P2→success）", () => {
    expect(PRIORITY_VARIANT.P0).toBe("danger");
    expect(PRIORITY_VARIANT.P1).toBe("warning");
    expect(PRIORITY_VARIANT.P2).toBe("success");
  });
});

/* ============================================================
 * 测试 4: 端到端链路 7 个步骤
 * ============================================================ */
describe("IntegrationCasesPage · E2E_STEPS", () => {
  it("包含 7 个步骤", () => {
    expect(E2E_STEPS).toHaveLength(7);
  });

  it("包含源平台 API / Connector / 数据同步 / Pipeline / Ontology / AIP / Action", () => {
    const labels = E2E_STEPS.map((s) => s.label);
    expect(labels).toContain("源平台 API");
    expect(labels).toContain("Connector");
    expect(labels).toContain("数据同步");
    expect(labels).toContain("Pipeline 变换");
    expect(labels).toContain("Ontology 物化");
    expect(labels).toContain("AIP 决策");
    expect(labels).toContain("Action 回写");
  });

  it("步骤序号从 1 到 7 连续递增", () => {
    E2E_STEPS.forEach((s, i) => {
      expect(s.step).toBe(i + 1);
    });
  });
});

/* ============================================================
 * 测试 5: 状态元信息和辅助函数
 * ============================================================ */
describe("IntegrationCasesPage · STATUS_META & helpers", () => {
  it("STATUS_META 包含 live/ref/wip 三种状态", () => {
    expect(STATUS_META.live).toBeTruthy();
    expect(STATUS_META.ref).toBeTruthy();
    expect(STATUS_META.wip).toBeTruthy();
    expect(STATUS_META.live.label).toContain("生产");
    expect(STATUS_META.ref.label).toContain("引用");
  });

  it("renderStars 根据数量渲染星级", () => {
    expect(renderStars(1)).toBe("⭐");
    expect(renderStars(3)).toBe("⭐⭐⭐");
    expect(renderStars(5)).toBe("⭐⭐⭐⭐⭐");
  });

  it("renderStars 对越界值做 clamp 处理", () => {
    expect(renderStars(0)).toBe("");
    expect(renderStars(-1)).toBe("");
    expect(renderStars(6)).toBe("⭐⭐⭐⭐⭐");
    expect(renderStars(100)).toBe("⭐⭐⭐⭐⭐");
  });
});

/* ============================================================
 * 测试 6: 类型完整性校验（编译时保障）
 * ============================================================ */
describe("IntegrationCasesPage · 类型一致性", () => {
  it("PlatformCase 类型可正确构造", () => {
    const pc: PlatformCase = {
      id: "test",
      name: "测试平台",
      icon: "🔧",
      iconBg: "#fff",
      iconColor: "#000",
      protocol: "REST",
      auth: "Token",
      stars: 2,
      status: "wip",
      tables: 10,
      apis: 20,
      syncs: 3,
      objects: 2,
      desc: "测试用例",
    };
    expect(pc.id).toBe("test");
  });

  it("Blocker 类型可正确构造", () => {
    const b: Blocker = {
      id: "GX",
      title: "测试阻塞",
      impact: ["平台A"],
      priority: "P2",
      solution: "方案",
      eta: "Week X",
    };
    expect(b.id).toBe("GX");
  });
});
