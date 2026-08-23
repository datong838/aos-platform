import { Link } from "react-router-dom";
import {
  BpDomainPanel,
  BpHeroLink,
  BpIndexTile,
} from "../pages/s2/blueprintUi";

/**
 * 226 · 严格对齐 foundry/html/index.html
 * 五段：工作台 → AIP footer-bar → 本体 → 数据集成 → 运维交付
 */
export function OverviewDomainGrid() {
  return (
    <>
      <BpDomainPanel
        tone="workshop"
        title="工作台"
        hint="入口只有「应用列表」；风险告警管理、智能助手、画布编辑等都是从列表里打开的模块，不是并列产品。"
      >
        <BpHeroLink
          to="/workshop"
          eyebrow="唯一入口"
          title="应用列表"
          desc="按业务场景打开模块 · 含风险告警管理、对象探索、智能助手…"
          cta="进入列表 →"
          accent="sky"
        />
        <div className="bp-section-micro">列表内模块示例（勿与入口平级理解）</div>
        <div className="bp-index-grid bp-index-grid-3">
          <BpIndexTile
            to="/workshop/orders"
            eyebrow="业务应用"
            title="订单管理系统"
            desc="统计卡片 · 订单列表 · 趋势图 · 详情面板"
            accent="sky"
          />
          <BpIndexTile
            to="/workshop/inbox"
            eyebrow="风控 Inbox"
            title="风险告警管理"
            desc="筛选 · 风控告警表格 · 对象详情 · 活动日志"
            accent="sky"
          />
          <BpIndexTile
            to="/workshop/buddy"
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
          ]}
        />
      </BpDomainPanel>

      <section className="bp-footer-bar" data-testid="overview-aip-bar">
        <h2 className="bp-domain-heading">
          AIP 人工智能平台 · k-LLM（核心调度） + Logic（编排引擎） + Agent Studio（Agent 开发工坊） + Assist（智能助手）
        </h2>
        <p className="hint">业务工作室 → 逻辑/工具 → 提案决策 → 模型配置</p>
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/aip/studio" eyebrow="Studio" title="Chatbot Studio" accent="amber" />
          <BpIndexTile to="/aip/logic" eyebrow="业务流程" title="业务逻辑编排" accent="amber" />
          <BpIndexTile to="/aip/tools" eyebrow="调用配置" title="智能体工具配置" accent="amber" />
          <BpIndexTile to="/aip/capabilities" eyebrow="Capabilities" title="智能体插件" accent="amber" />
        </div>
        <BpLinkMini
          muted
          links={[
            { to: "/aip/evals", label: "评测门控" },
            { to: "/aip/drafts", label: "草稿审批台" },
            { to: "/aip/lineage", label: "决策谱系" },
            { to: "/aip/model-providers", label: "模型供应商" },
            { to: "/aip/model-router", label: "模型路由" },
            { to: "/aip/maturity", label: "成熟度楼梯" },
          ]}
        />
      </section>

      <BpDomainPanel
        tone="ontology"
        title="本体 · 数字孪生"
        hint="Ontology Manager · Discover · 收藏 / 最近 / 重要 Object"
      >
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/ontology" eyebrow="Manager" title="本体管理" accent="violet" />
          <BpIndexTile to="/workshop/graph" eyebrow="Graph" title="对象探索" accent="violet" />
          <BpIndexTile to="/ontology/funnel" eyebrow="Runtime" title="Funnel 管道" accent="violet" />
          <BpIndexTile to="/ontology/wiki" eyebrow="Wiki" title="活知识 Wiki" accent="violet" />
          <BpIndexTile to="/ontology/graph-health" eyebrow="Health" title="图谱健康度" accent="violet" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel
        tone="data"
        title="数据集成"
        hint="连接器 → 管道 → 数据集 → 搭建 → 健康监控"
      >
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/data" eyebrow="Connect" title="数据源管理" accent="sky" />
          <BpIndexTile to="/data/pipelines" eyebrow="Pipeline" title="管道构建" accent="sky" />
          <BpIndexTile to="/data/datasets" eyebrow="Dataset" title="数据集预览" accent="sky" />
          <BpIndexTile to="/data/lineage" eyebrow="Lineage" title="数据沿袭" accent="sky" />
        </div>
      </BpDomainPanel>

      <BpDomainPanel
        tone="apollo"
        title="运维交付"
        hint="Hub 舰队 → Release 通道 → Spoke 详情 → Ferry 摆渡 → 资产包"
      >
        <div className="bp-index-grid bp-index-grid-4">
          <BpIndexTile to="/apollo" eyebrow="Hub" title="Hub 舰队" accent="emerald" />
          <BpIndexTile to="/apollo/release" eyebrow="Release" title="Release 通道" accent="emerald" />
          <BpIndexTile to="/apollo/ferry" eyebrow="Ferry" title="Ferry 摆渡" accent="emerald" />
          <BpIndexTile to="/apollo/config" eyebrow="Config" title="配置与密钥" accent="emerald" />
        </div>
      </BpDomainPanel>
    </>
  );
}

function BpLinkMini({
  links,
  muted,
}: {
  links: { to: string; label: string }[];
  muted?: boolean;
}) {
  return (
    <p className={`ov-link-mini${muted ? " is-muted" : ""}`}>
      {links.map((l, i) => (
        <span key={l.to}>
          {i > 0 ? <span className="ov-link-sep"> · </span> : null}
          <Link to={l.to}>{l.label}</Link>
        </span>
      ))}
    </p>
  );
}
