# DP direct successor verification（2026-09-22）

## Outcome

`DP_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `ad02a6ad-7fa6-45fc-a200-ad63629fd7bf` / `sha256:7deae31d1e7793e17d8fd18673ad02f2e0c08a6b9514604636779ee7f3c20c1c` |
| predecessor disable | `1def9b65-a469-4bec-8a1f-2dfc5f0d0e45` |
| legacy routes | 326 / group 353 |
| DP installation | `d2d3c478-f9d9-4489-92b7-1de57f546452` |
| DP generation | `b15f1733-89dd-4684-9475-9fba095a1d74` |
| lock | `sha256:06c2ac6eded4cadd0ffa0edb9bbbad3bac59d36e9f42993f6e6ecb5a7c44adba` |
| config | `5f9ceec4-8532-44be-bb07-13617e195f70` / `sha256:ffef5daa927083eddc12d3f5848efb7c2a818bb1b631905a61e0ef913b18ceab` |
| prepare | `9893b31e-aacb-4d6b-8553-e62d3db659d6` |
| cutover op | `29f2f093-aa25-435d-bc93-1e81ea959059` |
| registration etag | 5 |
| binding | rev **6** / epoch **3** enabled/ready |
| active routes | 327 / group 354 |
| Host | PID **25817** unique；18181=0 |
| definition | 265 disabled |
| health | baseline 3 → renewals 15（+12）`DP_HEALTH_OBSERVATION_GREEN`；samples=37 |

## Tests

`pytest … -k 'test_do_terminal_retirement or test_dp_replacement or test_dp_registration or test_dp_health'` → 4 passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 326/353、cutover 327/354：与 register/cutover/health 常量一致。
- retirement 绑定 failed attempt `43556e02…` rev5 / IngressJournalConflict、definition 265、active 324/351 → detached 326/353。
- health `OPERATION` 绑定 prepare `9893b31e…`，`BINDING_REVISION=6`（cutover 后）。
- 无 `run_definition`、无 mall 源读。

## Next wave

DP saved-snapshot recovery（1/6）。
