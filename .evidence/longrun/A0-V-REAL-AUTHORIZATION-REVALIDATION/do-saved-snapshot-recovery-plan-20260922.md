# DO 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `7041608f`：DO cutover 九路 **324/351**，binding rev6/epoch3；唯一 Host **22443**；
  definition 仍为 DN **262** disabled / recovery **86** /
  `sha256:59ddef1063f2e2ed0fbf4df77fd74a91399a554e56395f72bb3ec92f41854cb5`。
- 字母链：DO saved-snapshot →（封板后）DO 退休 + DP successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../do-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_do_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_do_product_controlled_api.py` |
| 4 | `scripts/a0v_do_snapshot_product_api.py` / `a0v_do_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_do_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DO-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威（封板）

- HEAD 封板前 `7041608f`；DO `e748c240…` / `93b514ad…`；Host 22443；etag **5**。
- transfer **263** → recovery **87** → enable **264** → pause **265**。
- attempt `43556e02…` failed **rev5** / IngressJournalConflict。

## 串行 1-6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan/preflight（本文件） |
| 2 | GREEN | 纯 HTTP 18181；Host 22443 不动；prepare/schedule-ingest/controls → SIGTERM API |
| 3 | GREEN | transfer **263** / renew **87** / enable **264**；sourceReads=0 |
| 4 | GREEN | 唯一 worker + Lease `A0V-DO-SNAPSHOT-WORKER-20260922` |
| 5 | GREEN | 连续观察至 terminal attempt `43556e02…` failed rev5 |
| 6 | GREEN | pause-terminal **265** + verification + pytest + commit → 自动 DO 退休 + DP successor |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
