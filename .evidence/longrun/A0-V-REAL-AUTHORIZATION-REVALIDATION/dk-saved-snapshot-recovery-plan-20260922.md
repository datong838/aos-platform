# DK 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `c8eb65f3`：DK cutover 九路 **312/339**，binding rev6/epoch3；唯一 Host **96590**；
  definition 仍为 DJ **250** disabled / recovery **82**。
- 字母链：DK saved-snapshot →（封板后）DK 退休 + DL successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dk-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dk_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dk_product_controlled_api.py` |
| 4 | `scripts/a0v_dk_snapshot_product_api.py` / `a0v_dk_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dk_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DK-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `c8eb65f3`；DK `b651f4d7…` / `fb16d08b…`；Host 96590。
- 前驱 definition DJ `aca93a08…` rev250 /
  recovery82 / `sha256:52d22d57c12bbbfe46328b35dcf130858e9b86548703795b0a7b593a1336e57f`。
- 目标：transfer **251** → recovery **83** → enable **252** → pause **253**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 96590 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DK 退休 + DL successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
