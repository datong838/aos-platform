# DL 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `b4278583`：DL cutover 九路 **315/342**，binding rev6/epoch3；唯一 Host **1325**；
  definition 仍为 DK **253** disabled / recovery **83**。
- 字母链：DL saved-snapshot →（封板后）DL 退休 + DM successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dl-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dl_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dl_product_controlled_api.py` |
| 4 | `scripts/a0v_dl_snapshot_product_api.py` / `a0v_dl_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dl_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DL-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `b4278583`；DL `83453fb3…` / `f3a1f381…`；Host 1325；18181=0。
- 前驱 definition DK `b651f4d7…` rev253 /
  recovery83 / `sha256:e025a04befb60cbe64ce7861aeacd43e8c024c34f9ddf2624c6210f525923065`。
- 目标：transfer **254** → recovery **84** → enable **255** → pause **256**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 1325 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DL 退休 + DM successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
