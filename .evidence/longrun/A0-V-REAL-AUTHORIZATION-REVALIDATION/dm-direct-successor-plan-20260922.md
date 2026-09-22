# DL 正式退休与 DM direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `0a71cc8e`：DL saved-snapshot attempt `9558b0cd…` failed **rev4**；
  definition **256** disabled；Host **1325**；18181=0、worker=0。
- 下一环：DL 退休 → DM successor → DM saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dm-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dl_terminal_retirement.py` |
| 3–5 | `scripts/a0v_dm_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威

- HEAD `0a71cc8e`；DL `83453fb3…` / `f3a1f381…`；九路 **315/342**；Host 1325。
- 目标 detach legacy **317/344**；DM cutover **318/345**。
- 退休 preflight 前不得 mkdir `replacement-dm`。

## 串行 1–6

| 步 | 状态 | 说明 |
|---|---|---|
| 1 | GREEN | plan（本文件） |
| 2 | GREEN | SIGTERM Host + released retirement（detach `dac9f81b…`） |
| 3 | GREEN | DM create→enable（install `5103c27a…` / gen `4da719c7…`） |
| 4 | GREEN | 注册 + cutover **318/345** |
| 5 | GREEN | health +12（baseline 5→17；binding rev6/epoch3） |
| 6 | GREEN | verification/commit → 自动 DM saved-snapshot |
