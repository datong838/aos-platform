# AN expired-attempt pause and retirement verification — 2026-09-19

## Result

`AN_EXPIRED_ATTEMPT_FORMALLY_RETIRED_GREEN`

AN is no longer a runnable or routed ecommerce installation. The saved snapshot remains frozen and no Store result was guessed or resent.

## Safe gate correction

The first two `pause-expired` invocations stopped before mutation because the draft gate expected 12 expired source controls. Read-only inspection proved all 12 AN controls were instead still valid through 2026-09-19 02:54:55Z. The plan and executor were corrected to require 12 current controls: the attempt expired because machine sleep crossed its Lease, independently of source-control validity.

No immutable pause output was created by either rejected invocation and definition revision 56 remained enabled until the corrected gate passed.

## Schedule pause

- exact attempt: `1d01cb93-3e8e-4063-b372-bdfb027d2ba3`;
- terminal state: `abandoned`, revision 11, `ATTEMPT_LEASE_EXPIRED`, raw error type null;
- gate: one exact abandoned attempt, zero unexpected/running attempts, 12 current controls, 12 frozen Runs, 12 dataset Receipts, 18 recovery Receipts, one relationship plan with 1,168 links, zero Store/link/outbox/pending/canary effects;
- immutable pause key: `a0v-an-saved-snapshot-pause-expired-v1`;
- definition transition: revision 56 enabled → revision 57 disabled;
- source reads: 0.

## Formal released-owner retirement

- preflight outcome: `AN_EXPIRED_RETIREMENT_PREFLIGHT_GREEN`;
- disable operation: `7fdd2161-1732-4a14-8aa4-101be445e801`;
- accepted exactly once with `replayed=false`;
- the runtime host completed the accepted operation before the fixed executor needed to claim it;
- process readback records `claimedByHost=true` and `resendDisable=false`;
- lifecycle: exactly one operation and two Receipts, ordered `fence → detach`;
- runtime binding: revision 9 / epoch 5, disabled, fenced, desired `disabled`, observed `unknown`;
- all three resources remain released;
- all nine routes are legacy, detached and fenced at route revision 95 / group revision 122;
- definition remains revision 57 disabled;
- zero running attempts, unresolved delivery attempts, pending runtime operations and `dev-org/dev-project` canary bindings.

## Validation

- compile and focused executor tests: `2 passed, 7 warnings in 4.70s`;
- cumulative AN lifecycle and retirement regression: `8 passed, 10 skipped, 7 warnings in 4.80s`;
- skips are PostgreSQL-fixture cases disabled by the local test profile; live formal preflight, pause, disable and audit ran against `aos_meta_head`;
- API/Worker PID 64439 serves health 200 from `127.0.0.1:18181` after the prior heartbeat-cancellation reload;
- browser reload at `127.0.0.1:8434/ontology` shows AOS v1.6.5 and, after directory resolution, `暂无可见工作台入口` for `org-org/dev-project`.

The browser result is the correct fail-closed state after retirement. It is not eight-workbench completion evidence.

## Plan/code consistency and next boundary

- The pause requires exact terminal identity and current saved-input authority before changing one definition revision.
- Retirement uses `require_released_owner_settlement`, preserves already released resources, and never resends an accepted disable operation.
- Store idempotency, the 12 input Runs and all dataset Receipts remain unchanged.
- Next wave must first design and test a direct AO successor from the AN detach Receipt. It may renew the saved recovery authority and reuse the original Store idempotency key, but it may not call `run_definition`, reread sources, or infer any Store result.
