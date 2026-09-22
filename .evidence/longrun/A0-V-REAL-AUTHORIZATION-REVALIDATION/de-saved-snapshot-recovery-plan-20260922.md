# DE 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `232d4bca`：DE cutover 九路 **294/321**，binding rev6/epoch3，RuntimePolicy rev11；
  唯一 Host **74459**；definition 仍为 DD **232** disabled / recovery **76**。
- 字母链：DE saved-snapshot →（封板后）DE 退休 + DF successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**（本波仅 runtime/substrate）。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../de-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_de_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_de_product_controlled_api.py` |
| 4 | `scripts/a0v_de_snapshot_product_api.py` / `a0v_de_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_de_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DE-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威

- HEAD `232d4bca`；DE `5d993078-18ec-4302-9286-7081a1463cc0` /
  `f5181ad4-e304-4533-aa4a-0f30b3c6dac3`；Host 74459。
- 前驱 definition DD `6e05658b…` rev232 /
  recovery76 / `sha256:8227326046fa3efd5f2449b35e0c497fe1b91b77ac253222e617969589879e2a`。
- 目标：transfer **233** → recovery **77** → enable **234** → pause **235**；
  attempt 终态实测 **rev5** / IngressJournalConflict（同 CJ/CS）；guard overlay predecessor_view revision=4。

## 串行 1-6

1. plan/preflight（本文件）
2. 纯 HTTP 18181；Host 74459 不动；prepare/schedule-ingest/controls → SIGTERM API
3. transfer/renew/enable，sourceReads=0
4. 唯一 worker + Lease
5. 连续观察至 terminal
6. pause-terminal + verification + pytest + commit → 自动 DE 退休 + DF successor

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。退休 preflight 前不得 mkdir `replacement-df`。
