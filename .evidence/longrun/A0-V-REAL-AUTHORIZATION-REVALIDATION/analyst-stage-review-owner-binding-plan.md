# Analyst stage review Owner 双事务绑定方案

日期：2026-09-12

基线：`646c79c3`

状态：APPROVED_FOR_IMPLEMENTATION（m1 单写者持续开发，不 push）

## 目标

在既有 `StageReviewDatabasePhases` 与 `AnalystStageDecisionStore` 之间增加窄绑定器。绑定器复用宿主命令身份合同，在两笔事务中锁定相同 decision target 与 idempotency key，快照真实 StageDecision head 和 authority Receipt；提交前 exact 重读一致，并且四种包侧校验结果齐全时，才调用现有唯一 Owner 写入。

本波不实现 Task/Plan/Run、职责、runtime、Eval 的复合 authority reader。绑定器要求显式同步 `read_authority` 依赖返回 authority snapshot 与四种 exchange；下一波用真实 reader 替换测试桩。本波不提供 HTTP/worker 入口，避免不完整 reader 被误当作发布授权。

## Rules

1. 命令 envelope 只允许 `scope/item/actor/key/expectedVersion` 五字段；scope 必须等于构造时的 `TenantScope`，item 必须通过现有 Pydantic、stable decision id 与 canonical hash。
2. 把现有命令内联身份校验提取为纯宿主 helper，旧同步命令必须复用它，行为不变。
3. prepare 与 current reload 都必须在 `HostTransaction` 内按排序后的两个 advisory key 加锁，再调用同步 `read_authority`，不得相信调用方提供的 Owner state。
4. Owner snapshot 至少包含 tenant、decisionId、head 当前 revision/version（可为空）和明确为空的 Receipt；原生 JSON canonical 化后进入 prepared 封印。若同 key Receipt 已存在，本绑定在 authority reader 前拒绝，必须由产品服务的 Owner replay fast path 精确回读，禁止重新运行四门。
5. `read_authority` 必须返回非空原生 JSON snapshot，以及 kind 恰好为 command/slot/runtime/eval 四种且唯一的 exchanges；少一项、额外项或异步依赖均 fail closed。
6. publisher 再次复核命令、prepared、四项 results 与 exchanges exact 对应，随后只调用既有 `AnalystStageDecisionStore.put` 一次。
7. 不新增表、不迁移、不改已安装 1.4.0、不接产品路由、不触碰真实租户数据；未知 IPC 结果仍由 coordinator 阻断提交事务。

## 文件

- `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py`
- `services/aos-api/aos_api/ecommerce_analyst_stage_review_owner_binding.py`
- `services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py`
- `services/aos-api/tests/extension_runtime/test_analyst_stage_review_owner_binding.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-stage-review-owner-binding-plan.md`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-stage-review-owner-binding-files.json`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/analyst-stage-review-owner-binding-verification.md`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 验收

1. 真实隔离 PostgreSQL 证明首次发布写入 StageDecision revision/head/Receipt，并可由 Store exact 回读。
2. prepare 后若 head 或相同 key Receipt 变化，第二事务 exact snapshot 不同并在 publisher 前拒绝。
3. 四种 exchange 缺失/重复、authority snapshot 空、命令 scope/hash/key/version 漂移全部零写。
4. 旧同步 `AnalystStageReviewCommandService` 的 accept/replay/revoke 与失败回滚回归不变。
5. 定向与阶段评审全回归、compileall、diff check、closure verifier 全绿；证据记录边界与 SHA256。

## 下一门

实现真实复合 authority reader：一次读取并封印 Task/Plan/Run、最新 StepRun、Checkpoint/Observation、Responsibility/Resolution、Eval report/contract/gate/source，并生成四种 exact package exchanges。完成后才可构造产品级异步 StageReviewCommand。
