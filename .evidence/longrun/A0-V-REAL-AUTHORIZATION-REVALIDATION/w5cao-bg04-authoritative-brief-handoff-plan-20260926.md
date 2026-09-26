# W5cao｜BG-04 已批准 Brief→内容任务权威接线方案

## 上位方案与边界

231 A1-03/04/05、231-9 BG-03/04 和栖月汇双侧增长产品方案要求：有来源的单商品/客群/场景建议，经 exact 方案评审后自动生成**内部**内容任务，实际能力产出可读物，再经人工评审续跑。W5cak 只有 `SalesWeaponBriefDraft`→`ContentTaskSpec` 纯映射；现有 Review Host 已能在同事务建立 AIP Task、TaskBrief 和 Handoff Receipt，并独立回读，但它没有消费已批准的销售武器包 Brief。不能把草稿 DTO、四 Artifact 通用引用或 caller-supplied TaskSpec 冒充已批准武器包。W5can 的真实 D01 来源门仍冻结；本波只处理可以独立验证的 BG-04 内部接线，绝不伪造上游批准。

## 文件级清单及步骤

1. 读 `ecommerce_growth_runtime_adapters.py` Review Host `_strict_review_accept_command`、`_review_lineage`、TaskBrief 存取与现有测试；核对 AIP `TaskBriefRevision` 能否保存/读回销售武器包的完整来源、unknown/禁说、exact Plan/Decision。列出缺口，保留旧 v1 回放。
2. 在 `services/aos-api/tests/extension_runtime/` 写 RED：未经批准或当前权威不一致的武器包绝不能进入 ACCEPT；合法包的来源/未知/禁说必须在 TaskBrief 中原样可读回；同键漂移、错租户、未知提交均不得产生第二任务。测试只使用隔离 PG/构造数据，不读商城源。
3. 只在已有 Review Host 与 AIP TaskBrief 上做最小实现，不另造任务 Owner、不增宽 Host 命令允许字段。若完整来源无法由现有四 Artifact/Plan/Decision 证明，停止接线并形成明确上游证据需求；不降低正式门。
4. 专项及邻接累计回归；隔离 PG 验证 Task/Brief/Handoff 同事务与旧 v1 回放，浏览器仅在真实可用页面存在且不会越权时验收；无页面则明确 N/A。
5. 方案/代码一致性和风险复审，verification 落盘后 m1 commit，更新 AOS/Prime 上下文。下一波返回首链最早缺口：D01 当前 selector/自然结果，或 BG-04 内容能力与人工续跑。

停止门：没有当前已批准 GrowthPlan/Decision、exact Evidence 与身份/租户/安装权威时，不发布武器包或实际内容任务；未知结果只读对账，不重发；Provider/对外发布保持关闭。旧 12 Run 不重播，不读商城源，230 L0 挂起，dev-org 零 canary，m1 单写不 push。

## 第 1/5 步现场复核（开码前）

`GrowthPlanRevision` 只有 objective/constraints/items/DecisionRef，`DecisionSummaryRevision` 有来源和不确定性，却均无完整的单商品 `fitFor`/`notFitFor`/禁说/真人交接结构。现有 Review `_strict_review_accept_command` 只接受固定 `taskSpec` 字段；`_review_lineage` 保存的 TaskBrief spec 是 objective/channels/audience/timeWindow/constraints 与四 Artifact/Plan 引用，没有 `SalesWeaponBriefDraft`、DecisionRef 或逐主张 EvidenceRef。AIP `TaskBriefRevision.spec` 本身是通用 JSON，存取能力足够，但当前 Review 命令无法传入并独立验证完整武器包。故**不能**只靠原四 Artifact/Plan/Decision 在 Review 入口推断一个已批准武器包；原方案第 3 步“保持严格命令字段不变”与目标相冲突。第 2 步 RED 暂不写一个要求当前接口无法表达的假测试。

下一步先补精确 v2 合同设计并修订本方案：定义武器包的持久 exact Ref、审批与来源读回、v1/v2 并存的严格命令版本；v1 旧回放不变，v2 缺任一权威即拒绝。审批之前没有自动 Task 创建。方案复审完成后才写 RED/最小代码，避免草稿绕过审批。

## 第 2/5 步方案修订：复用 GrowthPlan 的批准及 exact hash

不另造武器包批准状态机。`GrowthPlanRevision` 的新版本增加可选 `salesWeaponMethod`，由既有 GrowthPlan 发布/审批 Owner 的不可变 payload 和 contentHash 覆盖；历史无此字段的 v1 序列化必须逐字兼容。此字段不内嵌反向 `planRef`（避免 hash 自引用）；由当前已批准 Plan exact Ref 在 Review 读取时补成 `SalesWeaponBriefDraft`。`decisionRef` 仍取同一 Plan，业务语句的 EvidenceBundle exact refs 必须有界、唯一且闭合；来源 cutoff 不得晚于批准时间。此阶段的字段只是已批准 Plan 的内容，**不单独证明**来源仍当前、商品事实或评审已接受。

本步文件级最小切片：修改 `services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py`，新增结构化 `SalesWeaponMethod`/有来源语句并让 `GrowthPlanRevision.sales_weapon_method` 可选、None 不序列化；修改 `services/aos-api/tests/test_ecommerce_analyst_authority_contracts.py`，先 RED 证明旧 Plan hash 输入不变，新方法接受合法有来源数据并拒绝缺证据/禁说/时区/批准后 cutoff。不得触碰原 Plan Owner 写路径、Review Host、Task 创建、Provider；后续第 3 步才在 Review Host 同事务复核 Plan→Decision/Evidence/current authority、从 Plan 构造 exact Brief 并与 TaskSpec 比对，失败即无任务。旧 v1 Review 保留原规则，但不得标注为武器包 v2 验收。

若 `salesWeaponMethod` 与现有 Plan 发布语义不兼容，保留 RED 并先修订方案，不复制另一份批准 Owner。专项和累计回归、方案一致性与验证仍按前述第 4–5 步执行。

第 2 步代码复审发现原 `EcommerceAnalystAuthorityStore._publish` 只核对 actor/tenant/CAS/Receipt，对 `item.content_hash` 未做 payload 重算；Review Host 后续会重算，但无法让错误 hash 在发布时 fail closed。第 3 步须先改 `publish_plan` 或其窄路径，在任何 SQL 前核对原 canonical hash；RED 覆盖合法方法、漂移和旧 Plan，旧测试里的任意常量假 hash 必须改成真实计算，不能改生产 hash 算法适配假测试。随后才做 Review 当前权威/TaskSpec 接线。

## 第 3/5 步 Review Host 精确施工补充

Plan Owner hash 门和隔离 PG exact 读回已完成（`bf90b85a`），不再重复。当前最小剩余文件：`ecommerce_analyst_authority_contracts.py` 的 `SalesWeaponMethod` 加获批 `channels`/`timeWindow`，使全部 ContentTaskSpec 业务字段都由已批准 Plan 决定；对应合同测试先 RED。`ecommerce_growth_runtime_adapters.py` 的原 Review Host 在 `revalidate` 同一 HostTransaction 中，在原 `_revalidate_growth_plan` 读取当前 approved exact Plan 之后，仅对含 `salesWeaponMethod` 的 Plan：

1. 通过现有 `require_growth_plan_sources` / `require_current_revision` 复核同租户当前 Decision→Insight、完整 EvidenceBundle/原 Evidence/marking，要求方法 Evidence refs 被 Decision exact 来源集合包含，方法 cutoff 与 Insight/canonical Review cutoff 一致；以 Host dispatch 的 DB 时钟与命令有效期作为有界 freshness 上限，过期拒绝。不得读商城源、不得另开连接。
2. 从方法确定性派生 `title`、`objective`、`audience`、`channels`、`timeWindow`、`constraints`，与原 strict `taskSpec` 逐字段相等；商品技术来源键不进入 Task 文本。未匹配、缺 Evidence 或权限撤销都在创建 Task 前失败。
3. `_review_lineage` 在同一事务把完整方法、Decision exact Ref 与来源 cutoff 加入现有 TaskBrief `spec`，并维持旧无字段 Plan 的原 v1 payload 完全不变；使用既有 TaskBrief Owner 的 hash/Receipt/读回，不新建 Owner。v2 成功和漂移/撤权/旧 v1 回放均用隔离 PG 与 Host 邻接测试验证；未经该门的直接私有方法调用不算授权入口。

先写 RED，再实现；若 Review Host 无法获得 DB 时钟或原来源检查不能在 HostTransaction 中复用，停此切片并修订方案，不退化为 caller-supplied 授权。

下游复审补充：`ContentGenerateHostService._task_brief` 目前只接受旧 `_CONTENT_BRIEF_SPEC_FIELDS`，会把新的完整武器包 Brief 当漂移拒绝。因此本波还须在同文件的原内容生成 Host 中严格区分 v1/v2：先复核当前 approved GrowthPlan exact，再以 Plan 是否含 `salesWeaponMethod` 决定 TaskBrief **唯一允许**的字段集合；v2 必须逐字等于该 Plan 的方法、DecisionRef 和 cutoff，且任务文本与已批准方法一致；v1 保持旧字段集合和旧 Receipt 回放。不能以放宽 `set(spec)` 或跳过 Plan 核对代替接线。文件级测试补 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py` 的 v2 合法/漂移/旧 v1，及隔离 PG Brief 读回。真实能力调用、预算与审批仍由内容生成原门负责，本波不启动 Provider。

复审又发现旧 Review `_revalidate_analysis_runtime` 未核命令 cutoff 与原 AnalysisRuntimeReceipt cutoff；旧 Receipt 可无该字段。只对含批准武器包的 v2 路径，在 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 把原 Receipt 的 `cutoffAt` 与方法/Review cutoff 同版核对；旧 v1 不改。补 `services/aos-api/tests/extension_runtime/test_ecommerce_review_analysis_runtime_authority.py` 缺字段/漂移拒绝。否则 caller 可选另一 cutoff 伪装新方法来源。
