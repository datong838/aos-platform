# DE 正式退休与 DF direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `dbda4398`：DE saved-snapshot 唯一 attempt `c8ff272f…` failed **rev5**；
  definition **235** disabled；Host **74459** 仍唯一。
- 下一环：DE 退休 → DF successor →（封板后）DF saved-snapshot。BG-00。
- 无页面改动 → 浏览器验收 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../df-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_de_terminal_retirement.py` |
| 3 | `scripts/a0v_df_replacement_recovery.py` |
| 3–4 | `scripts/a0v_df_successor_business.py` / `scripts/a0v_df_successor_cutover.py` |
| 5 | `scripts/a0v_df_health_observation.py` |
| 6 | verification + tests overlay |

## 当前权威

- HEAD `dbda4398`；DE `5d993078…` / `f5181ad4…`；九路 **294/321**；Host 74459。
- failed attempt rev5；definition 235。目标 detach legacy **296/323**；DF cutover **297/324**。
- 退休 preflight 前不得 mkdir `replacement-df`。

## 串行 1–6

1. plan（本文件）
2. SIGTERM Host + released retirement
3. DF create→enable（RuntimePolicy rev11）
4. 注册 + cutover
5. health +12
6. verification/commit → 自动 DF saved-snapshot

## 停止条件

第二 Host/worker、未知重发、商城源读 → fail closed。不 push。
