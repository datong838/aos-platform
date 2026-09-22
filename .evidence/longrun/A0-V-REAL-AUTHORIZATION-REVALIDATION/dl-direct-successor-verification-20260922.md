# DL direct successor verification（2026-09-22）

## Outcome

`DL_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `c2cdc20d-7efd-4896-87f6-8afe7c7878ca` / `sha256:0e686f8422c64c3ea7bb19813854a9f653dc6e601bbd363afd468257e5e1045e` |
| predecessor disable | `796862c4-452d-4e2e-bab2-6300a139be33` |
| legacy routes | 314 / group 341 |
| DL installation | `83453fb3-8c39-422c-845b-e152551e0a30` |
| DL generation | `f3a1f381-5aeb-4494-a155-164e0ef9e0f5` |
| lock | `sha256:b2985931a11c73d1b6dd1a0b0befd93f8b9f18f5ec2017c486ffc0db63e080dc` |
| config | `3b84ed40-5bcd-4106-a4b2-c1e2359ea5f2` / `sha256:e96070b75b737b9dbbb301347a7fc70441e2b6a53c9d9d98f35c739e35f21952` |
| prepare-after-reset | `a0a02705-3d34-4520-b5b8-cf0ef8777fc6` |
| cutover op | `6d3f1c8b-7092-4d5e-9ac0-23865f729064` |
| registration etag | 7（post `reset_preparation`；ops=6 含 1×`PREPARATION_OWNER_LOST`） |
| active routes | 315 / group 342 |
| Host | PID 1325 unique；18181=0 |
| definition | 253 disabled |
| health | baseline 8 → renewals 20（+12）`DL_HEALTH_OBSERVATION_GREEN`；samples=37 |

## Tests

`pytest … -k 'test_dl_replacement or test_dl_registration or test_dl_health'` → 3 passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 314/341、cutover 315/342：与 commit/resume dispatchSnapshot 一致。
- business 对 post-reset etag7/ops6 使用 DL 本地 `current_request`；cutover/health 绑定 DK detach `c2cdc20d…`。
- 无 `run_definition`、无 mall 源读。

## Next wave

DL saved-snapshot recovery（1/6）。
