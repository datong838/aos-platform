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
