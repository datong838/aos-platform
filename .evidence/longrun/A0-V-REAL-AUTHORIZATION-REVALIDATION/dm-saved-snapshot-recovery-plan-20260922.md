# DM 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `6beed523`：DM cutover 九路 **318/345**，binding rev6/epoch3；唯一 Host **11440**；
  definition 仍为 DL **256** disabled / recovery **84** /
  `sha256:efddb5d4dd142266bccbe04b25b79ceba26837e23385fb17c02473c05cb4215a`。
- 字母链：DM saved-snapshot →（封板后）DM 退休 + DN successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dm-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dm_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dm_product_controlled_api.py` |
| 4 | `scripts/a0v_dm_snapshot_product_api.py` / `a0v_dm_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dm_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DM-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `6beed523`；DM `5103c27a…` / `4da719c7…`；Host 11440；18181=0；etag **7**。
- 前驱 definition DL `83453fb3…` rev256 /
  recovery84 / `sha256:efddb5d4dd142266bccbe04b25b79ceba26837e23385fb17c02473c05cb4215a`。
- 目标：transfer **257** → recovery **85** → enable **258** → pause **259**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan/preflight（本文件） |
| 2 | GREEN | 纯 HTTP 18181；Host 11440 不动；prepare/schedule-ingest/controls → SIGTERM API |
| 3 | GREEN | transfer **257** / renew **85** / enable **258**；sourceReads=0 |
| 4 | GREEN | 唯一 worker + Lease `A0V-DM-SNAPSHOT-WORKER-20260922` |
| 5 | GREEN | 连续观察至 terminal attempt `3e01547f…` failed rev4 |
| 6 | GREEN | pause-terminal **259** + verification + pytest + commit → 自动 DM 退休 + DN successor |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
