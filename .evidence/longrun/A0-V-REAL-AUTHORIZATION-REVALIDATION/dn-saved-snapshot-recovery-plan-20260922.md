# DN 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `0435a8e1`：DN cutover 九路 **321/348**，binding rev6/epoch3；唯一 Host **16967**；
  definition 仍为 DM **259** disabled / recovery **85** /
  `sha256:993275753ba8c461f9bcadbf5ce6f7d846e4aab542d500bb46b1046ed4296705`。
- 字母链：DN saved-snapshot →（封板后）DN 退休 + DO successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dn-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dn_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dn_product_controlled_api.py` |
| 4 | `scripts/a0v_dn_snapshot_product_api.py` / `a0v_dn_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dn_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DN-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威（封板）

- HEAD 封板前 `0435a8e1`；DN `2cb67f0a…` / `e8b25248…`；Host 16967；etag **5**。
- transfer **260** → recovery **86** → enable **261** → pause **262**。
- attempt `a2107628…` failed rev4 / IngressJournalConflict。

## 串行 1-6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan/preflight（本文件） |
| 2 | GREEN | 纯 HTTP 18181；Host 16967 不动；prepare/schedule-ingest/controls → SIGTERM API |
| 3 | GREEN | transfer **260** / renew **86** / enable **261**；sourceReads=0 |
| 4 | GREEN | 唯一 worker + Lease `A0V-DN-SNAPSHOT-WORKER-20260922` |
| 5 | GREEN | 连续观察至 terminal attempt `a2107628…` failed rev4 |
| 6 | GREEN | pause-terminal **262** + verification + pytest + commit → 自动 DN 退休 + DO successor |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
