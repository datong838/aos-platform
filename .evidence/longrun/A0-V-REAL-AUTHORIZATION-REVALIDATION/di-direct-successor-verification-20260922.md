# DI direct successor verification（2026-09-22）

## Outcome

`DI_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `6a8a6daa-1c32-45af-89f4-3bb2cf7ac80c` / `sha256:505640a22de3ee4b9cec5c9de036c7d3ff05e55bb2472f9d1bdadc5150220ea3` |
| predecessor disable | `c1750709-45a0-4c1a-ad89-63de6f2ca3e4` |
| legacy routes | 305 / group 332 |
| DI installation | `c8298a5d-9d94-4c37-81c9-508e2f0faf60` |
| DI generation | `56950fc1-4007-497a-8a09-df133a1950c1` |
| lock | `sha256:306ffd56004521bf793df38eb4887287afbec98279c169e64aaae469a5dbfffc` |
| config | `6d8cc828-307e-407d-b3ed-37a3ed524114` / `sha256:0b6534e9fd9f8e4f900cd3208d446340735a95dbaafc21d5285498bea47a2861` |
| prepare op | `d366b2d3-9456-4178-9a21-cc516cca507d` |
| cutover op | `818723c0-2995-441d-9409-dc1530f093e7` |
| active routes | 306 / group 333 |
| binding | rev6 / epoch3 / enabled / ready |
| Host | PID 90347 unique；18181=0；worker=0 |
| definition | 244 disabled |
| health | baseline 3 → renewals 15（+12）`DI_HEALTH_OBSERVATION_GREEN` |
| boundary | members=12 saved_runs=12 dataset=12 store=0 link=0 projection=0 canary=0 attempt=0 |

## Tests

`pytest … -k 'test_di_replacement or test_di_registration or test_di_health'` → 3 passed.

## Browser

N/A（无页面改动）。

## Next wave

DI saved-snapshot recovery（1/6）。
