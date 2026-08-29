# BI-W10 P10 当前 SSH 传输路径诊断

## 边界

- 任务：`BI-W10-P10-SSH-CONNECT-TIMEOUT-CURRENT-PATH-DIAGNOSIS-20260829`。
- 仅核验开发 API 正常启动预建、进程/本地监听状态、健康检查与 canonical SourceReadiness。
- 未手工运行、重放或补跑 P01～P12，未查询或修改源业务数据，未读取/输出凭据、端点或 PII，未增加重试或超时，未调用 Provider、迁移或发布。

## 当前事实

- 旧 P10 自然运行：`scr-cf35da6349bf40e4`，计划时槽 `2026-08-29T03:00:00Z`，状态 failed，0 行，旧记录 error code 为 `PIPELINE_EXECUTOR_FAILED`；保持不可变。
- 新 API owner：PID 40708，启动于 `2026-08-29 21:03:07 Asia/Shanghai`，加载代码提交 `45104fe9`。
- 当前启动预建：唯一 SSH source 在 `1442ms` 内建立转发，`ok=1 / failed=0 / total=1`；本地监听进程持续存在。
- 前一 owner 的同一启动预建也在 `1638ms` 内成功，说明当前配置路径可连续建立转发。
- `/v1/health` 返回 200；canonical SourceReadiness 仍保留旧 P10 failed，不以当前 tunnel 健康替代下一自然运行证据。

## 诊断结论

旧 `CONNECT_TIMEOUT` 在当前代码与配置下不可重复，未发现可安全归因的确定性实现缺陷。修改 SSH 参数、扩大超时或增加重试反而会破坏既有有界失败合同，因此本任务不改业务代码。第 129 节稳定分类已经由现 owner 加载，下一自然运行将形成新的独立稳定码与运行事实。

## 验收

- 当前 API owner continuity：GREEN。
- SSH startup prebuild：GREEN，`1/1`。
- 本地转发监听：GREEN。
- health：GREEN。
- 历史 run 不可变与可信失败：GREEN。
- 页面改动：无，浏览器验收 N/A。

## 裁决

`P10_CURRENT_SSH_TRANSPORT_PATH_GREEN_HISTORICAL_RUN_REMAINS_FAILED_NO_REPLAY`

本裁决关闭当前路径的确定性诊断，不把 P10 改判为 ready；继续开发不依赖 12/12 的八菜单功能与数据质量切片，并在下一自然时槽重新读取权威运行事实。
