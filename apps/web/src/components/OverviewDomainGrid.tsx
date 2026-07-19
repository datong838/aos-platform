import { Link } from "react-router-dom";
import type { OverviewMetrics } from "../overviewMetrics";
import {
  BpDomainPanel,
  BpHeroLink,
  BpIndexTile,
  BpMetricGrid,
} from "../pages/s2/blueprintUi";

/** 79/97 · index.html 四域色带 + tile grid + live 指标 */
export function OverviewDomainGrid({ metrics }: { metrics: OverviewMetrics | null }) {
  const m = metrics;

  return (
    <>
      <BpDomainPanel
        tone="workshop"
        title="工作台"
        health={(m?.health === "ok" || m?.health === "healthy") ? "ok" : m ? "warn" : undefined}
        hint="入口只有「应用列表」；运营台 / 知识图谱 / 智能助手 都是列表里打开的模块，不是并列产品。"
      >
        <BpMetricGrid
          density="compact"
          items={[
            {
              label: "接口",
              value: m ? ((m.health === "ok" || m.health === "healthy") ? "正常" : m.health) : "…",
              tone: m && (m.health === "ok" || m.health === "healthy") ? "ok" : "warn",
            },
            {
              label: "默认大模型",
              value: m?.defaultModel || m?.sidecar || "…",
              tone: m?.sidecar === "agnes-openai-compatible" ? "ok" : "muted",
            },
            {
              label: "工单",
              value: m?.workOrders ?? "…",
              tone: (m?.workOrders ?? 0) > 0 ? "ok" : "warn",
            },
            {
              label: "评测",
              value: m?.evalsGreen ? (
                <span className="status-dot" title="评测通过" aria-label="评测通过" />
              ) : (
                "—"
              ),
              tone: m?.evalsGreen ? "ok" : "warn",
            },
          ]}
        />
        <BpHeroLink
          to="/workshop"
          eyebrow="唯一入口"
          title="应用列表"
          desc="按业务场景打开模块 · 含运营台、知识图谱、智能助手…"
          cta="进入列表 →"
          accent="sky"
        />
        <div className="bp-section-micro">列表内模块示例（勿与入口平级理解）</div>
        <div className="bp-index-grid bp-index-grid-3">
          <BpIndexTile
            to="/workshop/inbox"
            eyebrow="运营收件箱"
            title="运营台"
            desc="筛选 · 表格 · 对象视图 · 变量条"
            accent="sky"
          />
          <BpIndexTile
            to="/workshop/graph"
            eyebrow="本体前端"
            title="知识图谱"
            desc="对象+关系图谱 · Wiki · 动作"
            accent="violet"
          />
          <BpIndexTile
            to={
              m && m.workOrders > 0
                ? `/workshop/buddy?order=wo-1001&assist=1`
                : "/workshop/buddy"
            }
            eyebrow="智能嵌入"
            title="智能助手"
            desc="挂在任意模块侧栏 / 表旁"
            accent="amber"
          />
        </div>
        <BpLinkMini
          links={[
            { to: "/workshop/canvas", label: "画布编辑" },
            { to: "/workshop/cop", label: "态势大屏" },
            { to: "/workshop/publish", label: "发布入口" },
            { to: "/aip/model-router", label: `模型路由${m?.models != null ? ` · ${m.models}` : ""}` },
            { to: "/aip/tools", label: `插件${m?.plugins != null ? ` · ${m.plugins}` : ""}` },
            {
              to: "/aip/drafts",
              label: m?.pendingDrafts ? `提案待审 · ${m.pendingDrafts}` : "提案审批",
            },
          ]}
        />
      </BpDomainPanel>

      <BpDomainPanel
        tone="aip"
        title="AIP 人工智能平台 · k-LLM（核心调度） + Logic（编排引擎） + Agent Studio（Agent 开发工坊） + Assist（智能助手）"
        hint="业务工作室 → 逻辑/工具 → 提案决策 → 模型配置"
      >
        <BpMetricGrid
          density="compact"
          items={[
            { label: "可路由模型", value: m?.models ?? "…", tone: "ok" },
            { label: "工具", value: m?.tools ?? "…", tone: "muted" },
            { label: "插件", value: m?.plugins ?? "…", tone: "muted" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4">
          {/* 38 v1.5 · 业务 → 决策 → 配置；成熟度不放首位 */}
          <BpIndexTile to="/aip/studio" eyebrow="工作室" title="对话工作室" desc="提示词 · 智能体配置" accent="amber" />
          <BpIndexTile to="/aip/logic" eyebrow="逻辑" title="AIP 逻辑画布" desc="三栏 · 思维链调试" accent="amber" />
          <BpIndexTile to="/aip/tools" eyebrow="工具" title="智能体管理工作台" desc="六类工具 · Wiki 子集" accent="amber" />
          <BpIndexTile to="/aip/capabilities" eyebrow="能力" title="重能力接入" desc="任务 · 会话 · 媒体集" accent="cyan" />
          <BpIndexTile to="/aip/drafts" eyebrow="提案" title="提案审批台" desc="人工批准 / 拒绝" accent="emerald" />
          <BpIndexTile to="/aip/evals" eyebrow="评测" title="评测门控" desc="高级自动化须评测通过" accent="amber" />
          <BpIndexTile to="/aip/lineage" eyebrow="谱系" title="决策谱系" desc="提案 → 动作 复盘" accent="violet" />
          <BpIndexTile to="/aip/model-providers" eyebrow="接入" title="大模型接入(插件)" desc="卡片 · 适配器" accent="amber" />
          <BpIndexTile to="/aip/model-router" eyebrow="路由" title="模型路由" desc="任务类型 · 预热熔断" accent="amber" />
          <BpIndexTile to="/aip/maturity" eyebrow="成熟度" title="成熟度楼梯" desc="对话线程 → 智能体 → 自动化门控" accent="amber" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel
        tone="ontology"
        title="语义本体 Ontology · 数字孪生"
        hint="OKF → 总览 → 漏斗水合 · 图谱健康"
      >
        <BpMetricGrid
          density="compact"
          items={[
            {
              label: "对象类型",
              value: m?.objectTypePublished ? "已发布" : "未发布",
              tone: m?.objectTypePublished ? "ok" : "warn",
            },
            { label: "图谱", value: "一跳邻接", tone: "muted" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/ontology" eyebrow="发现" title="本体管理" desc="收藏 / 最近 / 对象类型" accent="violet" />
          <BpIndexTile to="/ontology/funnel" eyebrow="漏斗" title="漏斗管道" desc="变更日志 → 水合" accent="violet" />
          <BpIndexTile to="/ontology/graph-health" eyebrow="健康" title="图谱健康度" desc="悬空 / 冲突 / 僵尸" accent="violet" />
          <BpIndexTile to="/ontology/wiki" eyebrow="Wiki" title="活知识 Wiki" desc="对象 ↔ Wiki 双向" accent="violet" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel tone="data" title="数据集成 · 三阶段链路 + OKF">
        <BpMetricGrid
          density="compact"
          items={[
            {
              label: "数据集",
              value: m?.datasets ?? "…",
              tone: (m?.datasets ?? 0) > 0 ? "ok" : "warn",
            },
            { label: "构建", value: m?.builds ?? "…", tone: "muted" },
            {
              label: "工单",
              value: m?.workOrders ?? "…",
              tone: (m?.workOrders ?? 0) > 0 ? "ok" : "warn",
            },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/data" eyebrow="① 连接器" title="数据连接" desc="数据源 · 路由 · 同步" accent="cyan" />
          <BpIndexTile to="/data/pipelines" eyebrow="② 管道" title="管道构建" desc="流程清洗" accent="cyan" />
          <BpIndexTile to="/data/datasets" eyebrow="③ 数据集" title="数据湖仓" desc="预览 · 历史" accent="cyan" />
          <BpIndexTile to="/ontology/okf-funnel" eyebrow="④ OKF" title="漏斗映射" desc="列 → 属性 映射" accent="emerald" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel
        tone="apollo"
        title="Apollo 交付引擎"
        hint="枢纽 · 发布 · 资产包"
      >
        <BpMetricGrid
          density="compact"
          items={[
            { label: "轻量版", value: "已就绪", tone: "ok" },
            { label: "完整运行时", value: "规划中", tone: "muted" },
            { label: "现场摆渡", value: "规划中", tone: "muted" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-3">
          <BpIndexTile to="/apollo" eyebrow="枢纽" title="舰队视图" desc="节点健康 · 探活" accent="indigo" />
          <BpIndexTile to="/apollo/release" eyebrow="发布" title="发布通道" desc="预发 → 公测 → 稳定" accent="indigo" />
          <BpIndexTile to="/apollo/assets" eyebrow="资产" title="现场资产包" desc="版本号 · 通道" accent="indigo" />
        </div>
      </BpDomainPanel>
    </>
  );
}

function BpLinkMini({ links }: { links: { to: string; label: string }[] }) {
  return (
    <p className="muted" style={{ marginTop: "0.65rem", fontSize: "0.7rem" }}>
      {links.map((l, i) => (
        <span key={l.to}>
          {i > 0 ? " · " : null}
          <Link to={l.to}>{l.label}</Link>
        </span>
      ))}
    </p>
  );
}
