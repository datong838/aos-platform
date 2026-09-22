# DJ 正式退休与 DK direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `d7927967`：DJ saved-snapshot attempt `8bf657a8…` failed **rev4**；
  definition **250** disabled；Host **94313**；18181=0、worker=0。
- 下一环：DJ 退休 → DK successor → DK saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dk-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dj_terminal_retirement.py` |
| 3–5 | `scripts/a0v_dk_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威

- HEAD `d7927967`；DJ `aca93a08…` / `6ce73106…`；九路 **309/336**；Host 94313。
- 目标 detach legacy **311/338**；DK cutover **312/339**。
- 退休 preflight 前不得 mkdir `replacement-dk`。

## 串行 1–6

1. plan（本文件）
2. SIGTERM Host + released retirement
3. DK create→enable
4. 注册 + cutover
5. health +12
6. verification/commit → 自动 DK saved-snapshot
