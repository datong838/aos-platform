# DN 正式退休与 DO direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `407cc984`：DN saved-snapshot attempt `a2107628…` failed **rev4**；
  definition **262** disabled；Host **16967**；18181=0、worker=0。
- 下一环：DN 退休 → DO successor → DO saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../do-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dn_terminal_retirement.py` |
| 3–5 | `scripts/a0v_do_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威（封板）

- HEAD 封板前 `407cc984`；DO `e748c240…` / `93b514ad…`；九路 **324/351**；Host **22443**；etag 5。
- detach legacy **323/350**；definition **262** disabled。
- health baseline 2 → 14（+12）。

## 串行 1–6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan（本文件） |
| 2 | GREEN | SIGTERM Host 16967 + released retirement（detach `35a465a7…`） |
| 3 | GREEN | DO create→enable（install `e748c240…` / gen `93b514ad…`） |
| 4 | GREEN | 注册 + cutover **324/351** |
| 5 | GREEN | health +12（baseline 2→14；binding rev6/epoch3） |
| 6 | GREEN | verification/commit → 自动 DO saved-snapshot |

## 停止条件

第二 Host/worker、商城源读、未知重发 → fail closed。不 push。
