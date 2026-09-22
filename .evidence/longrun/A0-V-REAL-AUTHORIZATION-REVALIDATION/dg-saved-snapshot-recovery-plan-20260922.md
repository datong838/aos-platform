# DG 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `6b78e6b2`：DG cutover 九路 **300/327**，binding rev6/epoch3，RuntimePolicy rev11；
  唯一 Host **82684**；definition 仍为 DF **238** disabled / recovery **78**。
- 字母链：DG saved-snapshot →（封板后）DG 退休 + DH successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dg-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dg_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dg_product_controlled_api.py` |
| 4 | `scripts/a0v_dg_snapshot_product_api.py` / `a0v_dg_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dg_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DG-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `6b78e6b2`；DG `d551d104…` / `6c1780ab…`；Host 82684。
- 前驱 definition DF `a0639f78…` rev238 /
  recovery78 / `sha256:16ec5ac89f55dd59c04a042c0638b799b58cdd068fa5ae4d300736a6c1ff2a10`。
- 目标：transfer **239** → recovery **79** → enable **240** → pause **241**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 82684 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DG 退休 + DH successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。退休 preflight 前不得 mkdir `replacement-dh`。
