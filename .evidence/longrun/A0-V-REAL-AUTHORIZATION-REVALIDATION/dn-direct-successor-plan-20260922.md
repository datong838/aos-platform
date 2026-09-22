# DM 正式退休与 DN direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `e56b4785`：DM saved-snapshot attempt `3e01547f…` failed **rev4**；
  definition **259** disabled；Host **11440**；18181=0、worker=0。
- 下一环：DM 退休 → DN successor → DN saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dn-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dm_terminal_retirement.py` |
| 3–5 | `scripts/a0v_dn_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威（封板）

- HEAD 封板前 `e56b4785`；DN `2cb67f0a…` / `e8b25248…`；九路 **321/348**；Host **16967**；etag 5。
- detach legacy **320/347**；definition **259** disabled。
- health baseline 5 → 17（+12）。

## 串行 1–6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan（本文件） |
| 2 | GREEN | SIGTERM Host 11440 + released retirement（detach `cf7a8c88…`） |
| 3 | GREEN | DN create→enable（install `2cb67f0a…` / gen `e8b25248…`） |
| 4 | GREEN | 注册 + cutover **321/348** |
| 5 | GREEN | health +12（baseline 5→17；binding rev6/epoch3） |
| 6 | GREEN | verification/commit → 自动 DN saved-snapshot |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
