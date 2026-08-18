# Cursor 会话 Dog（本 Agent 自管）

> 日期：2026-08-18  
> 范围：仅当前 Cursor AIP 会话。不改 Codex LaunchAgent、不改 w2-workshop Watchdog。

## 目标

只在本 Agent **停掉 / 失败 / 中断** 时唤醒；**正常 Loop 工作中不发哨兵**。

| 情况 | Dog |
|---|---|
| 正在工具调用、写代码、打 Health、封板 | 心跳新鲜 → 沉默 |
| 本波失败后主动写下 `failed-stopped` | 短延迟后唤醒一次 |
| 对话被中断、进程消失、心跳过期仍 `working` | 宽限期后唤醒一次 |
| 任务 `completed` | 永不唤醒 |
| 故意安静（`quiet_until`） | 到期前沉默 |

## 与 Loop 无关

Loop 是 Agent 自己续跑 AIP 波次。Dog 不代替 Loop，不定时喊人，不在你工作/Loop 时发哨兵。

只有心跳变成 `failed-stopped` / `interrupted`，或 `working|looping` 心跳过期（像被中断），才打印 `AGENT_LOOP_WAKE_aip_dog`。


- 不是 20 分钟定时 Tick（已停掉 `AGENT_LOOP_WAKE_aip_r2`）。
- 不是 Codex `com.aos.codex-long-task-watchdog`（那条只 resume Codex thread）。

## 状态

- 心跳/锁：`~/.cursor/aip-session-dog/`（不进 Git）
- 代码：本目录 `dog.py`
- 哨兵：`AGENT_LOOP_WAKE_aip_dog`

Agent 每波开工、波中、收口都要自己 `heartbeat`。失败收口写 `failed-stopped`，正常收口若还要继续则保持 `working` 并刷新心跳。
