# P8 25 页合同与权威追溯

> cutoff：2026-09-02；租户：`org-org/dev-project`；范围：AIP 左侧菜单 25 页。
> 判定规则：页面只认当前前端 SDK/请求与当前服务端 router；只有服务端返回的 exact Receipt/Lineage 才记为凭证。无 Receipt 的只读目录不伪造 Receipt，无 `lineageId` 时不以 `traceId` 替代。

| 页面 | 前端请求 owner | 服务端合同 owner | 数据权威与凭证边界 |
|---|---|---|---|
| 任务协作助手 `/aip/assist` | `api/aipWorkbench`、`api/aipTasks` | `routers/aip_assist_runtime.py`、`routers/aip_tasks.py` | Task/TaskRun/AgentRun 与 AssistThread Store；控制命令以 Task timeline/Receipt 回读，消息事件只绑定 exact subject refs |
| 智能体配置 `/aip/studio` | `api/aipAgentControl`、`api/client` | `routers/phase3_aip_agents.py`、`routers/aip_agent_runs.py` | AgentInstance、overlay、binding、AgentRun；写入必须 CAS 后重读，运行只认服务端 Run/Receipt |
| AIP 分析师 `/aip/analyst` | `api/aipWorkbench`、`api/ontologyExplorationAssets` | `routers/aip_analyst.py`、ontology exploration router | AnalystQuery authority、语义对象与探索资产；结果保留 source refs/cutoff，保存探索以服务端资产回读为准 |
| 业务逻辑编排 `/aip/logic` | logic graph/run/publication SDK、`api/aipTasks` | `routers/aip_logic_graphs.py`、`aip_logic_runs.py`、`aip_logic_publications.py`、`aip_logic_automations.py` | LogicGraph revision/hash、Publication、TaskRun；dry-run 不冒充 canonical Run，Receipt/Lineage 只取服务端返回 |
| 智能体工具配置 `/aip/tools` | `pages/s2/aip.tsx` canonical API | `routers/phase3_aip_tools.py`、`routers/aip_bindings.py` | Tool catalog、permission/binding authority；保存必须服务端确认，失败不保留本地已绑定态 |
| 成熟度楼梯 `/aip/maturity` | `pages/s2/extras.tsx` canonical API | `routers/aip_extras.py`、`routers/aip_runtime_guard_policies.py` | maturity/breaker 当前投影；状态切换只认服务端版本与回读 |
| 公共生产合同 `/aip/production-contracts` | `api/aipProductionContracts`、`api/aipActions` | `routers/aip_production_contracts.py`、`routers/aip_actions.py` | TaskBrief/Evidence/Eval/Responsibility/Preview/Proposal exact revision/hash；生产启动要求同 Task、批准且未过期 Proposal 和 Receipt-first |
| 能力目录 `/aip/capabilities` | `api/aipAgentControl` | `routers/phase3_aip_capabilities.py` | 全局 CapabilityRevision 与组织 Binding/Readiness；目录 published 不等于组织可运行 |
| 智能体目录 `/aip/agent-registry` | `api/aipAgentControl` | `routers/phase3_aip_agents.py`、`routers/phase3_aip_capabilities.py` | 六数字同事定义、组织实例、绑定与 readiness；安装/配置只认 RegistryReceipt 与回读 |
| 智能体市场 `/aip/agent-marketplace` | `api/aipMarketplaceImport` | `routers/phase3_aip_agents.py` | Marketplace catalog、import preview/job/receipt；preview 不等于已安装 |
| 智能体列表 `/aip/agents` | `api/aipAgentControl`、`api/aipMarketplaceImport` | `routers/phase3_aip_agents.py`、`routers/aip_agent_runs.py` | 组织 AgentInstance 与最近 AgentRun；进程内旧行不作 durable authority |
| 技能发布 `/aip/skill-publish` | `api/client`、`api/aipAgentControl` | `routers/phase3_aip_skills.py`、release publication router | Skill revision/hash、评测/批准与 Publication Receipt；校验失败不生成发布成功态 |
| 智能体导入 `/aip/agent-import` | `api/aipMarketplaceImport` | `routers/phase3_aip_agents.py` | Agent import preview/job/receipt；租户、版本与内容摘要不一致即失败关闭 |
| 能力导入 `/aip/capability-import` | `api/aipMarketplaceImport` | `routers/phase3_aip_agents.py`、`phase3_aip_capabilities.py` | Capability import preview/job/receipt 与 exact CapabilityRevision；不以预览冒充导入 |
| 评测门控 `/aip/evals` | `api/aipEvidence`、canonical eval API | `routers/aip_eval_authority.py`、`routers/evals.py` | EvalSuite/EvalRun/ReleaseGate authority；终态必须有完成时间与 exact suite/run refs |
| 草稿审批台 `/aip/drafts` | `api/aipActions` | `routers/aip_actions.py`、draft routers | Draft/Proposal/Approval revision 与 maker-checker Receipt；不可用迁移禁用而非模拟成功 |
| 决策谱系 `/aip/lineage` | `api/aipEvidence` | `routers/aip_lineage_authority.py` | LineageEvent append-only authority；仅服务端 `lineageId` 是谱系，缺失时显示缺证 |
| 可观测性 `/aip/observability` | `api/aipEvidence`、`api/aipActions` | `routers/aip_telemetry_usage.py`、`aip_lineage_authority.py` | TelemetrySpan/UsageReceipt 与 Lineage root；0 条凭证表示缺证，不解释为业务数量 0 |
| 记忆与知识治理 `/aip/memory-governance` | `api/aipMemory` | `routers/aip_memory_authority.py`、`aip_memory_improvement.py` | Memory item/revision、pipeline、projection 与 disclosure policy；创建/撤销必须 Receipt/CAS 后回读 |
| 模型目录 `/aip/model-catalog` | `api/aipModelRuntime`、`api/aipFeatureActivation` | `routers/model_catalog.py`、`aip_model_runtime.py` | ModelRevision、price authority 与 feature activation；注册/撤销以服务端列表回读为准 |
| 模型供应商 `/aip/model-providers` | model admin canonical API | `routers/model_providers.py`、provider plugin authority | Provider definition/config/health observations；页面不解析 secret，不把插件 ready 当完整运行就绪 |
| 模型路由 `/aip/model-router` | model admin canonical API | `routers/model_routes.py`、`aip_model_runtime.py` | versioned Route authority；保存与试聊共用 exact revision，Provider 不可用保持失败关闭 |
| 容量管理 `/aip/capacity` | `api/aipModelRuntime` | `routers/model_capacity.py`、`aip_model_runtime.py` | quota/capacity/budget/usage authority；缺预算显示缺权威，不填充 0，配额保存后重读 |
| 运行就绪 `/aip/model-runtime` | `api/aipModelRuntime` | `routers/aip_model_runtime.py` | Provider、Route、Capacity、Approval、Health 同 cutoff 组合；任一过期/缺失即 fail-closed，不隐式探测 Provider |
| 文档智能 `/aip/doc-intelligence` | `api/client` + authenticated upload | `routers/phase6_documents.py` | Document、template、ingestion/review receipts；上传/模板受控写必须回读，处理失败不伪造文档事实 |

## 复审结论

1. `INTERACTION_HONESTY_MANIFEST` 已与真实 AIP 侧栏 25 条路由建立一一覆盖测试；全部页面 `sourceMode=live`，且每页具备源码、fallback policy 和测试引用。
2. 原缺失的工具、公共生产合同、市场、技能发布、两类导入、谱系、运行就绪 8 页已补入清单；能力页已从旧 `CapabilityPage/mixed` 更正为实际 `CanonicalCapabilityPage/live`。
3. 本表只证明代码合同与权威归属；正向真实数据、负向隔离、浏览器交互及累计测试分别由 P8C～P8E 证据闭合。
