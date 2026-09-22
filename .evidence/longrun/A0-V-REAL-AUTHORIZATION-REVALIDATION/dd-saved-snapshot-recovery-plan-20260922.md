# DD 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `5d30d3b4`：DD cutover 九路 **291/318**，binding rev6/epoch3，RuntimePolicy rev11；
  唯一 Host **70991**；definition 仍为 DC **229** disabled / recovery **75**。
- 字母链：DD saved-snapshot →（封板后）DD 退休 + DE successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**（本波仅 runtime/substrate）。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dd-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dd_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dd_product_controlled_api.py` |
| 4 | `scripts/a0v_dd_snapshot_product_api.py` / `a0v_dd_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dd_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DD-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `5d30d3b4`；DD `6e05658b-5d0a-40ae-ab8e-81fcca5269db` /
  `422d2d5b-752a-4182-b1e8-831a8f63c2a1`；Host 70991。
- 前驱 definition DC `02d39eb8…` rev229 /
  `sha256:ca50bd7d360871e8a5d016361ce6faee27a683b1401bc822822f1e71edea9781`；
  recovery75 / `sha256:21518179c91919d832a5130e47079fdf0395802e3f738be25df26436071df757`。
- 目标：transfer **230** → recovery **76** → enable **231** → pause **232**；
  attempt 终态预期 **rev4** / IngressJournalConflict；guard overlay predecessor_view revision=4。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 70991 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DD 退休 + DE successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。退休 preflight 前不得 mkdir `replacement-de`。
