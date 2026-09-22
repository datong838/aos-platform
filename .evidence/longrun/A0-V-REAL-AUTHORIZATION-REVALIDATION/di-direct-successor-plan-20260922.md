# DH 正式退休与 DI direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `aca2cca4`：DH saved-snapshot 唯一 attempt `40429d74…` failed **rev4**；
  definition **244** disabled；Host **86843** 仍唯一；18181=0、worker=0。
- 下一环：DH 退休 → DI successor →（封板后）DI saved-snapshot。BG-00。
- 无页面改动 → 浏览器验收 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | `.evidence/.../di-direct-successor-plan-20260922.md` |
| 2 | `scripts/a0v_dh_terminal_retirement.py` |
| 3 | `scripts/a0v_di_replacement_recovery.py` |
| 3–4 | `scripts/a0v_di_successor_business.py` / `scripts/a0v_di_successor_cutover.py` |
| 5 | `scripts/a0v_di_health_observation.py` |
| 6 | verification + tests overlay |

## 封板权威

- DH 退休 GREEN：disable `c1750709…`；detach `6a8a6daa…` /
  `sha256:505640a22de3ee4b9cec5c9de036c7d3ff05e55bb2472f9d1bdadc5150220ea3`；legacy **305/332**。
- DI `c8298a5d-9d94-4c37-81c9-508e2f0faf60` / `56950fc1-4007-497a-8a09-df133a1950c1`；
  lock `sha256:306ffd56004521bf793df38eb4887287afbec98279c169e64aaae469a5dbfffc`。
- config `6d8cc828…` / `sha256:0b6534e9fd9f8e4f900cd3208d446340735a95dbaafc21d5285498bea47a2861`。
- prepare `d366b2d3…`；cutover `818723c0…`；九路 **306/333**；binding rev6/epoch3
  enabled/ready；唯一 Host **90347**；definition 244 disabled。
- health baseline 3 → renewals 15（+12）GREEN；samples=35。
- 边界：12/12/12；store=0、link=0、projection=0、canary=0、attempt=0；18181=0。

## 串行 1–6 结果

1. plan — GREEN
2. SIGTERM Host + released retirement — GREEN
3. DI create→enable — GREEN
4. 注册 + cutover 306/333 — GREEN
5. health +12 — GREEN
6. verification/tests/commit — IN PROGRESS → 下一波 DI saved-snapshot

## 停止条件

第二 Host/worker、未知重发、商城源读 → fail closed。不 push。
