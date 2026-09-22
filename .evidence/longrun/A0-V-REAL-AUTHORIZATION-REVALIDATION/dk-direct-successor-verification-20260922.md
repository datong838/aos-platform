# DK direct successor verification（2026-09-22）

## Outcome

`DK_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `5f4ea80e-31f3-4357-b80b-def70eb6cb03` / `sha256:865b94d856a1d753227f88cd90c285cf3a21d63ab07dc4a8707f0fd0bbce08da` |
| predecessor disable | `1e2eafae-df4f-4224-af78-aed094d76b53` |
| legacy routes | 311 / group 338 |
| DK installation | `b651f4d7-b2a3-4032-a0d2-9b43743deb07` |
| DK generation | `fb16d08b-8fcb-4eb0-8c13-7698d16b83b4` |
| lock | `sha256:d696720fe77538523f00f0e3dd8685b38ecbed06f53c4a70e5c7a8c7b2f7eff2` |
| config | `7478e277-6f9d-4ccb-b258-49b33da8f29e` / `sha256:e9da431335ba49fbbf7c93c3010a95381a72cdca297643415bca5585467de02a` |
| prepare op | `25492237-07ae-4288-91ca-a54c1d50651c` |
| cutover op | `aeaabf9f-fb1b-49f3-b012-97fa0762378b` |
| active routes | 312 / group 339 |
| Host | PID 96590 unique；18181=0 |
| definition | 250 disabled |
| health | baseline 3 → renewals 15（+12）`DK_HEALTH_OBSERVATION_GREEN` |

## Tests

`pytest … -k 'test_dk_replacement or test_dk_registration or test_dk_health'` → 3 passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- plan 目标 detach legacy 311/338、cutover 312/339：与 commit/resume dispatchSnapshot 一致。
- business/cutover/health 均绑定 DJ detach `5f4ea80e…` / hash `865b94d8…`。
- 无 `run_definition`、无 mall 源读。

## Next wave

DK saved-snapshot recovery（1/6）。
