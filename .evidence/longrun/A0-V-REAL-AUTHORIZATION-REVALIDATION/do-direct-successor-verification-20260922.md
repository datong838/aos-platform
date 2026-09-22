# DO direct successor verification（2026-09-22）

## Outcome

`DO_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `35a465a7-ef65-479d-9534-9850a82044b6` / `sha256:8adfdd0dbe1bdb14c09649f1255f532fc7628bc6414c98ede5e5f2022f2e34a8` |
| predecessor disable | `0c5e0d6d-f22f-4490-9f57-45c7cb16922d` |
| legacy routes | 323 / group 350 |
| DO installation | `e748c240-f9d4-47c0-a9dc-3c473b311cae` |
| DO generation | `93b514ad-3920-4eb4-8fc7-7cb1106254ff` |
| lock | `sha256:7a5f02619ee98dec6aa96784e64b2024b7d988ded5e0d76b4fefe9b35894a3e6` |
| config | `0a1ef242-3dae-456d-bc8a-3975e771bae4` / `sha256:d445eec67e68cb4c0d0130f5d1984106d5d0fc0b0a82c7868263471f13b79bd1` |
| prepare | `9e0c395e-f2a6-4d64-bb3a-19b7765b118e` |
| cutover op | `9269e6d0-0052-45f7-9f5f-24cb5f62e2b4` |
| registration etag | 5 |
| binding | rev **6** / epoch **3** enabled/ready |
| active routes | 324 / group 351 |
| Host | PID **22443** unique；18181=0 |
| definition | 262 disabled |
| health | baseline 2 → renewals TBD（+12）`DO_HEALTH_OBSERVATION_GREEN` |

## Tests

`pytest … -k 'test_dn_terminal_retirement or test_do_replacement or test_do_registration or test_do_health'` → 4 passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 323/350、cutover 324/351：与 register/cutover/health 常量一致。
- retirement 绑定 failed attempt `a2107628…` rev4 / IngressJournalConflict、definition 262、active 321/348 → detached 323/350。
- health `OPERATION` 绑定 prepare `9e0c395e…`，`BINDING_REVISION=6`（cutover 后）。
- 无 `run_definition`、无 mall 源读。

## Next wave

DO saved-snapshot recovery（1/6）。
