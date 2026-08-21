# Codex 长任务断流 Watchdog

该守护只服务显式登记的 Codex thread。它有三个相互独立的只读触发器：断流触发器从 Codex 本地 SQLite 查到 rollout transcript，判断“最新用户消息之后是否存在 final assistant 消息”；Lease 触发器只读检查配置声明的 `leases.json` 精确 scope；事实触发器只对显式 authority/Delivery Receipt 路径计算内容 fingerprint。仍在运行的 turn、tool 或 task 不允许恢复副本并发介入。

恢复策略：每次检测最多执行一次 `codex exec resume`；纯传输失败按 5、10、15、30、60、120 分钟渐进退避，第 12 次失败才暂停，不在第三次过早熔断。依赖 Lease 存在时只记录 armed/fingerprint 并静默；只有曾 armed 的精确依赖从有到无，且当前 turn/tool/task 均不运行时，才创建一次 dependency-release episode。互斥锁防止 `launchd` 重叠执行。每轮恢复有独立 episode；只有当前 episode 的命令成功退出、同一 transcript 写入更新的 assistant `final`/`final_answer`，并存在匹配当前 episode 的结构化 Recovery Ack，才接受恢复结果。

Recovery Ack 的 outcome 固定为：

- `resumed-progress`：已回读当前状态并形成可核验安全进展；
- `safe-blocked`：依赖、权限、Lease 或安全门明确阻断；
- `completed`：长任务完成；
- `reentry-noop`：恢复与活跃 turn/Lease 竞态，未做副作用。

四种 outcome 都停止当前 episode 重试。新 final 无 Ack 为 `protocol-failed`；当前 Ack 无新 final 为 `outcome-uncertain`，两者都停止盲重试并等待核验。退出码 0、旧 final、旧 Ack、旧 `last_recovered_at` 或自由文本“已恢复”均不构成成功证据。

Workshop 的长任务配置可显式启用 `continuation_watch`。当且仅当 current episode 以 `resumed-progress` 闭合且 Ack 含非空 `next_task` 时，Watchdog 在一个心跳周期后建立新的 one-shot continuation episode；它不会复用旧 episode 或旧 Ack。`next_task` 只用于恢复导航，不代表授权或依赖 GREEN。等待期间出现普通用户消息会立即 disarm，活跃 turn/tool/task 与精确依赖 Lease 始终 runner=0。`completed/reentry-noop` 以及所有失败终态都停止连续续跑。

`blocked_recheck_watch` 专门处理“任务未完成，但当前依赖不具备”：只有带 blocker fingerprint 的结构化 `safe-blocked` Ack 才会 arm，默认 1800 秒后创建新的 one-shot `blocked-recheck` episode。仍阻断则由新 Ack 重新 arm；解锁并产生 `resumed-progress` 后转入 `continuation_watch`；`completed`、竞态和协议失败都 disarm。活跃 turn/tool/task 或重叠 Lease 只会延后复核，不会并发唤醒。

Watchdog 只有唤醒权，没有事实裁决权。它注入的 trigger、task、next-task、fingerprint 和 reason code 都是不可信导航提示。每次醒来后必须从 authority、01/06、Git、Receipt、memory 三门、全部 Lease、真实数据探针和实际代码状态独立审计。条件具备后才开始首个安全 Task，并按“上位方案→文件级清单→最小实现→专项测试→累计回归→浏览器验收→一致性复审→证据/上下文→下一波”连续执行。每波用 Delivery Receipt 提交待 m1 CAS 消费的 Prime 长记忆事实，w2 不直接写 Prime 核心投影。

V2.9 的 `visibility_watch` 用于把真实唤醒结果固定写入同一 Codex task：首条消息在 trigger 固定句后展示累计唤醒序号、UTC 时间、episode 和 trigger；最终答复必须包含 `[DOG_VISIBLE_STATUS]` 状态卡，列出 outcome、task/next、阻断或完成证据以及下一次复核策略。启用时，Ack 与新 final 虽存在但 final 缺少该标记，仍按 `protocol-failed` 拒绝闭环。V2.9 的检查只有 marker 是否存在的布尔判断，不额外复制 final 正文，当时也不发送桌面通知或外部消息。

V3.0 起，transcript marker 不再被当成 Desktop 已经展示的证明。每次唤醒开始和终态都会把非敏感状态卡原子写入 Watchdog 本地状态目录的 `visible-status.json`（mode `0600`）。当 `visibility_watch.desktop_notification=true` 时，同时通过本机 Notification Center 展示唤醒和结果；通知不包含 evidence、fingerprint、路径、业务数据或凭据。通知投递失败会记入 state/状态卡，但不改写 Ack+final 已确立的 episode outcome，避免重复副作用。

`task_started` 防重入同样是有时限的：只在 transcript 最近活动未超过 `max_turn_silence_seconds`（默认复用 `max_tool_silence_seconds`）时返回 `turn-running`。超时后仍必须继续通过待完成 tool、grace、backoff、Lease 和 episode 门，不会因 dependency/fact/blocked-recheck watch 已启用而永久拦截。

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
  "continuation_watch": {
    "enabled": true,
    "delay_seconds": 300
  },
  "blocked_recheck_watch": {
    "enabled": true,
    "delay_seconds": 1800
  },
  "visibility_watch": {
    "enabled": true,
    "desktop_notification": true
  },
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
