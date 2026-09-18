# Recoverable Store parent feature Git 闭包验证

## 1. 验证对象

- 目标：把已经承载真实 AM 的 a0v084-a0v088、saved recovery、recoverable Store attempt、group
  completion、relationship/link/retirement 与 schedule/worker 形成可独立检出的父能力闭包。
- 文件边界：42 个文件；5 个 migration、5 个单步部署器、16 个运行时核心、16 个专项测试。
- 明确排除：successor 实例脚本、`lease_renewal.py`、`verification_commit.py`、
  `preparation_owner.py`、230 L0 以及工作树其他用户改动。

## 2. 当前真实运行边界

- AM attempt 1 `7d6cc3aa-881d-4aff-ac30-58978d06e85d` 与 attempt 2
  `38e5c7b9-fa37-4d3f-8f3f-769b995b4db3` 均为 failed。
- attempt 2 与 attempt 1 使用相同 request hash；失败前十二个 Run 已持续推进，最终失败与十二个 runtime
  control 同时到期相隔约 440ms。由于旧实现没有终态 reason 字段，只记录相关性，不追填猜测原因。
- definition rev54 disabled；AM installation 已通过正式 disable/detach 路径退休，binding fenced、资源释放，
  running/unresolved/runtime pending/authoritative outbox/dev-org canary 均为零。
- Store Receipt 仍为零；该事实意味着没有已知外部 Store 副作用，也不授权重发未知结果。

## 3. 文件与静态检查

- 42/42 文件存在。
- `git diff --check`：通过。
- Python `py_compile`：通过。
- Alembic：单一 head `a0v_088`。
- 新增 import 均落在本闭包或既有已跟踪模块中；没有引入 successor 实例、浏览器或 230 L0 依赖。

## 4. 专项与累计回归

- 跨窗口恢复主用例：2 passed、7 warnings，1788.78s；同时覆盖 running 和 stopped-failed 续跑，验证
  原 request identity 在恢复窗口变化后保持一致。
- attempt/lease 相邻组：11 passed、3 skipped。
- a0v084-a0v088 migration 与 recovery contracts：41 passed。
- failed recovery 与 schedule worker：13 passed。
- 本波 assessment/object/relationship/input/definition/attempt 累计组：28 passed、45 skipped、7 warnings，
  106.71s；skipped 均为测试自身声明的外部 PostgreSQL 条件分支，实际执行项无失败。
- AM exact pause 回归：18 passed；AM retirement/saved recovery：4 passed。

## 5. 方案与代码一致性结论

- 恢复请求身份由 tenant/group/actor、原 source claim、原 input manifest、exact policy content hash 与排序后
  Run IDs 组成；普通与恢复 definition 共用同一构造函数，不再受新窗口或新 definition identity 影响。
- attempt ordinal、原 request hash、saved input 与 prior attempt anchor 在数据库链和 Owner 中闭合；同一 request
  只能有一个 running attempt，失败后允许 direct successor，不允许并行 owner。
- relationship/link/retirement 仍经过 journal、Receipt 与生命周期 fence；没有将测试绿或投影状态当成外部
  Store 成功证据。
- 浏览器业务门禁保持独立：当前仍没有可见电商工作台入口，因此本提交只证明恢复父能力可检出、可回归，
  不宣称栖月汇自然经营首链完成。

## 6. 后续

1. 提交父能力闭包且仅暂存本证据、更新后的方案与 42 个明确文件。
2. 进入 a0v089 终态原因持久化，区分 control/lease 到期、heartbeat 故障与业务执行异常。
3. 关闭相邻 Host 续租闭包并在无 running attempt 空窗安全重载。
4. 由 Worker 正式 definition 自然产生 AN direct successor，不手工调用 `run_definition`，继续只读守护
   Receipt、租户隔离和未知提交边界。
