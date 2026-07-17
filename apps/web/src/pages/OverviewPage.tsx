import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, API_BASE } from "../api/client";
import { PageChrome } from "../components/PageChrome";

type Counts = { modules: number; models: number; plugins: number; tools: number };

/** AI OS control plane — not just a shell. */
export function OverviewPage() {
  const [health, setHealth] = useState("…");
  const [counts, setCounts] = useState<Counts>({ modules: 0, models: 0, plugins: 0, tools: 0 });
  const [sidecar, setSidecar] = useState("…");

  useEffect(() => {
    apiGet<{ status: string }>("/v1/health")
      .then((j) => setHealth(j.status))
      .catch((e) => setHealth(String(e)));
    Promise.all([
      apiGet<{ items: unknown[] }>("/v1/modules"),
      apiGet<{ items: unknown[]; sidecar?: string }>("/v1/aip/models"),
      apiGet<{ items: unknown[]; totals?: { all: number } }>("/v1/plugins"),
      apiGet<{ items: unknown[] }>("/v1/aip/tools"),
    ])
      .then(([mod, models, plugins, tools]) => {
        setCounts({
          modules: mod.items.length,
          models: models.items.length,
          plugins: plugins.totals?.all ?? plugins.items.length,
          tools: tools.items.length,
        });
        setSidecar(models.sidecar || "—");
      })
      .catch(() => undefined);
  }, []);

  return (
    <PageChrome
      title="AI操作系统"
      lede="数据操作系统 · 本体数字孪生 · AIP · 工作台 — 模型 / 插件 / 模块可运营，不只是壳。"
    >
      <p className="status-pill" style={{ marginBottom: "1rem" }}>
        <span className="status-dot" />
        {API_BASE} · health: {health} · LLM: {sidecar}
      </p>

      <section className="panel aip" style={{ marginBottom: "1.5rem" }}>
        <h2>操作系统控制面</h2>
        <p className="hint">模型可路由 · 插件可调用 · 模块可打开</p>
        <div className="tile-grid cols-4">
          <Link to="/aip/model-router" className="tile">
            <div className="eyebrow">模型</div>
            <div className="title">{counts.models}</div>
            <p className="desc">可路由模型 · 试聊</p>
          </Link>
          <Link to="/aip/tools" className="tile">
            <div className="eyebrow">插件 / Tools</div>
            <div className="title">{counts.plugins}</div>
            <p className="desc">tools {counts.tools} · parsers/sources/caps</p>
          </Link>
          <Link to="/workshop" className="tile">
            <div className="eyebrow">模块</div>
            <div className="title">{counts.modules}</div>
            <p className="desc">应用列表 · entryPath 绑定</p>
          </Link>
          <Link to="/aip/capabilities" className="tile">
            <div className="eyebrow">重能力</div>
            <div className="title">Job</div>
            <p className="desc">产物 → MediaSet</p>
          </Link>
        </div>
      </section>

      <section className="panel workshop">
        <h2>客户演示（TB.*）</h2>
        <p className="hint">本地可部署故事线 · Apollo 运维后置 · 不对标 Jupyter</p>
        <Link to="/demo" className="tile-hero">
          <div>
            <div className="eyebrow">15～20 分钟</div>
            <div className="title">WorkOrder 演示导航</div>
            <p className="desc">数据 → 本体 → 写回 → 画布 → Buddy → 治理</p>
          </div>
          <span className="aos-muted">打开演示 →</span>
        </Link>
      </section>

      <section className="panel workshop">
        <h2>工作台</h2>
        <p className="hint">
          入口只有「应用列表」；运营台 / 知识图谱 / Buddy 都是列表里打开的 Module。
        </p>
        <Link to="/workshop" className="tile-hero">
          <div>
            <div className="eyebrow">唯一入口</div>
            <div className="title">应用列表</div>
            <p className="desc">按业务场景打开 Module · 含运营台、知识图谱、Buddy…</p>
          </div>
          <span className="aos-muted">进入列表 →</span>
        </Link>
        <div className="tile-grid">
          <Link to="/workshop/inbox" className="tile">
            <div className="eyebrow">运营 Inbox</div>
            <div className="title">运营台</div>
            <p className="desc">Filter · Table · Object View · 变量条</p>
          </Link>
          <Link to="/workshop/graph" className="tile">
            <div className="eyebrow">本体前端</div>
            <div className="title">知识图谱</div>
            <p className="desc">Object+Link 图谱 · Wiki · Action</p>
          </Link>
          <Link to="/workshop/buddy" className="tile">
            <div className="eyebrow">AIP 嵌入</div>
            <div className="title">Buddy · Assist</div>
            <p className="desc">挂在任意 Module 侧栏 / 表旁</p>
          </Link>
        </div>
      </section>

      <section className="panel aip">
        <h2>AIP 人工智能平台</h2>
        <p className="hint">k-LLM · Logic · Agent Studio · Assist · Draft HITL</p>
        <div className="tile-grid cols-4">
          <Link to="/aip/drafts" className="tile">
            <div className="eyebrow">HITL</div>
            <div className="title">Draft 审批台</div>
            <p className="desc">提案批准 → 写生产</p>
          </Link>
          <Link to="/aip/logic" className="tile">
            <div className="eyebrow">Logic</div>
            <div className="title">逻辑画布</div>
            <p className="desc">dryRun 不落库</p>
          </Link>
          <Link to="/aip/studio" className="tile">
            <div className="eyebrow">Studio</div>
            <div className="title">Chatbot Studio</div>
            <p className="desc">Agent · 真 Tool 执行</p>
          </Link>
          <Link to="/aip/capabilities" className="tile">
            <div className="eyebrow">Capability</div>
            <div className="title">重能力接入</div>
            <p className="desc">Job · MediaSet</p>
          </Link>
        </div>
      </section>

      <section className="panel ontology">
        <h2>本体 · 数据 · Apollo</h2>
        <div className="tile-grid">
          <Link to="/ontology" className="tile">
            <div className="eyebrow">L2</div>
            <div className="title">本体管理</div>
            <p className="desc">Object Type · Link · Wiki</p>
          </Link>
          <Link to="/data" className="tile">
            <div className="eyebrow">L1</div>
            <div className="title">数据连接</div>
            <p className="desc">Pipeline · 解析插件</p>
          </Link>
          <Link to="/apollo" className="tile">
            <div className="eyebrow">交付</div>
            <div className="title">Apollo Hub</div>
            <p className="desc">Spoke · Asset Bundle</p>
          </Link>
        </div>
      </section>
    </PageChrome>
  );
}
