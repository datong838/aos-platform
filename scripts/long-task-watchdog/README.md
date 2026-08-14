# Codex 长任务断流 Watchdog

该守护只服务显式登记的 Codex thread。它从 Codex 本地 SQLite 查到 rollout transcript，判断“最新用户消息之后是否存在 `final` 或 `final_answer` assistant 消息”。若没有完成消息且 transcript 超过宽限期无变化，并且最新 `task_started` 已有对应 `task_complete`，才认为该 turn 疑似异常中断；仍在运行的 turn 不允许恢复副本并发介入。

恢复策略：首次检测只执行一次 `codex exec resume`；瞬时失败后按 5、10、15、20……分钟线性退避，最大间隔 60 分钟。ChatGPT/backend 网络故障、超时、非零退出或没有新增可见 final 不按累计次数永久熔断；配置、目录、可执行文件或权限等确定性本地错误才停止并等待显式复位。互斥锁防止 `launchd` 重叠执行。每轮恢复有独立 episode；只有当前 episode 的命令成功退出且同一 transcript 写入更新的 assistant `final/final_answer`，才可标记 recovered。这里的 recovered 只表示同一任务已被唤醒并可见结束，业务是否继续必须由恢复 Agent 按实际检查点判定。

运行状态会持久化 `consecutive_failures`、`last_retry_delay_seconds`、`next_retry_at`、`total_attempts` 和 `last_error`，便于区分“正在渐进退避”与“确定性配置错误”。一旦出现新的可见 `final/final_answer`，失败计数与退避时间立即归零。

安全边界：

- 不匹配聊天正文中的错误字符串。
- 不传 API Key，并主动从子进程环境移除常见 Key。
- 不使用 `--dangerously-bypass-approvals-and-sandbox`。
- 只允许通过配置中的精确 `additional_writable_dirs` 增加恢复所需可写目录；拒绝 `/`、用户主目录等宽泛目录。
- 不创建新 thread，只恢复配置中的同一 session。
- 默认宽限 300 秒；尚未返回的工具调用同样只保护 300 秒。超过 5 分钟无 transcript 心跳即进入恢复判定，避免工具调用残留永久阻塞续跑。
- Watchdog 唤醒后的第一条用户可见消息必须先声明“外部 Watchdog 检测到任务中断并已恢复本任务”，再把恢复指令视为路由提示，按 Git、检查点、Delivery Receipt、Lease 和共享记忆门禁核对真实状态。只有判定为 `CONTINUE` 才继续；已完成、评审门、环境阻塞或 Lease 冲突必须 no-op 并报告依据。
- 任务结束后将 `config.json` 的 `enabled` 改为 `false` 并卸载 LaunchAgent。

确定性配置错误停止后，先查看状态并修复权限、协议或环境问题，再显式复位：

```bash
python3 watchdog.py --status
python3 watchdog.py --reset-circuit
```

本地状态：`~/.codex/long-task-watchdog/`（配置、运行状态和互斥锁均为本机文件，不进 Git）。

测试：

```bash
cd /Users/ddt/work/projects/ai_agent/aos-platform/scripts/long-task-watchdog
python3 -m unittest -v test_watchdog.py
```
