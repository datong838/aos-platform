# DP 保存快照恢复与单一自然 attempt 方案（2026-09-22）

## 上位方案复习

- 上一波 `cb860ce5`：DP cutover 九路 **327/354**，binding rev6/epoch3；唯一 Host **25817**；
  definition 仍为 DO **265** disabled / recovery **87** /
  `sha256:6c3a170bb709282587f41dce243c66575a6e182d3e04d3819102aec1a57be16e`。
- 字母链：DP saved-snapshot →（封板后）DP 退休 + DQ successor。BG-00。
- 无页面改动 → 浏览器验收 **N/A**。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dp-saved-snapshot-recovery-plan-20260922.md` |
| 2–6 | `scripts/a0v_dp_saved_snapshot_recovery.py` |
| 2 | `scripts/a0v_dp_product_controlled_api.py` |
| 4 | `scripts/a0v_dp_snapshot_product_api.py` / `a0v_dp_terminal_supervisor.py` |
| 5–6 | `scripts/a0v_dp_attempt_guard.py` |
| 6 | verification + tests overlay |
| — | docs `leases.json` TASK `A0V-DP-SNAPSHOT-WORKER-20260922`（**不**进 freeze commit） |

## 当前权威（封板）

- HEAD 封板前 `cb860ce5`；DP `d2d3c478…` / `b15f1733…`；Host 25817；etag **5**。
- transfer **266** → recovery **88** → enable **267** → pause **268**。
- attempt `dec64efe…` failed **rev5** / IngressJournalConflict。

## 串行 1-6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan/preflight（本文件） |
| 2 | GREEN | 纯 HTTP 18181；Host 25817 不动；prepare/schedule-ingest/controls → SIGTERM API |
| 3 | GREEN | transfer **266** / renew **88** / enable **267**；sourceReads=0 |
| 4 | GREEN | 唯一 worker + Lease `A0V-DP-SNAPSHOT-WORKER-20260922` |
| 5 | GREEN | 连续观察至 terminal attempt `dec64efe…` failed rev5 |
| 6 | GREEN | pause-terminal **268** + verification + pytest + commit → 自动 DP 退休 + DQ successor |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
