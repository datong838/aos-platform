# DJ 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `5c762322`：DJ cutover 九路 **309/336**，binding rev6/epoch3；唯一 Host **94313**；
  definition 仍为 DI **247** disabled / recovery **81**。
- 字母链：DJ saved-snapshot →（封板后）DJ 退休 + DK successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dj-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dj_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dj_product_controlled_api.py` |
| 4 | `scripts/a0v_dj_snapshot_product_api.py` / `a0v_dj_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dj_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DJ-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `5c762322`；DJ `aca93a08…` / `6ce73106…`；Host 94313。
- 前驱 definition DI `c8298a5d…` rev247 /
  recovery81 / `sha256:3831357759bd96db97ff3e24417a5b1841b9203ae608d8b20a89feccef0b6d0c`。
- 目标：transfer **248** → recovery **82** → enable **249** → pause **250**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 94313 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DJ 退休 + DK successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
