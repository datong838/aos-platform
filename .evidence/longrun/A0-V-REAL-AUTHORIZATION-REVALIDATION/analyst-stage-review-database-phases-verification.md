# Analyst stage review 数据库三阶段适配验证

日期：2026-09-12  
基线：`aa6d7d35`

结论：准备事务与提交事务已由通用宿主适配器分离，已安装 Growth 包 IPC 期间不持有事务；current authority snapshot exact 漂移时零发布。具体 Owner 读取与 StageDecision publisher 尚待下一波绑定。

## 实现与方案一致性

- `StageReviewDatabasePhases.prepare` 在事务一调用同步 builder，退出事务后才返回带 command hash、authority snapshot 与 exchanges 的 prepared。
- coordinator 在事务外逐条调用既有 one-shot installed port；异常原样上抛，适配器不会打开提交事务。
- `StageReviewDatabasePhases.commit` 在独立事务二复核 command/prepared/results，重读 current snapshot；只有 exact 相等才调用 publisher，publisher 返回类型和 canonical JSON 在事务退出前校验。
- prepared 的完整性封印现同时覆盖 exchanges 与非空 authority snapshot，嵌套对象修改会在 IPC 或 commit 边界 fail closed。
- 数据库回调必须同步；事务段内没有 await，也不投递后台线程，避免调用任务取消后后台 publish 继续造成未知结果。

## 自动验证

- 定向新旧边界：`25 passed`。
- 阶段评审全回归：`126 passed`。
- 两个变更模块 `compileall` 通过。
- `git diff --check` 通过。
- AR2-7 closure：扫描 1776、分类 139、迁移 93；hash、正反依赖、跨层 import 与动态引用错误数组全部为空。
- 既有 7 条 warning 为 Pydantic 字段遮蔽及 Starlette/httpx 弃用提示，本切片未新增 warning。

## 关键失败场景

- 测试观测成功顺序为事务一 open/prepare/close、IPC、事务二 open/load/publish/close，IPC 断言 active transaction 为零。
- current snapshot 漂移：事务二 rollback，publisher 为零。
- IPC 超时未知：只出现事务一和一次 IPC；事务二与 publisher 均为零。
- publisher 异常：事务二 rollback，IPC 与 publisher 各一次且不重放。
- 空/变更 authority snapshot、异步依赖、错误 prepare shape、结果数量不完整全部拒绝。

## 当前 SHA256

- coordinator：`c471c6c180fc1273445e149cbc283c464b9c6799363f423078a2fb91e2fc0cfe`
- database phases：`af318535aaa438181f4e1f3558658f06853d2d2137501eddf172955a9a8d11f7`
- coordinator tests：`2c66a60998e45659a632688bf77984c410e2834f8e861340e05142c321e65c29`
- database phase tests：`190a624aaabbacf666de686980dfc7126ebb1dcfa8f33aa8024b2a9a10f32e7b`
- plan：`0cb8d569299db49b47d3315b39a2966d8f8cf2117be0dd2f67fc8c1d1af6131d`

## 风险与下一门

本切片尚未读取真实 Task/Plan/Run、StepRun、Checkpoint、StageDecision/EvalReport、TenantScope、角色和 lease，也未发布真实决策。因此它不能单独授权或证明栖月汇业务首链。下一波实现 owner-specific authority snapshot builder 与 publisher，绑定现有 `StageReviewCommand` 和数据库模型，并继续保持两个事务、零重试与 exact current 复核。
