# DK saved-snapshot recovery verification（2026-09-22）

## Outcome

`DK_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`

## Exact authority

| Field | Value |
|---|---|
| HEAD before | `c8eb65f3` |
| DK | `b651f4d7…` / `fb16d08b…`；routes **312/339**；Host **96590** |
| transfer | **251** / `sha256:2abcceb2c7a5472ebdfc53edcdfb82051b5b94640f376613b3dd53e48e0e4cb3`；sourceReads=0 |
| recovery | **83** / `sha256:e025a04befb60cbe64ce7861aeacd43e8c024c34f9ddf2624c6210f525923065` |
| enable | **252** / `sha256:81327e92d425463f858a5d6ae8bd052417a1497754b1add0bbe761fa3f268770` |
| attempt | `7c7282e0-aa83-45e6-99ac-ae996f86b1b7` failed **rev5** / IngressJournalConflict |
| requestHash | `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7` |
| pause | **253** disabled / `sha256:1b1b0851bea6b1d6ff3c420aba51946ad6163cdb27d3093b0574bf72930f1ff1` |

## Tests

相关 `test_dk_*` saved-snapshot overlay 通过。

## Browser

N/A。

## Next wave

DK 正式退休 + DL direct successor（1/6）。
