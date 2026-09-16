# Y5f4-Q 受控源失败分类与恢复资格验证

日期：2026-09-17
基线：`e0d7b776`

## 结论

`SOURCE_FAILURE_CLASSIFICATION_CODE_GREEN`。selected snapshot 读取继续只暴露固定正文 `SELECTED_SNAPSHOT_READ_FAILED`，但可信内部异常现在可携带闭合白名单 code；PipelineEngine 将其持久化为稳定错误码。未知、伪造或非连接器异常降级为 selected reader generic，不暴露 host、账号、密码、数据库、SQL 或原始异常文本。

本波没有重载 API、没有 SSH/JDBC 探测、没有启用 schedule、没有第二次源读取。P 波真实失败 `scr-09fc7164153f4d7d` 保持 failed/rows0，历史错误码不回填；schedule disabled，ingress/occurrence/attempt/Case Run 仍为 0，running/unresolved/canary 均为 0。

## 实现

- `jdbc_connector_runtime.connector_failure_code` 集中现有 SSH 与 MySQL 安全分类，未识别异常返回 `None`。
- `SelectedSnapshotReadError` 的 `str/repr` 固定为通用正文，`__cause__` 清空；构造器只接受闭合 code 集合，伪造值自动降级。
- `PipelineEngine._safe_error_code` 对 exact selected-reader 类型读取 code，对直接连接器异常复用同一分类器，其余保持 `PIPELINE_EXECUTOR_FAILED`。
- 无数据库迁移、无权限或业务状态改动。

## 验证

- JDBC、selected reader、PipelineEngine honesty、受控 executor 快速组合：87 passed。
- 覆盖 SSH 未就绪/auth/timeout 等安全码、MySQL 连接码、秘密不进入字符串/原因链、伪造 code 降级、原 source result 结构和执行异常脱敏。
- 两组 real-PG executor 文件共 8 项仍被既有 `test_lifecycle_pg` 环境门 skip；本波不把 skip 计为通过，也没有修改其门禁。
- Python compile、`git diff --check` 通过。
- 当前权威只读快照：`sc4-5l6y5f4-q-source-failure-classification-final.json`。

## 风险与下一波

安全码只有在部署新代码后的后继 run 才能产生；历史 P run 保持 generic，这是证据诚实性要求。下一波 Y5f4-R 先在不读取业务表的通道健康检查中确认 SSH tunnel 与 MySQL session，随后重载 API，并以新 authority/policy revision 建立一个新的自然 Cron 窗口。若通道仍失败，新的稳定码必须进入 `meta_schedule_run`；若成功，再继续 durable ingress → occurrence → Case/Run。不得把本次代码 GREEN 当成真实源恢复。
