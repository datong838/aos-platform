# DM saved-snapshot recovery verification（2026-09-22）

## Outcome

`DM_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `6beed523` |
| DM | `5103c27a…` / `4da719c7…`；routes **318/345**；Host **11440**；etag **7**（post-reset） |
| transfer | **257** / `sha256:5c102e25a805d4198796807c8e714a9540d2a6e5cdf32cf701a7cee6adcd6f77`；sourceReads=0 |
| recovery | **85** / `sha256:993275753ba8c461f9bcadbf5ce6f7d846e4aab542d500bb46b1046ed4296705` |
| enable | **258** / `sha256:df768cd2a1a50c924cbc156f0c85ba28676e6a55f32bfc32cea64feaff7e9cf6` |
| attempt | `3e01547f-7d49-48e7-b011-bdf9e3bbfe36` failed **rev4** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **259** disabled / `sha256:2461cd4f608d083d36eca0aa792962ff986dff17d0e5773c11e57c1a29eb02d3` |
| 18181 | released；worker stop-only（returnCode=-15）；Host 11440 唯一 |

## Tests

`pytest … -k 'test_dm_saved_snapshot or test_dm_product_api or test_dm_attempt_guard'` → passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- prepare 接受 etag7（`PREPARATION_OWNER_LOST` 后）；transfer/renew/enable 全 `sourceReads=0`。
- 唯一自然 attempt rev4 fail-closed；无 `run_definition`、无商城源读、无第二 Host/worker。
- leases TASK `A0V-DM-SNAPSHOT-WORKER-20260922` 不进 freeze commit。

## Next wave

DM 正式退休 + DN direct successor（1/6）。
