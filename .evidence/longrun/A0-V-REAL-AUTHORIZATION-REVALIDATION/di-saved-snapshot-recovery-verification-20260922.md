# DI saved-snapshot recovery verification（2026-09-22）

## Outcome

`DI_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `522e4831` |
| DI installation | `c8298a5d-9d94-4c37-81c9-508e2f0faf60` |
| DI generation | `56950fc1-4007-497a-8a09-df133a1950c1` |
| routes | 306 / group 333 |
| Host | PID 90347 unique；18181=0；worker=0 after terminal |
| transfer | definition **245**；`sourceReads=0` |
| recovery | **81** / `sha256:3831357759bd96db97ff3e24417a5b1841b9203ae608d8b20a89feccef0b6d0c` |
| enable | definition **246** / `sha256:2c0fb328b7c9e2a8bc5d20ecf4916554a957ef874eb57dc6434f53bf611ea219` |
| attempt | `d394a0fc-c82e-41c1-ba07-e56b480b3866` failed **rev4** |
| reason | `RECOVERABLE_EXECUTION_EXCEPTION` / `IngressJournalConflict` |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | definition **247** disabled / `sha256:287ef86a512bac4a4288ffd41c610174f5b70070ef7c2ae6c9de48724b61d49e` |
| boundary | members=12 runningRuns=12 dataset=12；store=0 link=0 projection=0 canary=0 |

## Tests

`pytest … -k 'test_di_'` → 6 passed。

## Browser

N/A（无页面改动）。

## Next wave

DI 正式退休 + DJ direct successor（1/6）。
