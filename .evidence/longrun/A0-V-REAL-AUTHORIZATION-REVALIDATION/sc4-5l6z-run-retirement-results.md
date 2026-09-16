# SC4-5L6Z：旧活动 Run 正式终止结果

日期：2026-09-17

## 结论

旧 `BusinessInvestigationRun analysis-e5b19a5fe290ce1bf60d5038cb1d6cf6` 的原源
`scr-bddff0a74c2a4365` 没有完整 snapshot group claim/input，关联 DataRequirement 的
Outbox delivery 已确定性 `failed/CURRENT_ROUTE_REJECTED`，且 Fulfillment、completion refs
均为空。因此没有伪造旧 group、没有重领 failed Outbox，也没有把过期 Requirement 续跑。

通过 canonical command/store 已完成以下正式终态：

- DataRequirement 从 r1 requested 进入 r2 rejected；同一幂等键重入读取既有 r2 Receipt，
  没有产生 r3。
- BusinessInvestigationRun 从 v2 WAITING_DATA/RUNNING 进入 v3 PREPARING/CANCELLED，
  `pending_requirement_ref`、`uncertain_command` 均为空，active slot 从 1 变为 0。
- 关联 canonical AIP Task 从 v5 paused 进入 v6 cancelled，TaskRun 从 v3 paused 进入
  v4 cancelled，并形成一条 `run.control` Evidence。
- 全过程 `sourceReadPerformed=false`、`externalEffectAuthorized=false`。

权威结果见：

- `sc4-5l6z-post-run-retirement-audit.json`
- `sc4-5l6z-run-retirement-receipts.json`
- 私有 0600 intent/result 与迁移证据位于
  `.aos-recovery-20260916/state/z-retire-ungrouped-run/` 和
  `.aos-recovery-20260916/state/z-main-a0v-075/`，不进入 Git。

## 修复与一致性

1. 分析发现与执行都要求原 source Run 属于完整 snapshot group，且 actor、control/run pair、
   input clock 一致；孤立的单路成功 Run 不再生成分析 Run。
2. DataRequirement 只有 requested/accepted/planned 继续要求创建时未过期；终态 reject/cancel/
   unknown 可保留原业务有效期，不能修改原 expiresAt。
3. Requirement reject Saga 使用既有 Run control 进入 CANCELLED；accept 行为不变。同键半提交
   重入只补 Run transition，不新增 Requirement revision。
4. `a0v_075` 只替换既有 Run control 函数的 exact UPDATE 片段，使 authority JSON 和 head
   物理字段一致。main 从 `a0v_074` 单步升级，13 张相关业务表前后指纹完全相同。

代码目录：

- `services/aos-api/aos_api/`
- `services/aos-api/alembic/versions/`
- `services/aos-api/tests/`
- `services/aos-api/tests/extension_runtime/`
- `scripts/`

## 验证

- 定向与组合回归：62 passed，14 skipped；跳过项是测试自身的可选环境分支，不包含
  `a0v_075` 隔离 PostgreSQL 合约用例，该用例已真实通过。
- `a0v_075` 隔离库：PREPARING → WAITING_DATA → CANCELLED；物理 pending 字段清空、slot
  释放、同键重放不新增事件。
- 脚本语法检查通过，`git diff --check` 通过。
- AR2 phase `ar2-7`：1982 modules 扫描，199 classified，93 migrated；hash、正反向依赖、
  bundle cross-layer import、dynamic reference 错误均为零。

## 尚未完成

本结果只完成 Z 波旧活动 Run/Task 的正式终止。P 的 65 个 occurrence 尚需全部形成可审计
终态，Policy11 仍需正式禁入，P 仍需 detach/uninstall；随后修复 schedule last_run 投影回退，
再创建 source-disabled 的 Q 并进入下一次真实自然链窗口。不得将本结果解释成 A0-V、八工作台
或发布完成。
