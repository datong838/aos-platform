# DQ direct successor verification（2026-09-22）

## Outcome

`DQ_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `b37d6076-1817-4617-9180-469d2e243273` / `sha256:600443ffed027de00432d61c0fbe412613d75d80cd47fa9950eaa3b8d18ac8ee` |
| predecessor disable | `24db7253-e015-4595-817e-491a5989d440` |
| legacy routes | 329 / group 356 |
| DQ installation | `29e553b2-3afc-4b15-b860-f79104f3491a` |
| DQ generation | `b8d6900d-b4a3-43d8-8891-a4b1d02abd3c` |
| lock | `sha256:0adb9ab736b270a430f148b28d1ce57c556375219b34ef733b909d9cfdaa1d63` |
| config | `2653bddb-a5cb-4cea-8b36-2a76920374fd` / `sha256:10843bf51b5eb5a1c9ce39e3ed30881b1c9661d87cddab3f52898f7ec3ae2900` |
| prepare | `2209ba48-7051-4349-bc80-51f2b340c48d` |
| cutover op | `13efdb15-7a6e-4415-92c8-0d5f3852fd6d` |
| registration etag | 5 |
| binding | rev **6** / epoch **3** enabled/ready |
| active routes | 330 / group 357 |
| Host | PID **32752** unique；18181=0 |
| definition | 268 disabled |
| health | baseline 3 → renewals 15（+12）`DQ_HEALTH_OBSERVATION_GREEN`；samples=37 |

## Tests

`pytest … -k 'test_dp_terminal_retirement or test_dq_replacement or test_dq_registration or test_dq_health'` → 4 passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 329/356、cutover 330/357：与 register/cutover/health 常量一致。
- retirement 绑定 failed attempt `dec64efe…` rev5 / IngressJournalConflict、definition 268、active 327/354 → detached 329/356。
- health `OPERATION` 绑定 prepare `2209ba48…`，`BINDING_REVISION=6`（cutover 后）。
- 无 `run_definition`、无 mall 源读。

## Next wave（暂停）

用户额度耗尽：本波封板后 **不** 自动进入 DQ saved-snapshot。下一波待续：DQ saved-snapshot recovery（1/6）。
