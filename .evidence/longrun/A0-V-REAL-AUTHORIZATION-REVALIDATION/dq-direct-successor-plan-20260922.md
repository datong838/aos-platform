# DP 正式退休与 DQ direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `ee22ae83`：DP saved-snapshot attempt `dec64efe…` failed **rev5**；
  definition **268** disabled；Host **25817**；18181=0、worker=0。
- 下一环：DP 退休 → DQ successor → DQ saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dq-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dp_terminal_retirement.py` |
| 3–5 | `scripts/a0v_dq_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威（封板）

- HEAD 封板前 `ee22ae83`；DP `d2d3c478…` / `b15f1733…`；九路 **327/354** → legacy **329/356**。
- DQ `29e553b2…` / `b8d6900d…`；lock `sha256:0adb9ab7…`；etag **5**；Host **32752**。
- cutover **330/357**；binding rev6/epoch3；prepare `2209ba48…`；health baseline 3 → 15（+12）。
- definition 仍为 DP **268** disabled。
- 用户指令：本波封板后暂停（额度），不自动进 DQ saved-snapshot。

## 串行 1–6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan（本文件） |
| 2 | GREEN | SIGTERM Host 25817 + released retirement（disable `24db7253…` / detach `b37d6076…`） |
| 3 | GREEN | DQ create→enable etag5 |
| 4 | GREEN | 注册 + cutover **330/357**（op `13efdb15…`） |
| 5 | GREEN | health +12（Host 32752；`DQ_HEALTH_OBSERVATION_GREEN`） |
| 6 | GREEN | verification/commit → **暂停**（不进下一波） |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
