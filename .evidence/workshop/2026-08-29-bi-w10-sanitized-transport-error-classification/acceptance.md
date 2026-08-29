# BI-W10 去敏传输错误分类验收

## 边界

- 任务：`BI-W10-SANITIZED-TRANSPORT-ERROR-CLASSIFICATION-20260829`。
- 租户事实边界保持 `org-org/dev-project`；本任务仅修改错误分类、调度记录合同与只读投影测试。
- 未手工运行、重放或补跑 P01～P12，未增加自动重试，未扩大连接/读取超时，未读取 Secret/PII，未修改真实业务数据，未调用 Provider，未执行迁移或发布。
- 本任务无页面改动，浏览器验收为 N/A。

## 实现

- `phase5_pipeline_engine.py` 把受控 SSH/JDBC 与 PyMySQL 运行异常归一为有限稳定码；任意未知异常保持 `PIPELINE_EXECUTOR_FAILED`。
- 所有分类都只持久化固定通用文案 `pipeline executor failed`，原始异常、端点、账号与业务数据不跨执行边界。
- `qyh_cron_scheduler.py` 原样持久化执行层稳定码；调度器自身意外异常改为固定 `SCHEDULE_EXECUTOR_EXCEPTION / schedule executor failed`，不再暴露异常类型或文本。
- `source_readiness.py` 继续使用既有 `meta_schedule_run.error_code` 权威字段；新增测试证明稳定码可原子投影到最新运行事实，不创建第二套状态。

## 稳定码

- SSH：`SSH_TUNNEL_NOT_READY`、`SSH_CONNECT_TIMEOUT`、`SSH_AUTHENTICATION_FAILED`、`SSH_CONNECTION_REFUSED`、`SSH_HOST_RESOLUTION_FAILED`、`SSH_HOST_KEY_VERIFICATION_FAILED`、`SSH_LOCAL_FORWARD_BIND_FAILED`、`SSH_FORWARD_FAILED`、`SSH_PROCESS_FAILED`。
- MySQL：`MYSQL_CONNECT_FAILED`、`MYSQL_SERVER_GONE`、`MYSQL_CONNECTION_LOST`。
- 未识别异常：`PIPELINE_EXECUTOR_FAILED`；调度边界自身异常：`SCHEDULE_EXECUTOR_EXCEPTION`。

## 验证

- 专项：`53 passed`，覆盖执行分类、调度持久化、调度异常脱敏与 SourceReadiness 最新运行投影。
- 累计：`133 passed`，覆盖 EC live executor、store assembly、pipeline honesty/resolver、JDBC runtime、Cron 以及 SourceReadiness API/contract/evidence/investigation/service/source。
- `git diff --check`：通过。
- `python -m compileall -q services/aos-api/aos_api`：通过。
- 完整 API 套件审计在 `152 passed / 6 failed` 时主动终止：5 项失败是迁移降级测试被当前不可降级 authority 数据按设计拒绝，1 项是写安装状态测试与权威库既有第 7 个实例冲突；这些测试不适用于当前权威开发库，也不位于本任务调用链。终止后确认 Alembic 仍为 `wcat_003 (head)`、8080 原 owner 未重启，专项 `53/53` 再次通过。

## 方案一致性与风险复审

- 与计划一致：只增加有限分类和既有字段投影，没有重试、补跑、超时放宽、第二套 authority 或原始异常持久化。
- 与可信空一致：错误码只说明失败类别，不把失败运行、零行或旧成功伪装为 ready。
- 与租户安全一致：分类器不读租户内容；调度和 SourceReadiness 仍经既有 tenant-scoped authority。
- 当前自然失败记录不会被追溯篡改；稳定码只作用于后续自然运行，这是不可变运行事实的预期行为。

## 裁决

`BI_W10_SANITIZED_TRANSPORT_ERROR_CLASSIFICATION_CODE_SCHEDULER_SOURCE_READINESS_GREEN_NO_REPLAY`

本任务完成后，下一项继续按自然运行事实做精确诊断与 8 菜单真实数据功能回读；不得用代码通过替代同 cutoff 的 SourceReadiness 运行事实。
