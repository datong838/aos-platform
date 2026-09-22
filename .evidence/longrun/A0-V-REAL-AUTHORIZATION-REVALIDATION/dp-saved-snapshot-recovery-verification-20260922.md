# DP saved-snapshot recovery verification（2026-09-22）

## Outcome

`DP_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `cb860ce5` |
| DP | `d2d3c478…` / `b15f1733…`；routes **327/354**；Host **25817**；etag **5** |
| transfer | **266** / `sha256:3a42133f3da86de7bab74fe1ce4c64549ab875b32c0bb2cfa426a56bf7b0937f`；sourceReads=0 |
| recovery | **88** / `sha256:da07e053ba6d658236ce11304b50438898646dbea1878fc14e9a2ca1c86e5f58` |
| enable | **267** / `sha256:878f2ed1519de0f061adddb5f341cb6dd0c0af0a1dd1ebef8a9d570970f471e0` |
| attempt | `dec64efe-54fd-4c69-9bbc-1263311dc48f` failed **rev5** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **268** disabled / `sha256:b097a58e0d517b7f08256ffcb2eefd1080cbbda684899dd3c8f5fc3ab448b81c` |
| 18181 | released；worker stop-only（returnCode=-15）；Host 25817 唯一 |
| previewHash | `sha256:4a791287c941aa8a84e690d70ba9759a071247c91e2aa905574131b8c7133866` |

## Tests

`pytest … -k 'test_dp_saved_snapshot or test_dp_product_api or test_dp_attempt_guard'` → passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- prepare 接受 etag5；transfer/renew/enable 全 `sourceReads=0`。
- 唯一自然 attempt **rev5** fail-closed；guard overlay 仍用 predecessor_view revision=4。
- 无 `run_definition`、无商城源读、无第二 Host/worker。
- leases TASK `A0V-DP-SNAPSHOT-WORKER-20260922` 不进 freeze commit。

## Next wave

DP 正式退休 + DQ direct successor（1/6）。
