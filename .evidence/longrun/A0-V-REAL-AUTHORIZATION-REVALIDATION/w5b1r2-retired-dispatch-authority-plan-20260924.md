# W5b1R2 历史已 detach dispatch 的生命周期判定修复（2026-09-24）

## 根因与范围

W5b1R `ba659895` 的原 Owner disable 在同事务被 `open activation claim gate authority drifted` 拒绝，新 Command Receipt=0、旧 enable 仍 accepted。只读查得 group `6a402d31-83ad-546c-807f-508c87498ce1`：历史 112 条 activate/cutover 仍 `resumed`，112 条对应 lifecycle operation 均 `detached`；当前 9 条 dispatch binding 全是 `legacy`/fenced/无 installation，claim gate 当前行不存在。`EcommerceGrowthDisableDependent._after_runtime_fenced` 仅按旧 activation 与 runtime revision 匹配，未先判别该 group 已正式退休，于是误入必须拥有开放 gate rev2 的 fence 函数。

复习 `ecommerce_growth_lifecycle.py`、`ar2_017` DB gate、`a0v_055/a0v_072` 历史迁移、W5b1R 计划和失败验证。本波仅改变 Python Owner 的**只读判别**，不改数据库函数/历史表/凭据，不读商城源，不绕过仍有当前 extension dispatch 的任何门禁。

## 修改文件与执行顺序

- 修改 `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`；新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_retired_dispatch_gate.py`；新增仅本波使用的 `scripts/a0v_w5b1r2_enable_retirement.py`（新私有目录/新键，绝不复用 W5b1R intent）。
1. 独立只读审查现行 matched activation、关联 group 与 gate/dispatch/历史 detached、当前 generation 的 running/claimed/unknown 尝试及旧 enable outbox。写前/后都要求 12 schedules off、旧定义 disabled、canary0。
2. 仅在**恰好一个** activation 匹配且该 activation 的 group 完整满足：精确 9 个 operation ID、9/9 `legacy`/fenced/无安装关联、目标安装没有任何 extension dispatch、claim gate 不存在、存在该 activation 的正式 detached 历史、generation 无运行/claimed/unknown 尝试时，判为没有当前待 fence dispatch，沿原 Owner 的 no-op dependent 返回；否则继续原逻辑/报错。正常开放 gate/fresh activation 路径完全不变。
3. 单测覆盖完整 retired、缺任一证据、混合 dispatch、有 gate、活跃尝试、多个 matched；运行原 cutover/disable/concurrency 相关回归与 `git diff --check`。再用只读主库连接调用新判别，必须与第 1 步一致。
4. 冻结新批次精确 intent（O_EXCL/0600）并通过原 RuntimeDisableService 新键一次取消旧 enable；若 DB 仍拒绝或提交边界未知，不重发。按 W5b0 已验证的 outbox 审计/精确消费规则，确认新 disable 正式终态和旧 enable cancelled。
5. 独立审计、verification、m1 commit，不 push；下一波才设计新 live successor/PreparedJob 与 12 条当前 selection 控制链。

## 停止条件

不能证明完整退休谓词、存在任何当前 extension dispatch/未知尝试、旧 enable 已被 claim/提交、或本波 Owner 请求未知时停在原状态。禁止伪造 gate、直接 UPDATE、删除 outbox、传 `dependent=None` 或重放旧键。
