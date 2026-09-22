# DN saved-snapshot recovery verification（2026-09-22）

## Outcome

`DN_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `0435a8e1` |
| DN | `2cb67f0a…` / `e8b25248…`；routes **321/348**；Host **16967**；etag **5** |
| transfer | **260** / `sha256:2cc1c853e8ad02edc4c78c95c013a910214b76b81e6513841259601c18c67e50`；sourceReads=0 |
| recovery | **86** / `sha256:59ddef1063f2e2ed0fbf4df77fd74a91399a554e56395f72bb3ec92f41854cb5` |
| enable | **261** / `sha256:84c6607039ef49a9216034f65d5b388786425a01c1d7d9f1907b3b7bb854efb2` |
| attempt | `a2107628-439a-4aff-861a-cf80abd1df09` failed **rev4** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **262** disabled / `sha256:b3e81d6dba304740176bbf20202321b061933d890fb570d986bda54833754e1b` |
| 18181 | released；worker stop-only（returnCode=-15）；Host 16967 唯一 |
| previewHash | `sha256:b64a0b6798b1697d96d59144efea25b754bf6455f5b0b1211e6fec85b486b131` |

## Tests

`pytest … -k 'test_dn_saved_snapshot or test_dn_product_api or test_dn_attempt_guard'` → passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- prepare 接受 etag5（stock lifecycle）；transfer/renew/enable 全 `sourceReads=0`。
- 唯一自然 attempt rev4 fail-closed；无 `run_definition`、无商城源读、无第二 Host/worker。
- leases TASK `A0V-DN-SNAPSHOT-WORKER-20260922` 不进 freeze commit。

## Next wave

DN 正式退休 + DO direct successor（1/6）。
