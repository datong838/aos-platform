import { act } from "react"; import { createRoot, type Root } from "react-dom/client"; import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"; import type { AnalystViewResponse, LearningScenarioContribution } from "../../api/ecommerceWorkshop"; import { AnalystPage } from "./AnalystPage";
import { CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS, OPEN_BUSINESS_INVESTIGATION_COMMAND_FEATURE, OPEN_BUSINESS_INVESTIGATION_READ_FEATURE, resolveBusinessInvestigationFeatureFlags } from "./businessInvestigationFeatureFlags";
const ids = ["overview", "drivers", "diagnosis", "plan", "effects", "evidence", "quality"] as const; const axes = ["metric_query", "model", "eval", "plan_materialization", "professional_handoff"] as const; const cutoff="2026-08-24T08:00:00Z";
const emptyInvestigationClient = { listCases: vi.fn().mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 }), listRuns: vi.fn().mockResolvedValue({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [], count: 0 }) };
const blocked: AnalystViewResponse={schemaVersion:"aos.ecommerce-workshop.analyst-view/v1",tenant:{orgId:"org-org",projectId:"dev-project"},resourceRevision:1,evaluatedAt:cutoff,dataCutoff:cutoff,readiness:"degraded",views:ids.map((viewId)=>{const blocker={code:`ANALYST_${viewId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`,dependency:viewId,requiredAction:"attach exact refs"};return{viewId,status:"blocked",resourceRevision:1,dataCutoff:cutoff,readinessAxes:axes.map((axis)=>({axis,status:"blocked",exactRef:null,blockers:[blocker]})),metrics:[],authorityRefs:[],blockers:[blocker],countLedger:{denominator:0,ready:0,unknown:0,blocked:0,conflict:0}}}),page:{limit:100,count:0,hasMore:false,nextCursor:null}}; const emptyJobs=()=>Promise.resolve({tenant:{orgId:"org-org",projectId:"dev-project"},items:[],count:0});
const scenarioBlocker={code:"GROWTH_PLAN_EXACT_ROOT_REQUIRED",dependency:"growth-plan",requiredAction:"provide exact refs"}; const scenarioIds=["insight","growth_plan","content","creator","media","publication","effect_review","memory_candidate"] as const; const outcomeIds=["provider_applied","usage_settled","effect_mature","memory_governed"] as const; const blockedV2:AnalystViewResponse={...blocked,schemaVersion:"aos.ecommerce-workshop.analyst-view/v2",growthScenario:{schemaVersion:"aos.ecommerce-workshop.growth-scenario/v1",status:"blocked",rootPlanRef:null,scenarioBindingHash:null,evaluatedAt:cutoff,stages:scenarioIds.map((stageId)=>({stageId,status:"blocked",exactRefs:[],contribution:"等待 exact authority",blockers:[scenarioBlocker]})),ledger:{tasksExpected:0,tasksObserved:0,handoffsExpected:0,handoffsObserved:0,outcomesExpected:4,outcomesReady:0,outcomesBlocked:4,outcomesUnknown:0},outcomeAxes:outcomeIds.map((axisId)=>({axisId,status:"blocked",exactRef:null,blocker:scenarioBlocker})),blockers:[scenarioBlocker],commands:{materialize:false,dispatch:false,publish:false,promoteMemory:false},externalEffectsAllowed:false}};
const hash=`sha256:${"a".repeat(64)}`; const learningRef=(resourceType:string,resourceId:string)=>({resourceType,resourceId,revision:1,contentHash:hash}); const learningBlocker={code:"REVOCATION_IMPACT_REVIEW_REQUIRED",dependency:"learning",requiredAction:"review impact refs"}; const learningStages=["effect_review","maturity","memory_candidate","governance","promotion","knowledge_query","revocation_impact"] as const; const learningAxes=["effect_mature","candidate_governed","knowledge_promoted","future_query_authorized","revocation_impact_recorded"] as const; const learning:LearningScenarioContribution={schemaVersion:"aos.ecommerce-workshop.learning-scenario/v1",status:"blocked",rootEffectReviewRef:learningRef("EffectReviewRevision","review-1"),maturityPolicyRef:learningRef("EffectMaturityPolicyRevision","policy-1"),learningBindingHash:"b".repeat(64),composition:{atomicSkillRefs:[learningRef("SkillRevision","review-outcomes"),learningRef("SkillRevision","govern-knowledge")],logicRevisionRef:learningRef("LogicRevision","effect-to-governed-knowledge"),roleBindings:[{roleRef:learningRef("AgentTemplate","analyst"),assigneeRef:learningRef("AgentInstance","analyst-1"),skillBindingRef:learningRef("SkillBinding","learning-binding-1")}]},evaluatedAt:cutoff,stages:learningStages.map((stageId,index)=>index===6?{stageId,status:"unknown",exactRefs:[],contribution:"等待撤销影响复核",blockers:[learningBlocker]}:{stageId,status:"ready",exactRefs:[learningRef(index===0?"EffectReviewRevision":"LearningStageRevision",stageId)],contribution:`stage ${stageId}`,blockers:[]}),ledger:{reviewsExpected:1,reviewsObserved:1,candidatesExpected:1,candidatesObserved:1,promotionsExpected:1,promotionsObserved:1,citationsExpected:1,citationsObserved:1,historicalExposures:2,retainedExposures:2,impactRefsExpected:1,impactRefsObserved:0},outcomeAxes:learningAxes.map((axisId,index)=>index===4?{axisId,status:"unknown",exactRef:null,blocker:learningBlocker}:{axisId,status:"ready",exactRef:learningRef("LearningOutcomeRevision",axisId),blocker:null}),blockers:[learningBlocker],commands:{submitCandidate:false,approveCandidate:false,promoteCandidate:false,publishWiki:false,revokeKnowledge:false},externalEffectsAllowed:false};
describe("AnalystPage",()=>{let host:HTMLDivElement;let root:Root;beforeEach(()=>{host=document.createElement("div");document.body.appendChild(host);root=createRoot(host)});afterEach(()=>{act(()=>root.unmount());host.remove()});it("展示七视图、专业贡献链且无分析写入口",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blocked)}} loadAsyncJobs={emptyJobs}/>));expect(host.querySelectorAll('[role="tab"]')).toHaveLength(7);expect(host.textContent).toContain("Observation ≠ attribution ≠ causal claim");expect(host.querySelector('[aria-label="专业贡献归因路径"]')).not.toBeNull();expect(host.textContent).toContain("原子技能");expect(host.textContent).toContain("逻辑编排");expect(host.textContent).toContain("数字同事");expect(host.textContent).toContain("工作台贡献");expect(host.textContent).toContain("保持 unknown");expect(host.textContent).toContain("关键假设和不确定性");expect(host.querySelector('[aria-label="统一异步任务抽屉"]')).not.toBeNull();expect(host.textContent).not.toMatch(/保存分析|新建计划|批准并物化|派发|晋升记忆/)});it("七个经营视图分别呈现视觉稿对应的信息架构且保持可信空",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blocked)}} loadAsyncJobs={emptyJobs}/>));const select=(label:string)=>{const tab=Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item)=>item.textContent?.includes(label));act(()=>tab?.click())};expect(host.querySelectorAll(".analyst-exact-panel.is-overview .analyst-exact-cadence article")).toHaveLength(6);select("驱动因素");expect(host.querySelectorAll(".analyst-exact-panel.is-drivers .analyst-exact-driver-cards > article")).toHaveLength(3);select("问题诊断");expect(host.querySelectorAll(".analyst-exact-panel.is-diagnosis .analyst-exact-diagnosis-table tbody tr")).toHaveLength(6);expect(host.querySelector(".analyst-exact-panel.is-diagnosis")?.textContent).not.toMatch(/\b0(?:\.0+)?%\b/);select("增长计划");expect(host.querySelectorAll(".analyst-exact-panel.is-plan .analyst-exact-lifecycle span")).toHaveLength(5);select("效果复盘");expect(host.querySelectorAll(".analyst-exact-panel.is-effects .analyst-exact-review-list > section")).toHaveLength(3);select("证据链");expect(host.querySelectorAll(".analyst-exact-panel.is-evidence .analyst-exact-evidence-nodes > section")).toHaveLength(4);select("数据质量");expect(host.querySelectorAll(".analyst-exact-panel.is-quality .analyst-exact-quality-grid > article, .analyst-exact-panel.is-quality .analyst-exact-quality-grid > aside")).toHaveLength(4);expect(host.textContent).toContain("未知不显示为 0");expect(Array.from(host.querySelectorAll("button")).map((item)=>item.textContent).join(" ")).not.toMatch(/保存|提交|执行|发布|物化|派发|晋升/)});it("切换质量视图不制造零值",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blocked)}} loadAsyncJobs={emptyJobs}/>));const tab=Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item)=>item.textContent?.includes("数据质量"));act(()=>tab?.click());expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("当前没有可挂接的经营指标");expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("披露分母、缺失、冲突");const ledger=host.querySelector('[aria-label="分母与新鲜度"]');expect(ledger?.textContent).toContain("未知");expect(ledger?.textContent).not.toMatch(/\b0\b/)});it("支持方向键沿七视图循环",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blocked)}} loadAsyncJobs={emptyJobs}/>));const tabs=host.querySelectorAll<HTMLButtonElement>('[role="tab"]');act(()=>tabs[0]?.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight",bubbles:true})));const panel=host.querySelector<HTMLElement>('[role="tabpanel"]');expect(panel?.getAttribute("aria-label")).toBe("驱动因素");expect(tabs[1]?.tabIndex).toBe(0);expect(tabs[1]?.getAttribute("aria-controls")).toBe(panel?.id);expect(panel?.getAttribute("aria-labelledby")).toBe(tabs[1]?.id)})});

describe("Analyst quality count semantics", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("ready 的可信空账本保留真实零值", async () => {
    const response: AnalystViewResponse = {
      ...blocked,
      views: blocked.views.map((view) => view.viewId === "quality" ? {
        ...view,
        status: "ready",
        blockers: [],
        readinessAxes: view.readinessAxes.map((axis) => ({ ...axis, status: "ready", blockers: [] })),
      } : view),
    };
    await act(async () => root.render(<AnalystPage client={{ getAnalystView: vi.fn().mockResolvedValue(response) }} loadAsyncJobs={emptyJobs} />));
    const tab = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item) => item.textContent?.includes("数据质量"));
    act(() => tab?.click());
    const ledger = host.querySelector('[aria-label="分母与新鲜度"]');
    expect(ledger?.textContent).not.toContain("未知");
    expect(Array.from(ledger?.querySelectorAll("dd") ?? []).map((item) => item.textContent)).toEqual(["0", "0", "0"]);
  });
});

describe("AnalystPage GrowthPlan scenario",()=>{let host:HTMLDivElement;let root:Root;beforeEach(()=>{host=document.createElement("div");document.body.appendChild(host);root=createRoot(host)});afterEach(()=>{act(()=>root.unmount());host.remove()});it("展示八阶段四轴守恒且不产生跨域写入口",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blockedV2)}} loadAsyncJobs={emptyJobs}/>));expect(host.querySelector('[aria-label="GrowthPlan跨域同链贡献"]')).not.toBeNull();const supplemental=host.querySelector<HTMLDetailsElement>(".analyst-supplemental-context");expect(supplemental?.open).toBe(false);expect(supplemental?.querySelector("summary")?.textContent).toContain("正式业务能力 → 数字同事 → 工作台贡献");expect(host.textContent).toContain("洞察 → GrowthPlan → 内容 → 达人 → 媒体 → 发布 → 复盘");expect(host.textContent).toContain("原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献");expect(host.textContent).toContain("Provider applied、Usage settled、Effect mature、Memory governed 四轴独立");expect(host.textContent).toContain("不自动晋升 Wiki");const buttons=Array.from(host.querySelectorAll("button")).map((item)=>item.textContent).join(" ");expect(buttons).not.toMatch(/开始执行|立即发布|物化任务|晋升 Wiki/)});});

describe("AnalystPage learning governance scenario",()=>{let host:HTMLDivElement;let root:Root;beforeEach(()=>{host=document.createElement("div");document.body.appendChild(host);root=createRoot(host)});afterEach(()=>{act(()=>root.unmount());host.remove()});it("展示七阶段五轴、四层贡献与撤销守恒且不开治理命令",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blockedV2),getAnalystLearningScenario:vi.fn().mockResolvedValue(learning)}} loadAsyncJobs={emptyJobs}/>));expect(host.querySelector('[aria-label="经营经验沉淀"]')).not.toBeNull();expect(host.querySelectorAll(".analyst-learning-stages li")).toHaveLength(7);expect(host.querySelectorAll(".analyst-learning-axes article")).toHaveLength(5);expect(host.textContent).toContain("原子 Skill → Logic 编排 → 数字同事绑定 → 工作台贡献视图");expect(host.textContent).toContain("历史 Exposure 保留");expect(host.textContent).toContain("approve ≠ promote");expect(host.textContent).toContain("submit=false · approve=false · promote=false · publish=false · revoke=false");const buttons=Array.from(host.querySelectorAll("button")).map((item)=>item.textContent).join(" ");expect(buttons).not.toMatch(/提交 Candidate|批准 Candidate|晋升知识|发布 Wiki|撤销知识/)});it("学习场景失败不破坏原 Analyst 视图",async()=>{await act(async()=>root.render(<AnalystPage client={{getAnalystView:vi.fn().mockResolvedValue(blockedV2),getAnalystLearningScenario:vi.fn().mockRejectedValue(new Error("unavailable"))}} loadAsyncJobs={emptyJobs}/>));expect(host.querySelector('[role="alert"][aria-label="经营经验沉淀"]')).not.toBeNull();expect(host.querySelectorAll('[role="tab"]')).toHaveLength(7);expect(host.textContent).toContain("经验候选、知识库与撤销操作均不开放")})});

describe("AnalystPage BI-W7-01 investigation contribution", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("只识别冻结的 exact flag namespace 且默认关闭", () => {
    expect(resolveBusinessInvestigationFeatureFlags(undefined, false)).toBe(CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS);
    expect(resolveBusinessInvestigationFeatureFlags(undefined, true)).toBe(OPEN_BUSINESS_INVESTIGATION_READ_FEATURE);
    expect(resolveBusinessInvestigationFeatureFlags("", true)).toBe(CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS);
    expect(resolveBusinessInvestigationFeatureFlags("workshop.analyst.business-investigation.read")).toBe(CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS);
    expect(resolveBusinessInvestigationFeatureFlags("ecommerce.investigation.read")).toBe(OPEN_BUSINESS_INVESTIGATION_READ_FEATURE);
    expect(resolveBusinessInvestigationFeatureFlags("ecommerce.investigation.commands")).toBe(CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS);
    expect(resolveBusinessInvestigationFeatureFlags("ecommerce.investigation.read,ecommerce.investigation.commands")).toBe(OPEN_BUSINESS_INVESTIGATION_COMMAND_FEATURE);
  });

  it("开发态未配置时默认开放只读验收入口且不隐式开放命令", async () => {
    await act(async () => root.render(
      <AnalystPage
        client={{ getAnalystView: vi.fn().mockResolvedValue(blocked) }}
        investigationClient={emptyInvestigationClient}
        featureFlags={resolveBusinessInvestigationFeatureFlags(undefined, true)}
        loadAsyncJobs={emptyJobs}
      />,
    ));

    const tabs = host.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    expect(tabs).toHaveLength(8);
    expect(tabs[0]?.textContent).toContain("生意探究");
    expect(host.textContent).toContain("写入口 0 · 周期计划、评审与 Handoff 关闭");
    expect(host.textContent).not.toContain("ecommerce.investigation.commands · canonical 评审受控");
  });

  it("exact read flag 关闭时完整保留原七视图行为", async () => {
    await act(async () => root.render(
      <AnalystPage
        client={{ getAnalystView: vi.fn().mockResolvedValue(blocked) }}
        featureFlags={CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS}
        loadAsyncJobs={emptyJobs}
      />,
    ));

    const tabs = host.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    expect(tabs).toHaveLength(7);
    expect(tabs[0]?.textContent).toContain("经营总览");
    expect(host.textContent).not.toContain("ecommerce.investigation.read");
  });

  it("exact read flag 开启时生意探究成为首 Tab 且七视图仍可访问", async () => {
    await act(async () => root.render(
      <AnalystPage
        client={{ getAnalystView: vi.fn().mockResolvedValue(blocked) }}
        investigationClient={emptyInvestigationClient}
        featureFlags={OPEN_BUSINESS_INVESTIGATION_READ_FEATURE}
        loadAsyncJobs={emptyJobs}
      />,
    ));

    const tabs = host.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    expect(tabs).toHaveLength(8);
    expect(tabs[0]?.textContent).toContain("生意探究");
    expect(tabs[0]?.getAttribute("aria-selected")).toBe("true");
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("ecommerce.investigation.read");
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("当前没有可见分析记录");
    expect(host.textContent).not.toMatch(/开始分析|创建 Case|继续运行|执行 Handoff/);

    act(() => tabs[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("经营总览");
    expect(tabs[1]?.tabIndex).toBe(0);
    expect(tabs[1]?.getAttribute("aria-controls")).toBe(host.querySelector('[role="tabpanel"]')?.id);
  });

  it("同一冻结 flag 根支持全关、只读、受控命令再全关", async () => {
    const analystClient = { getAnalystView: vi.fn().mockResolvedValue(blocked) };
    const renderWith = async (featureFlags: typeof CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS) => {
      await act(async () => root.render(
        <AnalystPage
          client={analystClient}
          investigationClient={emptyInvestigationClient}
          featureFlags={featureFlags}
          loadAsyncJobs={emptyJobs}
        />,
      ));
    };

    await renderWith(CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS);
    expect(host.querySelector("#analyst-tab-investigation")).toBeNull();

    await renderWith(OPEN_BUSINESS_INVESTIGATION_READ_FEATURE);
    expect(host.querySelector("#analyst-tab-investigation")).not.toBeNull();
    expect(host.querySelector(".business-investigation-tab > header > strong")?.textContent).toBe("只读");
    expect(host.textContent).toContain("写入口 0 · 周期计划、评审与 Handoff 关闭");

    await renderWith(OPEN_BUSINESS_INVESTIGATION_COMMAND_FEATURE);
    expect(host.querySelector(".business-investigation-tab > header > strong")?.textContent).toBe("受控操作");
    expect(host.textContent).toContain("ecommerce.investigation.commands · canonical 评审受控");

    await renderWith(CLOSED_BUSINESS_INVESTIGATION_FEATURE_FLAGS);
    expect(host.querySelector("#analyst-tab-investigation")).toBeNull();
    expect(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).toHaveLength(7);
    expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("经营总览");
  });
});

describe("AnalystPage S8 visual density", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("默认折叠经营参谋说明并保留完整语义", async () => {
    await act(async () => root.render(
      <AnalystPage
        client={{ getAnalystView: vi.fn().mockResolvedValue(blocked) }}
        loadAsyncJobs={emptyJobs}
      />,
    ));

    const heroContext = host.querySelector<HTMLDetailsElement>(".analyst-hero-context");
    expect(heroContext?.open).toBe(false);
    expect(heroContext?.querySelector("summary")?.textContent).toContain("经营参谋说明");
    expect(heroContext?.textContent).toContain("Observation ≠ attribution ≠ causal claim");
  });
});
