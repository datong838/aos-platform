# Codex 长任务断流 Watchdog

该守护只服务显式登记的 Codex thread。它从 Codex 本地 SQLite 查到 rollout transcript，判断“最新用户消息之后是否存在 final assistant 消息”。若没有 final 且 transcript 超过宽限期无变化，则认为该 turn 疑似异常中断。

恢复策略：首次检测立即执行两次 `codex exec resume`；均失败后按 300 秒退避，每到期只重试一次，直到恢复成功。互斥锁防止 `launchd` 重叠执行。

安全边界：

- 不匹配聊天正文中的错误字符串。
- 不传 API Key，并主动从子进程环境移除常见 Key。
- 不使用 `--dangerously-bypass-approvals-and-sandbox`。
- 不创建新 thread，只恢复配置中的同一 session。
- 默认宽限 300 秒；尚未返回的工具调用最多保护 4 小时，兼顾长命令与崩溃工具调用最终可恢复。
- 任务结束后将 `config.json` 的 `enabled` 改为 `false` 并卸载 LaunchAgent。

本地状态：`~/.codex/long-task-watchdog/`（配置、运行状态和互斥锁均为本机文件，不进 Git）。

测试：

```bash
cd /Users/ddt/work/projects/ai_agent/aos-platform/scripts/long-task-watchdog
python3 -m unittest -v test_watchdog.py
```
