# DO saved-snapshot recovery verification（2026-09-22）

## Outcome

`DO_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `7041608f` |
| DO | `e748c240…` / `93b514ad…`；routes **324/351**；Host **22443**；etag **5** |
| transfer | **263** / `sha256:d74fcffa1057d1d98213ee1de047268e395ff88447ccae35e4cd77886b41b4e9`；sourceReads=0 |
| recovery | **87** / `sha256:6c3a170bb709282587f41dce243c66575a6e182d3e04d3819102aec1a57be16e` |
| enable | **264** / `sha256:21fcd60168f47327992c9c111a3e7034f4179e4a78519d4170b0cb324418cf0b` |
| attempt | `43556e02-29d2-41df-b8b1-3482d57c1e26` failed **rev5** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **265** disabled / `sha256:d57cc4dfd128fadf9c83f970ef075c35ef8e5a17b21af3378dceeea53fc4d19c` |
| 18181 | released；worker stop-only（returnCode=-15）；Host 22443 唯一 |
| previewHash | `sha256:bc17436032c702221d507ca9bc7d110a61cfa505023bc193f660c6480dc4ed9b` |

## Tests

`pytest … -k 'test_do_saved_snapshot or test_do_product_api or test_do_attempt_guard'` → passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- prepare 接受 etag5；transfer/renew/enable 全 `sourceReads=0`。
- 唯一自然 attempt **rev5** fail-closed；guard overlay 仍用 predecessor_view revision=4。
- 无 `run_definition`、无商城源读、无第二 Host/worker。
- leases TASK `A0V-DO-SNAPSHOT-WORKER-20260922` 不进 freeze commit。

## Next wave

DO 正式退休 + DP direct successor（1/6）。
