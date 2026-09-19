# AN expired-attempt pause and retirement plan — 2026-09-19

## Authority boundary

- branch/worktree: `m1` / `/Users/ddt/work/projects/ai_agent/aos-platform`;
- no push; 230 L0 remains suspended;
- installation/generation: `7eebbd30-88fe-4c3d-a665-f36c5a9d64bb` / `41223cb2-28f6-4109-bdaf-e009ca084367`;
- the only AN attempt `1d01cb93-3e8e-4063-b372-bdfb027d2ba3` is terminal `abandoned`, revision 11, reason `ATTEMPT_LEASE_EXPIRED`;
- binding revision 7 / epoch 4 is disabled and fenced by the runtime host, and all three resources are released;
- definition revision 56 is still enabled, so the independent worker continues to make safe denied scheduling checks;
- 12 Runs and 12 dataset Receipts remain frozen; Store Receipt, `ecom_link`, pending projection and canary effects are zero.

This boundary authorizes only formal schedule pause and released-owner retirement. It does not authorize manual execution, source reread, Store resend or a successor.

## File-level inventory

1. `scripts/a0v_an_saved_snapshot_recovery.py`
   - add a fixed `pause-expired` action;
   - require the exact abandoned attempt, frozen group, no-effect Store boundary, fenced binding, released resources, twelve still-current source controls and zero canary;
   - transition definition revision 56 from enabled to disabled revision 57 with a new immutable idempotency key.
2. `services/aos-api/tests/extension_runtime/test_a0v_an_saved_snapshot_recovery.py`
   - pin exact identity, terminal reason, revision, no-effect gates and absence of `run_definition`.
3. `scripts/a0v_an_expired_retirement.py`
   - implement fixed `preflight → request-disable → process-disable → audit` actions;
   - use released-owner settlement because runtime binding/resources have already been fenced and released;
   - require exact route group, definition revision 57, attempt identity and zero Store/canary effects;
   - never resend an accepted disable operation with an unknown result.
4. `services/aos-api/tests/extension_runtime/test_a0v_an_expired_retirement.py`
   - pin identities, revisions, receipt phases, released-owner API and no-resend rule.
5. `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/an-expired-retirement-verification-20260919.md`
   - record previews, mutations, Receipts, tests, live readback and next-wave boundary.

## Execution order and stop rules

1. Run read-only gates and tests before any mutation. Attempt expiry and source-control expiry are independent; the current AN controls must still be valid.
2. Execute `pause-expired` once; if the immutable result already exists, inspect it rather than repeating it.
3. Require definition revision 57 disabled and zero new attempt before retirement.
4. Run retirement `preflight` and `request-disable` once.
5. If the host has already completed the accepted operation, audit it. Otherwise claim only that exact outbox delivery and finish it once.
6. Stop on any identity, revision, Receipt, route, resource, Store or canary mismatch. Never infer success and never issue a replacement request.

## Exit conditions

- definition revision 57 is disabled;
- AN binding is revision 9 / epoch 5, disabled and fenced with desired state disabled;
- nine routes are legacy, fenced and detached at their next exact revisions;
- lifecycle has exactly fence and detach Receipts for the one disable operation;
- three resources remain released;
- one abandoned AN attempt remains the only AN attempt;
- 12 frozen Runs and 12 dataset Receipts remain, with zero Store Receipt, links, pending projection and canary effects;
- evidence and exact files are committed, then the next wave may design a direct successor using the original immutable Store idempotency key.
