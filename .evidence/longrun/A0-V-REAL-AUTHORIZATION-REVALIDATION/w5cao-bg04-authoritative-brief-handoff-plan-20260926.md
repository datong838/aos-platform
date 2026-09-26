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
