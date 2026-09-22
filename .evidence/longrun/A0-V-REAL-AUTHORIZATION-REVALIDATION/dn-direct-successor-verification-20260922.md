# DN direct successor verification（2026-09-22）

## Outcome

`DN_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `cf7a8c88-8ce1-41c7-bbc0-3fd0263b53ac` / `sha256:286b64b99a46f7b627370e65ca95f5394477d63d185447192757b2b16f31f6ae` |
| predecessor disable | `3bfab115-bfbc-415f-b65c-7f8f2e25c05f` |
| legacy routes | 320 / group 347 |
| DN installation | `2cb67f0a-0970-4d75-9c4a-a19d68563a3e` |
| DN generation | `e8b25248-98fc-475b-bf9e-1e7e3e803ec7` |
| lock | `sha256:ddc55f6f4f7b5ccb6729b983df4ec98895d99642fbdaf349e61cccf83c26e4a4` |
| config | `b3b76d74-c526-4147-839c-c21902931649` / `sha256:b1c846f6550199aa2d1701098013ee59f42085e5085ce8c9ede6556d2cdbbeff` |
| prepare | `7c3a1ce9-d0c5-453d-ae61-1d862de8a3b0` |
| cutover op | `9510cc3c-a547-4d91-881d-34fc7ca18527` |
| registration etag | 5 |
| binding | rev **6** / epoch **3** enabled/ready |
| active routes | 321 / group 348 |
| Host | PID **16967** unique；18181=0 |
| definition | 259 disabled |
| health | baseline 5 → renewals 17（+12）`DN_HEALTH_OBSERVATION_GREEN`；samples=37 |

## Tests

`pytest … -k 'test_dm_terminal_retirement or test_dn_replacement or test_dn_registration or test_dn_health'` → 4 passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 320/347、cutover 321/348：与 register/cutover/health 常量一致。
- retirement 绑定 failed attempt `3e01547f…` rev4 / IngressJournalConflict、definition 259、active 318/345 → detached 320/347。
- health `OPERATION` 绑定 prepare `7c3a1ce9…`，`BINDING_REVISION=6`（cutover 后）。
- 无 `run_definition`、无 mall 源读。

## Next wave

DN saved-snapshot recovery（1/6）。
