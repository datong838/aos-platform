# W5CB4 P2g30b 当前 RETURN Action 正式生产者细化计划（2026-09-27，编码前）

## 上位与现状

- 231-5 §4–6：人工退回必须新版产物与新批准，旧批准不续用；新预算 held 在能力调用前，未知提交只读对账。产品方案要求工作台控制全过程、不可绕权限/预算。
- P2g29b 证明原 Task `executing` 时不能新建通用 Plan/ImpactPreview。P2g30a `m1@5a8f1a14` 已封 RETURN 半成品 Action 提案/决定，但还没有正向 producer，Host `revalidate/execute` 仍禁入。
- 当前 `BoundContentReturnTarget._source(require_queued=True)` 已校验 ReturnDecision、原 Review Receipt、原 Artifact、唯一 queued 后继 attempt；`require_frozen_repair_brief` 已校验正式 revise/freeze Receipt；`LockedEcommerceGrowthHostPort._lock_and_revalidate` 已拥有整组 dispatch 与 Runtime 锁；内容 Host `_agent_capability_authority` 已校验当前 Capability/Agent/Responsibility 关联。不得在新模块复制这些状态机。

## 文件级清单与串行步骤

1. RED 扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_repair_action_binding.py`：完整六项、R2、原 running Task/Run、唯一 RETURN target、冻结 Brief、当前 dispatch、正式 Capability 和预算上界应得稳定非空 hash；跨租户/旧 decision/非 queued attempt/多义 target/旧 Brief/安装 epoch 漂移/Capability 漂移/负金额均拒绝，且失败零 Action 行。先验证失败输出。
2. RED 扩原 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 同一 RETURN 分支：经公共 `AipActionStore.create_proposal` 与不同 checker 的 `decide` 产生唯一正式批准事件；独立连接读回 proposal/draft/event 的 exact hash。已有旧批准不得充当新批准；重放不产生第二提案。无直接 INSERT 返工批准。
3. 最小实现只修改 `services/aos-api/aos_api/ecommerce_content_repair_action_binding.py` 和 `services/aos-api/aos_api/aip_action_store.py`：在同一事务先唯一寻址 target，再复用上述校验；以当前 ActionType revision、六项 exact payload、scope、task/run、当前授权截面算稳定 hash。请求与重放在 maker 阶段重核；checker 在决定/重放前重核同一 hash、proposal/draft、maker/checker、到期与权限。通用 Preview、首生内容、外部动作和通用预算 Store 不改。
4. 若公共 Store 不能在当前权限/锁序下复用这四个读源，或 Capability/新预算上界无正式来源，停在可复现 RED 与无写 verification，不制造 mock 权威、放宽锁或绕过审批。必要改动超清单先修方案。
5. 专项与相邻累计、迁移头/编译、方案代码一致性及零副作用检查；纯后端浏览器不适用。verification→m1 精确提交→D-waves/AOS/Prime 更新；下一波 P2g30c 才做新容量/预算 held 与新版 prompt/第二次结果 Owner。当前恢复库/自然 Worker/Provider、旧 12 Run、商城源、230 L0 均禁入。
