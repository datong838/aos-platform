# DH 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `f59255db`：DH cutover 九路 **303/330**，binding rev6/epoch3，RuntimePolicy rev11；
  唯一 Host **86843**；definition 仍为 DG **241** disabled / recovery **79**。
- 字母链：DH saved-snapshot →（封板后）DH 退休 + DI successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dh-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dh_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dh_product_controlled_api.py` |
| 4 | `scripts/a0v_dh_snapshot_product_api.py` / `a0v_dh_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dh_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DH-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `f59255db`；DH `10d583ad…` / `107a24f5…`；Host 86843。
- 前驱 definition DG `d551d104…` rev241 /
  recovery79 / `sha256:1c1e3cd66d597f5157eb6be4f4d6a00a9b50f5d077c5329f026247398d5f6ca4`。
- 目标：transfer **242** → recovery **80** → enable **243** → pause **244**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 86843 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DH 退休 + DI successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。退休 preflight 前不得 mkdir `replacement-di`。
