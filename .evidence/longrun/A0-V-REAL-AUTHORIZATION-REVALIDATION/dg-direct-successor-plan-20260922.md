# DF 正式退休与 DG direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `53362fe4`：DF saved-snapshot 唯一 attempt `20318703…` failed **rev4**；
  definition **238** disabled；Host **79478** 仍唯一；18181=0、worker=0。
- 下一环：DF 退休 → DG successor →（封板后）DG saved-snapshot。BG-00。
- 无页面改动 → 浏览器验收 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dg-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_df_terminal_retirement.py` |
| 3 | `scripts/a0v_dg_replacement_recovery.py` |
| 3–4 | `scripts/a0v_dg_successor_business.py` / `scripts/a0v_dg_successor_cutover.py` |
| 5 | `scripts/a0v_dg_health_observation.py` |
| 6 | verification + tests overlay |

## 当前权威

- HEAD `53362fe4`；DF `a0639f78…` / `ec18c8c6…`；九路 **297/324**；Host 79478。
- failed attempt rev4；definition 238。目标 detach legacy **299/326**；DG cutover **300/327**。
- 退休 preflight 前不得 mkdir `replacement-dg`。

## 串行 1–6

1. plan（本文件）
2. SIGTERM Host + released retirement
3. DG create→enable（RuntimePolicy rev11）
4. 注册 + cutover
5. health +12
6. verification/commit → 自动 DG saved-snapshot

## 停止条件

第二 Host/worker、未知重发、商城源读 → fail closed。不 push。
