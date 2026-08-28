# BI-W10-01 受限恢复环境运行态身份回读验收

- 截止：`2026-08-28T08:17:38Z`
- 租户：`org-org/dev-project`
- 任务：`BI-W10-01-RESTRICTED-RUNTIME-OWNER-READBACK`
- 基线：`aos-platform/m1@59864659`
- 边界：未重启 API，未手工执行 Pipeline，未重放 DLQ，未修改真实业务数据，未触发 Provider 维护、migration 或发布。

## 独立复现

Watchdog 受限环境中，`GET /v1/health` 返回 200，`lsof` 只显示 PID `68386` 监听 8080，但旧守护返回 `PROCESS_NOT_ALIVE`。根因为权限模型禁止 `kill(pid, 0)` 和 `ps`；POSIX `EPERM` 表示 PID 存在但当前主体无权发信号，不是进程死亡。

## 最小修复

- 正常环境仍优先用 `ps` 校验 `uvicorn` 与 `aos_api.main:app`。
- 只在命令行因权限不可读时，允许以“PID 精确独占 8080 + `lsof` cwd 精确等于 `services/aos-api`”作为受限回读身份证据。
- cwd 缺失/漂移、PID 不一致、多监听者和命令漂移仍全部失败关闭。
- `ensure-api.sh` 的“已在线”快捷路径也必须先通过 exact owner 守护，不再只凭 health 200 返回成功。

## 验证

- 守护专项：`17/17 passed`。
- JDBC/Cron/SourceAdapter/live executor/SourceReadiness 累计：`109/109 passed`，7 条既有 warning。首次累计回归暴露 Cron 关闭用例会继承本地 Provider 维护开关，已将该用例收紧为同时关闭 Provider 后重跑全组 GREEN；生产启动逻辑未改。
- `bash -n scripts/demo/ensure-api.sh`：GREEN。
- `compileall scripts/demo/api_runtime_guard.py`：GREEN。
- 受限环境实际回读：`RUNTIME_OWNER_EXACT`，`listenerPids=[68386]`，PID 未重启。
- 无 `--restart` 执行 `ensure-api.sh`：先输出 exact owner JSON，再返回 `already up`。
- SourceReadiness 新鲜回读：截止 `2026-08-28T08:27:29.536453Z`，`10 ready / 2 failed`，P07/P08 均仍为 `failed`；未伪造恢复。

## 结论

`RESTRICTED_RUNTIME_OWNER_READBACK_GREEN / NATURAL_P07_P08_WINDOW_PENDING / NO_RESTART / NO_MANUAL_RUN / NO_EXTERNAL_EFFECT / NO_RELEASE`。

涉及页面的视觉与组件实现未变更，浏览器验收不适用；既有八菜单视觉/功能证据未被本切片改写。
