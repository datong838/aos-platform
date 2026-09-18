# a0v089 attempt 终态原因持久化方案

## 1. 问题与目标

- 现有 `extension_runtime_execution_attempt` 与 event 只保存终态，AM 两次失败无法从权威记录区分业务异常、
  control 到期或 heartbeat 故障。
- 新字段只保存固定 reason code 和异常类型名，不保存异常正文、SQL、凭据、源数据或第三方响应。
- 历史 succeeded/failed/abandoned 行保持 nullable，不根据时间相关性追填原因；a0v089 后的新终态由数据库 trigger
  强制约束。

## 2. 文件级清单

- migration：`services/aos-api/alembic/versions/a0v_089_runtime_attempt_terminal_reason.py`
- 单步部署器：`scripts/a0v_runtime_attempt_terminal_reason_deploy.py`
- attempt Owner：`services/aos-api/aos_api/extension_runtime/generation_attempts.py`
- recoverable context：`services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py`
- signed-read 调用点：`services/aos-api/aos_api/extension_runtime/ui_read_worker_store.py`
- PostgreSQL/部署/调用点测试：
  `services/aos-api/tests/extension_runtime/test_generation_attempts_pg.py`、
  `services/aos-api/tests/extension_runtime/test_a0v_runtime_attempt_terminal_reason_deploy.py`、
  `services/aos-api/tests/extension_runtime/test_ui_read_request_pg.py`。

## 3. 数据约束

- head 与 event 各增加 nullable `terminal_reason_code`、`terminal_error_type`。
- reason code 仅允许：recoverable execution exception、ingress cancelled/deadline、heartbeat failure/stop timeout、
  lease expired，以及 UI read 已有的六个固定 failure code。
- error type 若非空，只允许 1..160 个 ASCII 字母、数字、点和下划线，首字符必须是字母或下划线。
- running/succeeded 必须两字段为空；a0v089 后 failed 必须有 reason；abandoned 固定 reason 且 error type 为空。
- event 的 reason/error 必须与同 revision 的 head 一致；head 更新与 event 插入仍在同一调用事务。

## 4. 分类与优先级

1. heartbeat 线程无法停止：`RECOVERABLE_HEARTBEAT_STOP_TIMEOUT`。
2. heartbeat renew/race 失败：`RECOVERABLE_HEARTBEAT_FAILED`。
3. 主执行抛 `INGRESS_CANCELLED`：`RECOVERABLE_INGRESS_CANCELLED`。
4. 主执行抛 `INGRESS_DEADLINE_EXCEEDED`：`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`。
5. 其他主执行异常：`RECOVERABLE_EXECUTION_EXCEPTION`。
6. 过期回收：`ATTEMPT_LEASE_EXPIRED`；UI read 使用它自身已经验证过的 failure code。

heartbeat 安全失败优先于同时存在的业务异常，因为 attempt owner 已失去可靠续租能力。异常类型取实际异常类的
`__name__`，仅在白名单字符和长度验证后落库。

## 5. 验证与退出条件

- 先用 PostgreSQL 测试证明失败无 reason、未知 reason、原始异常正文和 head/event 不一致均 fail closed。
- 验证成功 reason 为空、failed 分类正确、expired abandoned 固定、UI read failure 正确映射、历史空值兼容。
- migration 单一 head、部署器幂等、`py_compile`、专项回归、`git diff --check` 全绿。
- 仅提交上述文件与本方案/验证证据；不部署、不重载、不产生 AN，直至相邻 Host 续租闭包完成。
