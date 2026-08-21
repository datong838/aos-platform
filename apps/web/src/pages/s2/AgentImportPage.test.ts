import { describe, expect, it } from "vitest";
import {
  ADAPTER_TYPES,
  ADAPTER_DETAILS,
  DEFAULT_TOOL_MAPPINGS,
  DEFAULT_PERMISSION_MAPPINGS,
  computeMappingStats,
  getAdapterDetail,
  INITIAL_AGENT_IMPORT_SOURCE,
  agentImportStateLabel,
  canAdvanceAgentImport,
  type AdapterType,
} from "./AgentImportPage";

describe("AgentImportPage · 真实初始态", () => {
  it("不预填第三方仓库、路径或业务能力", () => {
    expect(INITIAL_AGENT_IMPORT_SOURCE).toEqual({
      githubUrl: "",
      agentPath: "",
      branch: "main",
      capabilityName: "",
      capabilityDisplayName: "",
      capabilityDescription: "",
    });
  });

  it("没有 exact Scan Receipt 时禁止进入后续步骤", () => {
    expect(canAdvanceAgentImport(undefined)).toBe(false);
    expect(canAdvanceAgentImport("")).toBe(false);
    expect(canAdvanceAgentImport("scan-receipt-1")).toBe(true);
  });

  it("门禁错误显示受阻而不是误报导入失败", () => {
    expect(agentImportStateLabel({ success: false, importing: false, error: null })).toBe("未开始");
    expect(agentImportStateLabel({ success: false, importing: false, error: "缺少 Scan Receipt" })).toBe("受阻");
    expect(agentImportStateLabel({ success: false, importing: true, error: null })).toBe("导入中");
    expect(agentImportStateLabel({ success: true, importing: false, error: null })).toBe("成功");
  });
});

describe("AgentImportPage · ADAPTER_TYPES", () => {
  it("包含 5 种 Adapter 类型", () => {
    expect(ADAPTER_TYPES.length).toBe(5);
  });

  it("每个 Adapter 有 key/label/desc/tag/color", () => {
    for (const a of ADAPTER_TYPES) {
      expect(a.key.length).toBeGreaterThan(0);
      expect(a.label.length).toBeGreaterThan(0);
      expect(a.desc.length).toBeGreaterThan(0);
      expect(a.tag.length).toBeGreaterThan(0);
      expect(a.color.length).toBeGreaterThan(0);
    }
  });

  it("process 是推荐项", () => {
    const process = ADAPTER_TYPES.find((a) => a.key === "process");
    expect(process?.recommended).toBe(true);
  });
});

describe("AgentImportPage · ADAPTER_DETAILS", () => {
  it("包含全部 5 种 Adapter 详情", () => {
    expect(ADAPTER_DETAILS.http).toBeTruthy();
    expect(ADAPTER_DETAILS.process).toBeTruthy();
    expect(ADAPTER_DETAILS.mcp).toBeTruthy();
    expect(ADAPTER_DETAILS.docker).toBeTruthy();
    expect(ADAPTER_DETAILS.session).toBeTruthy();
  });

  it("每个 Adapter 详情有 schema 数组", () => {
    for (const key of Object.keys(ADAPTER_DETAILS) as AdapterType[]) {
      const detail = ADAPTER_DETAILS[key];
      expect(Array.isArray(detail.schema)).toBe(true);
      expect(detail.schema.length).toBeGreaterThan(0);
      for (const f of detail.schema) {
        expect(f.field.length).toBeGreaterThan(0);
        expect(f.type.length).toBeGreaterThan(0);
        expect(typeof f.required).toBe("boolean");
      }
    }
  });

  it("每个 Adapter 详情有 example 字符串", () => {
    for (const key of Object.keys(ADAPTER_DETAILS) as AdapterType[]) {
      expect(ADAPTER_DETAILS[key].example.length).toBeGreaterThan(0);
    }
  });

  it("每个 Adapter 详情有 compatibility 数组", () => {
    for (const key of Object.keys(ADAPTER_DETAILS) as AdapterType[]) {
      const detail = ADAPTER_DETAILS[key];
      expect(Array.isArray(detail.compatibility)).toBe(true);
      expect(detail.compatibility.length).toBeGreaterThan(0);
      for (const c of detail.compatibility) {
        expect(["pass", "warn", "fail"]).toContain(c.status);
      }
    }
  });

  it("每个 Adapter 详情有 latency 和 isolation", () => {
    for (const key of Object.keys(ADAPTER_DETAILS) as AdapterType[]) {
      expect(ADAPTER_DETAILS[key].latency.length).toBeGreaterThan(0);
      expect(ADAPTER_DETAILS[key].isolation.length).toBeGreaterThan(0);
    }
  });
});

describe("AgentImportPage · getAdapterDetail", () => {
  it("返回正确的 Adapter 详情", () => {
    const httpDetail = getAdapterDetail("http");
    expect(httpDetail).toBe(ADAPTER_DETAILS.http);
  });

  it("process 详情有正确的字段", () => {
    const processDetail = getAdapterDetail("process");
    expect(processDetail.schema.some((f) => f.field === "entrypoint")).toBe(true);
    expect(processDetail.schema.some((f) => f.field === "runtime")).toBe(true);
  });

  it("docker 详情有 GPU 字段", () => {
    const dockerDetail = getAdapterDetail("docker");
    expect(dockerDetail.schema.some((f) => f.field === "gpu")).toBe(true);
  });
});

describe("AgentImportPage · DEFAULT_TOOL_MAPPINGS", () => {
  it("至少 4 个工具映射", () => {
    expect(DEFAULT_TOOL_MAPPINGS.length).toBeGreaterThanOrEqual(4);
  });

  it("每个映射有 sourceTool 和 targetToolId", () => {
    for (const m of DEFAULT_TOOL_MAPPINGS) {
      expect(m.sourceTool.length).toBeGreaterThan(0);
      expect(typeof m.targetToolId).toBe("string");
      expect(["pass", "warn", "fail"]).toContain(m.status);
      expect(typeof m.autoMapped).toBe("boolean");
    }
  });

  it("包含至少 1 个自动映射", () => {
    expect(DEFAULT_TOOL_MAPPINGS.some((m) => m.autoMapped)).toBe(true);
  });

  it("包含至少 1 个失败映射（需要手动配置）", () => {
    expect(DEFAULT_TOOL_MAPPINGS.some((m) => m.status === "fail")).toBe(true);
  });
});

describe("AgentImportPage · DEFAULT_PERMISSION_MAPPINGS", () => {
  it("至少 3 个权限映射", () => {
    expect(DEFAULT_PERMISSION_MAPPINGS.length).toBeGreaterThanOrEqual(3);
  });

  it("每个权限映射有 source/target/granted", () => {
    for (const p of DEFAULT_PERMISSION_MAPPINGS) {
      expect(p.sourcePermission.length).toBeGreaterThan(0);
      expect(p.targetPermission.length).toBeGreaterThan(0);
      expect(typeof p.granted).toBe("boolean");
    }
  });

  it("包含已授权和未授权项", () => {
    expect(DEFAULT_PERMISSION_MAPPINGS.some((p) => p.granted)).toBe(true);
    expect(DEFAULT_PERMISSION_MAPPINGS.some((p) => !p.granted)).toBe(true);
  });
});

describe("AgentImportPage · computeMappingStats", () => {
  it("返回 total/autoMapped/pass/warn/fail", () => {
    const stats = computeMappingStats(DEFAULT_TOOL_MAPPINGS);
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("autoMapped");
    expect(stats).toHaveProperty("pass");
    expect(stats).toHaveProperty("warn");
    expect(stats).toHaveProperty("fail");
  });

  it("total 等于映射总数", () => {
    const stats = computeMappingStats(DEFAULT_TOOL_MAPPINGS);
    expect(stats.total).toBe(DEFAULT_TOOL_MAPPINGS.length);
  });

  it("pass + warn + fail = total", () => {
    const stats = computeMappingStats(DEFAULT_TOOL_MAPPINGS);
    expect(stats.pass + stats.warn + stats.fail).toBe(stats.total);
  });

  it("空数组返回全 0", () => {
    const stats = computeMappingStats([]);
    expect(stats.total).toBe(0);
    expect(stats.autoMapped).toBe(0);
  });
});
