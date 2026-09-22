# DK 正式退休与 DL direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `71ceaeb2`：DK saved-snapshot attempt `7c7282e0…` failed **rev5**；
  definition **253** disabled；Host **96590**；18181=0、worker=0。
- 下一环：DK 退休 → DL successor → DL saved-snapshot。BG-00。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../dl-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dk_terminal_retirement.py` |
| 3–5 | `scripts/a0v_dl_replacement_recovery.py` / business / cutover / health |
| 6 | verification + tests |

## 当前权威

- HEAD `71ceaeb2`；DK `b651f4d7…` / `fb16d08b…`；九路 **312/339**；Host 96590。
- 目标 detach legacy **314/341**；DL cutover **315/342**。
- 退休 preflight 前不得 mkdir `replacement-dl`。

## 串行 1–6

1. plan（本文件）
2. SIGTERM Host + released retirement
3. DL create→enable
4. 注册 + cutover
5. health +12
6. verification/commit → 自动 DL saved-snapshot

## 波次进度（执行中）

| 步 | 状态 | 证据 |
|---|---|---|
| 1 | GREEN | 本文件 |
| 2 | GREEN | DK disable `796862c4…`；detach `c2cdc20d…`/`sha256:0e686f84…`；legacy **314/341** |
| 3 | GREEN | DL `83453fb3…` / gen `f3a1f381…`；Host **1325**；prepare-after-reset `a0a02705…` |
| 4 | GREEN | 注册 etag**7**；cutover **315/342**；op `6d3f1c8b…` |
| 5 | GREEN | health baseline 8 → 20（+12）；Host 唯一 1325；18181=0 |
| 6 | GREEN | verification + tests + commit → 下一波 DL saved-snapshot |

## 注册硬编码例外（最小）

Host 在首次 verify 中途死亡 → `lifecycle.reset_preparation` → etag **7**、ops **6**
（含 1× `PREPARATION_OWNER_LOST` verify）。`a0v_dl_successor_business.current_request`
改为 DL 本地精确守卫，不再复用 AV etag=5/ops=4。
