# W5cao｜第 2/5 步：已批准 GrowthPlan 内的武器包方法载体（中间证据）

先复习 231 A1-03/04/05、231-9 BG-03/04、栖月汇产品方案与现有 Review/TaskBrief Owner。W5cao 方案增补后，`GrowthPlanRevision` 新增可选、结构化的 `salesWeaponMethod`：单商品来源键/标签、有来源客群与场景、适配/不适配、待评审主张、未知、禁说、真人交接及来源 cutoff。它进入原 GrowthPlan 的序列化/hash 输入，不另设批准状态机；历史无此字段的 Plan JSON 不增键。没有反向 planRef 自引用，Review 后续从当前 approved Plan exact Ref 构造 Brief。

RED：合法新字段被旧 `extra=forbid` 拒绝；GREEN：新字段受有界证据闭包、去重、时区和 cutoff≤批准时间约束。新旧序列化 hash 输入不同；旧接口与数据未迁移。专项/相邻累计：49 passed、7 既有 warnings；compile 和 `git diff --check` 通过。未改 Host、Task Owner、Provider、路由或 UI，浏览器 N/A。

**未完成**：真实 Decision/Evidence 当前性、商品事实、销售武器包对 `taskSpec` 的一致性、TaskBrief 全文保存/读回、v1 回放、未知提交与自然链均未验收。第 3/5 步在现有 Review Host 同事务读取当前 approved Plan 与 Decision/Evidence，验证 method，匹配 TaskSpec 并保存完整 method；任何不足保持无任务。不得用这份结构合同称首链已经生产内容。旧 12 Run 不重发，不读商城源，230 L0 挂起，dev-org 零 canary，m1 单写不 push。

## 第 3/5 步第一段：原 Plan Owner hash 门已补

RED：旧 `publish_plan` 对任意 `content_hash` 先进入 SQL（测试失败）；GREEN：只在原 GrowthPlan Owner 发布窄入口于 SQL 前用原 `canonical_hash` 核对完整 payload，`get_plan_exact` 也重算 exact hash，并核对 Plan 身份/版本。旧测试的假常量 hash 已改成真实计算，没有更改生产 hash 算法。隔离 PG 新方法在原 Store 中发布/读回，外层 rollback；旧 Review current-approved Plan 测试保持通过。Plan/Review/武器包邻接累计 **76 passed、1 skipped**，追加 PG 方法读回后该文件 2 passed；7 既有 warnings。Host 尚未比较批准 method 与 `taskSpec`，完整 W5cao 仍未完成。
