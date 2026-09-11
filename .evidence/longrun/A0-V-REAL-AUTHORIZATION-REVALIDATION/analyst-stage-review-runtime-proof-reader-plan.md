# 阶段评审 runtime proof reader 方案

日期：2026-09-12

基线：`4ef94c05`

## 目标与 Rules

新增只读 `read_stage_review_runtime_authority`，复用现有事务内 Task/Plan/Run、StepRun、Checkpoint 和 Observation Evidence 校验，成功后返回 plan、可 canonical 封印的 runtime snapshot，以及 `validate_runtime` exact payload/expected。现有 `require_stage_review_runtime` 保持签名与 plan 返回值。

reader 必须使用数据库实际 observation payload；snapshot 必须覆盖当前 task/run 状态、plan exact ref、step attempt、checkpoint identity/state/dependency hash、Evidence identity/content hash。不得 IPC、写库、构造权限或接受调用方 observation。失败行为与旧函数一致。

## 文件

- `services/aos-api/aos_api/ecommerce_analyst_stage_review_runtime.py`
- `services/aos-api/tests/test_ecommerce_analyst_stage_review_runtime.py`
- 本 plan/files/verification
- closure manifest

## 验收与下一门

三阶段真实隔离 Task runtime 均生成与包协议一致的 payload/expected，兼容 wrapper 返回不变；数据漂移、后继启动、缺 checkpoint、跨租户继续拒绝。下一波实现 responsibility proof reader，再实现 Eval/source proof reader，最终组合五门。
