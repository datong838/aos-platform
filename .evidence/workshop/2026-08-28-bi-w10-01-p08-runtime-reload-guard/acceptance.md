# BI-W10-01 P08 API 运行态所有权守护验收

- 截止：`2026-08-28T07:49:46.497565Z`
- 租户：`org-org/dev-project`
- 分支/基线：`m1@6062eb0283bf4dcf6065adbf20fe0efdb79cd688`
- 任务：`BI-W10-01-P08-RUNTIME-RELOAD-GUARD`
- 边界：未手工执行 Pipeline，未重放 DLQ，未修改栖月汇业务数据，未 apply migration，未发布。

## 根因与修复

既有 `ensure-api.sh --restart` 只轮询 `/v1/health`。当 8080 被旧进程持有时，新进程可因地址冲突退出，而旧进程继续返回 200，导致脚本错误宣称重载成功。新增 `api_runtime_guard.py` 后，成功条件收紧为：PID 文件有效、PID 存活、命令包含 `uvicorn` 与 `aos_api.main:app`、且 8080 的唯一 LISTEN owner 精确等于该 PID。

通用恢复入口同时显式设置 `AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED=false`，避免 P08 连续性恢复隐式继承环境中的 Provider 健康维护开关。第一次启动复核发现旧环境曾触发 3 次文本 Provider 健康探测；确认后立即整改并重启。整改后日志切片中 `api.agnes-ai.cn=0`、`provider_health_tick=0`、`qyh_cron_run=0`，未继续外呼，也未 catch-up 运行。

## 测试

- 运行态守护 + JDBC 隧道缓存 + Cron slot：`38 passed`。
- SourceAdapter + live executor + SourceReadiness 相邻累计：`56 passed`。
- `bash -n scripts/demo/ensure-api.sh`：GREEN。
- `compileall scripts/demo/api_runtime_guard.py`：GREEN。
- 作用域 `git diff --check`：GREEN。

## 真实运行回读

- 新进程 PID：`68386`；启动：`2026-08-28 15:47:35 +08:00`。
- 运行态守护：`RUNTIME_OWNER_EXACT`；`listenerPids=[68386]`；`127.0.0.1:8080/v1/health` 为 HTTP 200。
- 启动日志：`startup_qyh_real_cron_ready count=12`、`startup_qyh_real_cron_worker_started interval_seconds=15`、`startup_aip_text_provider_health_maintenance_disabled`。
- 计划：P01～P12 共 `12/12 enabled`。
- SourceReadiness：`10 ready / 2 failed`，`12/12 reconciliation pass`；整体仍为 `failed`。
- source/projection：十二类逐类相等；负向 canary `0/0`。
- P07 最新仍为 `2026-08-28T00:00:14.376592Z failed`；P08 最新仍是前一日失败，证明当天自然 slot 缺失未被补写；P09 仍保留 `startedAt=2026-08-28T01:45:25.370555Z` 的历史时序异常。

## 结论

`P08_RUNTIME_RELOAD_GUARD_CODE_AND_RUNTIME_GREEN / NATURAL_P08_SLOT_PENDING / NO_CATCH_UP / NO_RELEASE`。

本结论只关闭 API 运行态所有权与恢复入口副作用边界，不把历史缺失的 P08 run 改判为 GREEN。下一关闭条件仍是后续自然 09:00 Asia/Shanghai slot 的新 P08 run、DLQ 与同截止 SourceReadiness；不得手工补跑。
