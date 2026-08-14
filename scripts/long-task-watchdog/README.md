# Codex 长任务断流 Watchdog

该守护只服务显式登记的 Codex thread。它从 Codex 本地 SQLite 查到 rollout transcript，判断“最新用户消息之后是否存在 final assistant 消息”。若没有 final 且 transcript 超过宽限期无变化，并且最新 `task_started` 已有对应 `task_complete`，才认为该 turn 疑似异常中断；仍在运行的 turn 不允许恢复副本并发介入。

恢复策略：每次检测最多执行一次 `codex exec resume`；纯传输失败按 5、10、15、20……分钟线性退避，最大 60 分钟并持续低频重试，不因第三次或任意固定次数的 ChatGPT/backend 传输失败永久熔断。互斥锁防止 `launchd` 重叠执行。每轮恢复有独立 episode；只有当前 episode 的命令成功退出、同一 transcript 写入更新的 assistant `final`/`final_answer`，并存在匹配当前 episode 的结构化 Recovery Ack，才接受恢复结果。

Recovery Ack 的 outcome 固定为：

- `resumed-progress`：已回读当前状态并形成可核验安全进展；
- `safe-blocked`：依赖、权限、Lease 或安全门明确阻断；
- `completed`：长任务完成；
- `reentry-noop`：恢复与活跃 turn/Lease 竞态，未做副作用。

四种 outcome 都停止当前 episode 重试。新 final 无 Ack 为 `protocol-failed`；当前 Ack 无新 final 为 `outcome-uncertain`，两者都停止盲重试并等待核验。退出码 0、旧 final、旧 Ack、旧 `last_recovered_at` 或自由文本“已恢复”均不构成成功证据。

安全边界：

- 不匹配聊天正文中的错误字符串。
- 不传 API Key，并主动从子进程环境移除常见 Key。
- 不使用 `--dangerously-bypass-approvals-and-sandbox`；使用 `workspace-write`、显式 `--add-dir` 和配置化 network access。
- 不创建新 thread，只恢复配置中的同一 session。
- 默认宽限 300 秒；尚未返回的工具调用同样只保护 300 秒。超过 5 分钟无 transcript 心跳即进入恢复判定，避免工具调用残留永久阻塞续跑。
- Watchdog 唤醒后的第一条用户可见消息只能声明“外部 Watchdog 检测到任务中断，正在恢复核验”。只有 `resumed-progress/completed` 的证据闭合后才可说“已恢复”；`safe-blocked` 必须说“已触发并安全阻断”。
- 任务结束后将 `config.json` 的 `enabled` 改为 `false` 并卸载 LaunchAgent。

Workshop 专用配置至少应包含：

```json
{
  "config_revision": "workshop-watchdog-v2",
  "expected_branch": "w2-workshop",
  "sandbox_mode": "workspace-write",
  "network_access": true,
  "writable_roots": ["/absolute/path/to/git-common", "/absolute/path/to/docs"],
  "ack_path": "/absolute/path/to/recovery-ack.json",
  "authority_path": "/absolute/path/to/authority.json",
  "retry_interval_seconds": 300,
  "max_retry_interval_seconds": 3600
}
```

恢复 turn 结束前调用 `watchdog.py --record-ack`。该命令自行采集 actual branch、HEAD、authority revision、Git common dir、所有 writable roots 和 loopback 网络，不允许调用方手写这些系统事实。Ack 文件强制 mode `0600`。

本地状态：`~/.codex/long-task-watchdog/`（配置、运行状态和互斥锁均为本机文件，不进 Git）。

测试：

```bash
cd /Users/ddt/work/projects/ai_agent/aos-platform/scripts/long-task-watchdog
python3 -m unittest -v test_watchdog.py
```
