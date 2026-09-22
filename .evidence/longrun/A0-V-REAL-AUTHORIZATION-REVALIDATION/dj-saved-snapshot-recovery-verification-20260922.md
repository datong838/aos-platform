# DJ saved-snapshot recovery verification（2026-09-22）

## Outcome

`DJ_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `5c762322` |
| DJ | `aca93a08…` / `6ce73106…`；routes **309/336**；Host **94313** |
| transfer | **248**；sourceReads=0 |
| recovery | **82** / `sha256:52d22d57c12bbbfe46328b35dcf130858e9b86548703795b0a7b593a1336e57f` |
| enable | **249** / `sha256:b028488250d3862c57acd53714e51728ba2117fd8b77dc55170f96d06a147fd9` |
| attempt | `8bf657a8-2f62-4057-b2f9-352b64a28a6c` failed **rev4** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **250** disabled / `sha256:0119005898a11f15ffe2746edec43affe696987890b7e5836027d71396f87911` |

## Tests

相关 `test_dj_*` saved-snapshot overlay 通过。

## Browser

N/A。

## Next wave

DJ 正式退休 + DK direct successor（1/6）。
