# W5c3k 当前四来源配置 Stage 部分验证（2026-09-24）

## 结论

**STOPPED，零配置写入。** 原 stage 在 0600 intent 落盘后、调用 `append_configuration` 之前，被 `ConfigurationDocument.model_validate` 的严格 tuple 类型校验拒绝：冻结 JSON 的 `roleRefs`/`dataRefs` 是 list。错误边界明确，不能把已有 intent 当作可重试授权。全新 key `a0v-w5c3k-current-four-source-stage-20260924-v1` 对应配置记录0，同安装配置记录0，无 result 文件。

## 证据

- 方案 `2e4b33c4`；预检当前 active/etag5、binding rev1/epoch1 disabled/fenced/ready、Host PID17302 同 Job/三 held 资源、四来源 Policy rev13、九路/调度/canary正常。测试 32 passed、`git diff --check` 通过。
- 异常发生于本波脚本从 JSON 字典构造严格 `ConfigurationDocument`，在 `append_configuration` 调用前；只读回查 `configurations=0`、`stageCommands=0`、attempt0、受控源 claim40、meta_schedule_run53。W5c3j 独立 audit 仍 GREEN。未发 configure/enable、未读商城源。

## 下一波 W5c3kR

先方案，以最小代码修复 JSON→严格 tuple 模型恢复（原 `model_validate_json`），增加回归测试，使用**新私有 state 和新幂等键**在相同 live Job 仍 held 时重新预检/正式 stage；旧 W5c3k intent 永久冻结、不重发。若 Host/lease 漂移，停止写并走正式恢复。
