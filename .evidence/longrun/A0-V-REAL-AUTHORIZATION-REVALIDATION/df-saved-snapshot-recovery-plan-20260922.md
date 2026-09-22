# DF 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `bfc436b7`：DF cutover 九路 **297/324**，binding rev6/epoch3，RuntimePolicy rev11；
  唯一 Host **79478**；definition 仍为 DE **235** disabled / recovery **77**。
- 字母链：DF saved-snapshot →（封板后）DF 退休 + DG successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../df-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_df_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_df_product_controlled_api.py` |
| 4 | `scripts/a0v_df_snapshot_product_api.py` / `a0v_df_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_df_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DF-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `bfc436b7`；DF `a0639f78…` / `ec18c8c6…`；Host 79478。
- 前驱 definition DE `5d993078…` rev235 /
  recovery77 / `sha256:da03bcf65d367b30fc1c86b83d687ea90d752d306c353c866c4c9dff4d66668c`。
- 目标：transfer **236** → recovery **78** → enable **237** → pause **238**；
  attempt 终态可能 rev4 或 rev5 / IngressJournalConflict。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 79478 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DF 退休 + DG successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。退休 preflight 前不得 mkdir `replacement-dg`。
