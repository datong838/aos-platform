# DL saved-snapshot recovery verification（2026-09-22）

## Outcome

`DL_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `b4278583` |
| DL | `83453fb3…` / `f3a1f381…`；routes **315/342**；Host **1325**；etag **7**（post-reset） |
| transfer | **254** / `sha256:700e0d123bbb6ae665e465b0c9f9093be8b08d02afb7eab58730c47205c1c166`；sourceReads=0 |
| recovery | **84** / `sha256:efddb5d4dd142266bccbe04b25b79ceba26837e23385fb17c02473c05cb4215a` |
| enable | **255** / `sha256:cfc085b037bc9c75aed11c735f33bdcf4cd7ef9ca3c0543061d6cd7e3ef40d1f` |
| attempt | `9558b0cd-2641-4ad7-bf76-6c152fb674d1` failed **rev4** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **256** disabled / `sha256:2a1ab680d8e7e7f261b0e7dc363781a1889ed1f44a99e4ac843410972ddd1abc` |
| 18181 | released；worker stop-only；Host 1325 唯一 |

## Tests

`pytest … -k 'test_dl_saved_snapshot or test_dl_product_api or test_dl_attempt_guard'` → passed。

## Browser

N/A（letter cycle 无页面 UI）。

## 方案/代码一致性

- prepare 接受 etag7（`PREPARATION_OWNER_LOST` 后）；transfer/renew/enable 全 `sourceReads=0`。
- 唯一自然 attempt rev4 fail-closed；无 `run_definition`、无商城源读、无第二 Host/worker。
- leases TASK `A0V-DL-SNAPSHOT-WORKER-20260922` 不进 freeze commit。

## Next wave

DL 正式退休 + DM direct successor（1/6）。
