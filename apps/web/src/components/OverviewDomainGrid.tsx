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
        hint="入口只有「应用列表」；运营台 / 知识图谱 / Buddy 都是列表里打开的 Module。"
      >
        <BpMetricGrid
          items={[
            { label: "Module", value: m?.modules ?? "…", tone: "muted" },
            { label: "WorkOrder", value: m?.workOrders ?? "…", tone: (m?.workOrders ?? 0) > 0 ? "ok" : "warn" },
            { label: "Evals", value: m?.evalsGreen ? "绿" : "—", tone: m?.evalsGreen ? "ok" : "warn" },
            { label: "入口", value: "应用列表", tone: "muted" },
          ]}
        />
        <BpHeroLink
          to="/workshop"
          eyebrow="唯一入口"
          title="应用列表"
          desc="按业务场景打开 Module · 含运营台、知识图谱、Buddy…"
          cta="进入列表 →"
          accent="sky"
        />
        <div className="bp-section-micro">列表内 Module 示例</div>
        <div className="bp-index-grid bp-index-grid-3">
          <BpIndexTile
            to="/workshop/inbox"
            eyebrow="运营 Inbox"
            title="运营台"
            desc="Filter · Table · Object View · 变量条"
            accent="sky"
          />
          <BpIndexTile
            to="/workshop/graph"
            eyebrow="本体前端"
            title="知识图谱"
            desc="Object+Link 图谱 · Wiki · Action"
            accent="violet"
          />
          <BpIndexTile
            to={
              m && m.workOrders > 0
                ? `/workshop/buddy?order=wo-1001&assist=1`
                : "/workshop/buddy"
            }
            eyebrow="AIP 嵌入"
            title="Buddy · Assist"
            desc="挂在任意 Module 侧栏 / 表旁"
            accent="amber"
          />
        </div>
        <BpLinkMini
          links={[
            { to: "/workshop/canvas", label: "画布编辑" },
            { to: "/workshop/cop", label: "态势大屏" },
            { to: "/workshop/publish", label: "发布入口" },
          ]}
        />
      </BpDomainPanel>

      <BpDomainPanel
        tone="aip"
        title="AIP 人工智能平台"
        hint="成熟度楼梯 → 工具面板 → Logic 三栏（试跑不落库）"
      >
        <BpMetricGrid
          items={[
            { label: "可路由模型", value: m?.models ?? "…", tone: "ok" },
            { label: "默认模型", value: m?.defaultModel ?? "…", tone: "muted" },
            { label: "Tools", value: m?.tools ?? "…", tone: "muted" },
            { label: "Draft 待审", value: m?.pendingDrafts ?? "…", tone: (m?.pendingDrafts ?? 0) > 0 ? "warn" : "ok" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/aip/maturity" eyebrow="成熟度" title="成熟度楼梯" desc="Threads → Agent → 自动化门控" accent="amber" />
          <BpIndexTile to="/aip/tools" eyebrow="工具" title="Agent 工具面板" desc="六类工具 · Wiki 子集" accent="amber" />
          <BpIndexTile to="/aip/logic" eyebrow="Logic" title="AIP Logic 画布" desc="三栏 · CoT Debugger" accent="amber" />
          <BpIndexTile to="/aip/capabilities" eyebrow="Capability" title="重能力接入" desc="Job · Session · MediaSet" accent="cyan" />
          <BpIndexTile to="/aip/model-providers" eyebrow="接入" title="模型供应商" desc="卡片 · Adapter" accent="amber" />
          <BpIndexTile to="/aip/model-router" eyebrow="路由" title="模型路由" desc="任务类型 · 预热熔断" accent="amber" />
          <BpIndexTile to="/aip/drafts" eyebrow="Draft" title="提案审批台" desc="HITL 批准/拒绝" accent="emerald" />
          <BpIndexTile to="/aip/evals" eyebrow="Evals" title="评测门控" desc="L4 须 Eval 绿" accent="amber" />
          <BpIndexTile to="/aip/lineage" eyebrow="谱系" title="决策谱系" desc="Draft → Action 复盘" accent="violet" />
          <BpIndexTile to="/aip/studio" eyebrow="Studio" title="Chatbot Studio" desc="Prompt · Agent 配置" accent="amber" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel tone="ontology" title="语义本体 Ontology · 数字孪生" hint="OKF → Overview → Funnel 水合 · 图谱健康">
        <BpMetricGrid
          items={[
            { label: "WorkOrder", value: m?.workOrders ?? "…", tone: (m?.workOrders ?? 0) > 0 ? "ok" : "warn" },
            { label: "OT 已发布", value: m?.objectTypePublished ? "是" : "否", tone: m?.objectTypePublished ? "ok" : "warn" },
            { label: "Draft 待审", value: m?.pendingDrafts ?? "…", tone: "muted" },
            { label: "图谱", value: "1-hop", tone: "muted" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/ontology" eyebrow="Discover" title="本体管理" desc="收藏 / 最近 / Object Type" accent="violet" />
          <BpIndexTile to="/ontology/funnel" eyebrow="Funnel" title="漏斗管道" desc="Changelog → Hydration" accent="violet" />
          <BpIndexTile to="/ontology/graph-health" eyebrow="健康" title="图谱健康度" desc="悬空 / 冲突 / 僵尸" accent="violet" />
          <BpIndexTile to="/ontology/wiki" eyebrow="Wiki" title="活知识 Wiki" desc="Object ↔ Wiki 双向" accent="violet" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel tone="data" title="数据集成 · 三阶段链路 + OKF">
        <BpMetricGrid
          items={[
            { label: "Dataset", value: m?.datasets ?? "…", tone: (m?.datasets ?? 0) > 0 ? "ok" : "warn" },
            { label: "Build", value: m?.builds ?? "…", tone: "muted" },
            { label: "WorkOrder", value: m?.workOrders ?? "…", tone: "muted" },
            { label: "种子", value: (m?.workOrders ?? 0) > 0 ? "已就绪" : "待初始化", tone: (m?.workOrders ?? 0) > 0 ? "ok" : "warn" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/data" eyebrow="① Connector" title="数据连接" desc="Sources · Router · Sync" accent="cyan" />
          <BpIndexTile to="/data/pipelines" eyebrow="② Pipeline" title="管道构建" desc="DAG 清洗" accent="cyan" />
          <BpIndexTile to="/data/datasets" eyebrow="③ Dataset" title="Lakehouse" desc="预览 · 历史" accent="cyan" />
          <BpIndexTile to="/ontology/okf-funnel" eyebrow="④ OKF" title="Funnel 映射" desc="列 → Property 映射" accent="emerald" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel tone="apollo" title="Apollo 交付引擎" hint="Hub · Release · 资产包 — Full 运行时与 Ferry 运维后置（本阶段不深化，仅保留导航）">
        <BpMetricGrid
          items={[
            { label: "Lite", value: "已就绪", tone: "ok" },
            { label: "Full 运行时", value: "后置", tone: "muted" },
            { label: "Ferry 现场", value: "后置", tone: "muted" },
            { label: "本波", value: "仅导航", tone: "muted" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-3">
          <BpIndexTile to="/apollo" eyebrow="Hub" title="舰队视图" desc="Spoke 健康 · Probe" accent="indigo" />
          <BpIndexTile to="/apollo/release" eyebrow="Release" title="发布通道" desc="rc → beta → stable" accent="indigo" />
          <BpIndexTile to="/apollo/assets" eyebrow="Assets" title="FDE 资产包" desc="SemVer · Channel" accent="indigo" />
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
