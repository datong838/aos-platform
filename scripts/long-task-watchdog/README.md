# Codex 长任务断流 Watchdog

该守护只服务显式登记的 Codex thread。它有三个相互独立的只读触发器：断流触发器从 Codex 本地 SQLite 查到 rollout transcript，判断“最新用户消息之后是否存在 final assistant 消息”；Lease 触发器只读检查配置声明的 `leases.json` 精确 scope；事实触发器只对显式 authority/Delivery Receipt 路径计算内容 fingerprint。仍在运行的 turn、tool 或 task 不允许恢复副本并发介入。

恢复策略：每次检测最多执行一次 `codex exec resume`；纯传输失败按 5、10、15、30、60、120 分钟渐进退避，第 12 次失败才暂停，不在第三次过早熔断。依赖 Lease 存在时只记录 armed/fingerprint 并静默；只有曾 armed 的精确依赖从有到无，且当前 turn/tool/task 均不运行时，才创建一次 dependency-release episode。互斥锁防止 `launchd` 重叠执行。每轮恢复有独立 episode；只有当前 episode 的命令成功退出、同一 transcript 写入更新的 assistant `final`/`final_answer`，并存在匹配当前 episode 的结构化 Recovery Ack，才接受恢复结果。

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
- 依赖释放唤醒后的第一条用户可见消息只能声明“依赖 Watchdog 检测到迁移 Lease 已释放，正在重新核验后继续”。它只表示依赖变化触发核验，不表示工作已恢复。
- 依赖监控只匹配显式 `scope_tokens`；存在其他不重叠 AIP Lease 不会阻断 Workshop，也不会读取 w1-aip 工作区。
- 外部事实监控首次只建 baseline；仅 idle 且无精确 Lease blocker 时，新的 fingerprint 才单次唤醒。它只存 hash，不把文档正文写入 state/log/prompt；符号链接、缺失路径和超限文件失败关闭。
- 外部事实变化的固定首句是“依赖 Watchdog 检测到外部交付事实已变化，正在重新核验后继续”。变化不等于依赖 GREEN，恢复 turn 仍必须全量复核。
- dependency release/fact change 恢复尚未闭合时，如果同一 thread 出现更新的非 Watchdog 用户消息，视为用户已人工接管：当前 episode 记为 `manual-reentry/reentry-noop`，清零重试并消费旧 release 事件，但不写 `last_recovered_at`、不声称自动恢复成功。Watchdog 自己带协议标记的 resume prompt 不属于人工接管。
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
  "retry_schedule_seconds": [300, 600, 900, 1800, 3600, 7200],
  "max_transport_failures": 12,
  "dependency_watch": {
    "enabled": true,
    "leases_path": "/absolute/path/to/memory/leases.json",
    "scope_tokens": ["services/aos-api/alembic/versions"],
    "ignore_task_ids": ["current-workshop-task-id"]
  },
  "fact_watch": {
    "enabled": true,
    "paths": [
      "/absolute/path/to/authority.json",
      "/absolute/path/to/memory/receipts/deliveries"
    ],
    "max_files": 10000,
    "max_file_bytes": 16777216
  }
}
```

恢复 turn 结束前调用 `watchdog.py --record-ack`。该命令自行采集 actual branch、HEAD、authority revision、Git common dir、所有 writable roots 和 loopback 网络，不允许调用方手写这些系统事实。Ack 文件强制 mode `0600`。

本地状态：`~/.codex/long-task-watchdog/`（配置、运行状态和互斥锁均为本机文件，不进 Git）。

测试：

```bash
cd /Users/ddt/work/projects/ai_agent/aos-platform/scripts/long-task-watchdog
python3 -m unittest -v test_watchdog.py
```
