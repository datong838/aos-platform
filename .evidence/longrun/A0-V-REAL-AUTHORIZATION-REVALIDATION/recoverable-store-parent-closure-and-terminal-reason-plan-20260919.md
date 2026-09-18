# Recoverable Store parent feature 收口与终态原因持久化方案

## 1. 上位目标与当前事实

- 上位目标仍是原保存输入在 current authority、预算、审批、租户隔离和幂等 Receipt 下自然完成，不把测试
  通过替代真实首链。
- a0v084-a0v088、saved recovery transfer、current authority、recoverable Store attempt、heartbeat/drain 以及
  group completion 已在真实 AM 前序和本轮 PostgreSQL 场景中使用，但 parent feature 尚未形成完整 Git 闭包。
- 本轮 request identity 修复位于该未提交 parent feature 内；必须先形成可独立检出的可运行闭包，不能只提交
  子 hunk 并留下缺失 migration/Owner 的 HEAD。
- AM 两笔同 request hash attempt 均已 failed；第二笔在十二个 runtime control 同时到期后约 440ms 进入终态，
  当前实现没有持久化 exact failure reason，不能从时间相关性反推原因。
- definition 已按 exact failed-attempt gate 从 rev53 enabled 变为 rev54 disabled；installation 已经正式 detach，
  disable operation 成功、binding fenced、三项资源释放、九条 route 回到 legacy，AM 不再是合法运行对象。
- 当前没有 running attempt、runtime pending、authoritative outbox 或 dev-org canary；允许完成 parent Git 闭包，
  但 successor 仍须等待本闭包、相邻 Host 续租闭包、终态原因持久化与安全 reload 完成。

## 2. parent feature 最小闭包

### 数据库链

- `services/aos-api/alembic/versions/a0v_084_snapshot_saved_recovery_transfer.py`
- `services/aos-api/alembic/versions/a0v_085_snapshot_replacement_recovery_receipt.py`
- `services/aos-api/alembic/versions/a0v_086_snapshot_chained_replacement_recovery_receipt.py`
- `services/aos-api/alembic/versions/a0v_087_snapshot_prior_recovery_anchor.py`
- `services/aos-api/alembic/versions/a0v_088_recoverable_store_attempt.py`

### 运行时核心

- `services/aos-api/aos_api/extension_runtime/generation_attempts.py`
- `services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py`
- `services/aos-api/aos_api/pipeline_snapshot_group_{assessment_owner,completion,link_command,link_executor,object_executor}.py`
- `services/aos-api/aos_api/pipeline_snapshot_group_{recovery_authority,recovery_contracts,recovery_owner}.py`
- `services/aos-api/aos_api/pipeline_snapshot_group_{relationship_audit,relationship_journal}.py`
- `services/aos-api/aos_api/pipeline_snapshot_group_{retirement_executor,retirement_journal}.py`
- `services/aos-api/aos_api/pipeline_snapshot_schedule_{definition,service,worker}.py`

### 部署与验证闭包

- 五个 `scripts/a0v_snapshot_*_deploy.py` / `scripts/a0v_recoverable_store_attempt_deploy.py` 单步迁移器。
- 对应 migration deploy 测试、recovery contract/authority/assessment/object/link/retirement/schedule/attempt 的专项
  PostgreSQL 测试。
- `lease_renewal.py`、`verification_commit.py`、`preparation_owner.py` 等 Host 资源续租修复属于相邻但独立闭包，
  不因 parent feature 收口而夹带；另波按自身方案和测试提交。

## 3. 终态原因持久化后续

parent feature 收口后新增 a0v089，不回写历史猜测：

1. attempt head 增加 nullable 的安全 `terminal_reason_code` 与 `terminal_error_type`；历史 terminal 行允许为空。
2. `settle` 只允许受控枚举 reason code 与安全类型名，禁止原异常正文、凭据、SQL 或源数据进入数据库。
3. `RecoverableStoreAttempt.__exit__` 对当前异常做固定分类；heartbeat 自身失败与业务执行失败必须可区分。
4. attempt event 与 head 的 state/revision/reason 同一事务落定；成功不得带失败原因。
5. Worker 日志继续只输出安全 reason code；Guard 读取 head/event，不依赖瞬时进程日志。
6. AM 首笔历史原因保持 `unknown/not-recorded`，不得追填推测值。

## 4. 验证和提交顺序

1. 生成 tracked/untracked 文件清单，逐文件复核 import、migration 链和测试覆盖；排除 successor 实例脚本及其他
   用户工作树文件。
2. 运行 a0v084-a0v088 migration chain、recoverable attempt、saved recovery、authority、group completion 及 worker
   专项；耗时 PostgreSQL 场景不并发。
3. `py_compile`、Alembic single head、`git diff --check` 通过；浏览器门禁独立保持。
4. 只 stage parent 最小闭包并审查 cached diff，提交后确认工作树其他改动仍在。
5. 再进入 a0v089 Red/Green；只在空窗完成迁移与 Host 安全 reload，随后才允许 Worker 通过正式 definition
   自然产生 direct successor，仍禁止手工 `run_definition`。

## 5. 停止和安全条件

- 当前或新 attempt running 时禁止 retirement 及 schema/runtime reload。
- Store Receipt 查询未知、出现第二个并行 running owner、request hash 漂移、dev-org 非零或 migration 多 head 时，
  停止写动作并只读对账。
- 不触碰 230 L0，不 push，不重置、不清理、不覆盖现有未提交文件。
