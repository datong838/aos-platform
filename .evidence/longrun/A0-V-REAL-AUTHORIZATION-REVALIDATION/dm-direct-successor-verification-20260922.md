# DM direct successor verification（2026-09-22）

## Outcome

`DM_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `dac9f81b-dca8-4d1b-b82c-1d561d9dafb8` / `sha256:75fb102aba48b8f999b8b8b241f49dfd6b0b8544f05b1cfeecc0d177e5ba6b19` |
| predecessor disable | `71083a3f-9594-4f6a-9467-8095ac05630e` |
| legacy routes | 317 / group 344 |
| DM installation | `5103c27a-753e-4cad-85cb-9fa35dc0574d` |
| DM generation | `4da719c7-1144-4867-bbdc-8a70362ba5f0` |
| lock | `sha256:169e90f7a54fc17af057799741e199c424e8cdf9d790157cc7645a9c7001c16a` |
| config | `3ca3f8ce-c5a0-4c45-a9fa-0df0fdbc6b38` / `sha256:6668b26d7f9016740b97e5891cb3c97b2bc8a8c0a8edc3bd2201ff7af8e4d4ef` |
| failed prepare (settled) | `ec7a706f-d592-4139-9b54-67073fab064d`（RESOURCE_CLEANUP_UNCERTAIN → name-absent confirm） |
| prepare-after-reset (live) | `8698b16a-b46b-4cca-85ed-1781a7ea46ca` |
| cutover op | `a8f4e2c1-6b09-4d7a-9e15-3c82f1d047b6` |
| registration etag | 7（post `reset_preparation`；含 failed prepare + `PREPARATION_OWNER_LOST` + live） |
| binding | rev **6** / epoch **3** enabled/ready |
| active routes | 318 / group 345 |
| Host | PID **11440** unique；18181=0 |
| definition | 256 disabled |
| health | baseline 5 → renewals 17（+12）`DM_HEALTH_OBSERVATION_GREEN`；samples=36 |

## Tests

`pytest … -k 'test_dm_replacement or test_dm_registration or test_dm_health'` → 3 passed。  
累计：`test_oci_driver` + `test_resource_recovery_pg`（含 claimed-null-container）在本波相关改动上 GREEN。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 317/344、cutover 318/345：与 register/cutover/health 常量一致。
- business 对 post-reset etag7 / ops7 使用 DM 本地 `current_request`；cutover/health 绑定 DL detach `dac9f81b…`。
- health `OPERATION` 绑定 live prepare `8698b16a…`，`BINDING_REVISION=6`（cutover 后）。
- 无 `run_definition`、无 mall 源读。

## Next wave

DM saved-snapshot recovery（1/6）。
