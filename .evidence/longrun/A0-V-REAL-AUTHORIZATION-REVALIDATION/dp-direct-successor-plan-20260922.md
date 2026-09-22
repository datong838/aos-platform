# DO 正式退休与 DP direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `0faa51e6`：DO saved-snapshot attempt `43556e02…` failed **rev5**；
  definition **265** disabled；Host **22443**；18181=0、worker=0。
- 下一环：DO 退休 → DP successor → DP saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dp-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_do_terminal_retirement.py` |
| 3–5 | `scripts/a0v_dp_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威（封板）

- HEAD 封板前 `0faa51e6`；DO `e748c240…` / `93b514ad…`；九路 **324/351** → legacy **326/353**。
- DP `d2d3c478…` / `b15f1733…`；lock `sha256:06c2ac6e…`；etag **5**；Host **25817**。
- cutover **327/354**；binding rev6/epoch3；prepare `9893b31e…`；health baseline 3 → 15（+12）。
- definition 仍为 DO **265** disabled。

## 串行 1–6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan（本文件） |
| 2 | GREEN | SIGTERM Host 22443 + released retirement（disable `1def9b65…` / detach `ad02a6ad…`） |
| 3 | GREEN | DP create→enable etag5 |
| 4 | GREEN | 注册 + cutover **327/354**（op `29f2f093…`） |
| 5 | GREEN | health +12（Host 25817；`DP_HEALTH_OBSERVATION_GREEN`） |
| 6 | GREEN | verification/commit → 自动 DP saved-snapshot |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
