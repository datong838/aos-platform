# W5CB4 P2g29b · 运行中 RETURN 的通用 Preview 组合边界（2026-09-27）

- 编码前方案 `m1@1a4711a6`，边界修订 `m1@206b7699`。目标是核公共 ImpactPreview→Action 链能否给原 running Run 的 RETURN 返工产生新批准，而不是让隔离夹具直接 INSERT 批准。
- 静态合同：内容预算批准需要正式 proposal 的非空 `action_binding_hash`；通用 Action 路径由 frozen/ready ImpactPreview 计算该 hash。Preview 需要 ProductionContext，且 Plan 风险的 `productionContract.productionContextRef` 必须相同。原 RETURN Task/Run 仍 executing/running，不能重写旧 Plan。
- 动态探针只在原同库正式 RETURN 对象链上调用公共 `AipTaskStore.create_plan`，传当前 Task version 和拟绑定冻结返工 Brief 的 ProductionContext ref；接口以 `AipTaskTransitionBlocked: cannot create a plan while task is executing` 拒绝。独立读回 Plan 计数前后相同；未写假 Plan、Preview、Action 或审批，未调用 Provider。
- `test_ecommerce_content_review_pending_pg.py` 全文件 **8 passed**；`git diff --check` 通过。该结果只证明“在原执行中 Task 上补通用 Plan/Preview”这一路不成立，不证明所有可能的正式返工批准方案均不成立。当前实例无安全迁移/启动权威，浏览器验收本子波不适用。
- 下一波在公共 Action 提案入口设计 RETURN 专属 exact binding：只对当前安装和原 RETURN 的 frozen Brief、ReturnDecision、原 Artifact、能力和预算上限计算并在决定时重核 hash，保留 maker/checker 与预算门；首生和外部动作路径不变。须先方案、再 RED/最小改动/同库公共提案+决定正向；不得伪造真人批准，不解除 Host `revalidate/execute` 双重禁入。恢复 PG `a0v_092` 且无可核当前备份，继续 `STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS`。
