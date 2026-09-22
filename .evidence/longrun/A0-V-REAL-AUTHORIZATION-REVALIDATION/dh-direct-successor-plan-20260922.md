# DG 正式退休与 DH direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `4af58ebe`：DG saved-snapshot 唯一 attempt `6e9e2fc8…` failed **rev4**；
  definition **241** disabled；Host **82684** 仍唯一；18181=0、worker=0。
- 下一环：DG 退休 → DH successor →（封板后）DH saved-snapshot。BG-00。
- 无页面改动 → 浏览器验收 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dh-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dg_terminal_retirement.py` |
| 3 | `scripts/a0v_dh_replacement_recovery.py` |
| 3–4 | `scripts/a0v_dh_successor_business.py` / `scripts/a0v_dh_successor_cutover.py` |
| 5 | `scripts/a0v_dh_health_observation.py` |
| 6 | verification + tests overlay |

## 当前权威

- HEAD `4af58ebe`；DG `d551d104…` / `6c1780ab…`；九路 **300/327**；Host 82684。
- failed attempt rev4；definition 241。目标 detach legacy **302/329**；DH cutover **303/330**。
- 退休 preflight 前不得 mkdir `replacement-dh`。

## 串行 1–6

1. plan（本文件）
2. SIGTERM Host + released retirement
3. DH create→enable（RuntimePolicy rev11）
4. 注册 + cutover
5. health +12
6. verification/commit → 自动 DH saved-snapshot

## 停止条件

第二 Host/worker、未知重发、商城源读 → fail closed。不 push。
