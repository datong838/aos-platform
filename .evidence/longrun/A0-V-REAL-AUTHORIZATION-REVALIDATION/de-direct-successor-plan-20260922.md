# DD 正式退休与 DE direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `29d5964f`：DD saved-snapshot 唯一 attempt `a2396b18…` failed **rev4**；
  definition **232** disabled；Host **70991** 仍唯一。
- 下一环：DD 退休 → DE successor →（封板后）DE saved-snapshot。BG-00。
- 无页面改动 → 浏览器验收 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../de-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dd_terminal_retirement.py` |
| 3 | `scripts/a0v_de_replacement_recovery.py` |
| 3–4 | `scripts/a0v_de_successor_business.py` / `scripts/a0v_de_successor_cutover.py` |
| 5 | `scripts/a0v_de_health_observation.py`（OPERATION=`b7f95379…`） |
| 6 | `.evidence/.../de-direct-successor-verification-20260922.md` |
| 6 | `services/aos-api/tests/.../test_a0v_bn_saved_snapshot_recovery.py` overlay |

## 当前权威

- HEAD `29d5964f`；DD `6e05658b…` / `422d2d5b…`；九路 **291/318**；Host 70991。
- failed attempt rev4；definition 232。目标 detach legacy **293/320**；DE cutover **294/321**。
- 退休 preflight 前不得 mkdir `replacement-de`。

## 串行 1–6

1. plan（本文件）
2. SIGTERM Host + released retirement
3. DE create→enable（RuntimePolicy rev11）
4. 注册 + cutover
5. health +12
6. verification/commit → 自动 DE saved-snapshot

## 停止条件

第二 Host/worker、未知重发、商城源读 → fail closed。不 push。
