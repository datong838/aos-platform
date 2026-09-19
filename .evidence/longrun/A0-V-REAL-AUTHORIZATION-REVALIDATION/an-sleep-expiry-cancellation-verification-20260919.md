# AN sleep-expiry cancellation verification — 2026-09-19

## Result

`AN_HEARTBEAT_LOSS_CANCELLATION_GREEN`

This closes the runtime code defect exposed by the AN machine-sleep expiry. It does not complete the saved snapshot, authorize a resend, or make the eight ecommerce workbenches available.

## Elapsed-time audit

- Work and commits continued from midnight through commit `59e3a87c` at 04:57:02 +08:00.
- The last AN heartbeat was 04:59:52 +08:00.
- The host then had no useful execution from about 05:00:14 to 09:12:20, a 4h12m06 gap consistent with computer sleep.
- Recovery and diagnosis ran from 09:12 to about 09:21.
- The foreground turn then stopped until 09:27:28, adding about six avoidable minutes. The five-minute heartbeat replies did not replace foreground development and are retained only as a fallback wake-up.
- The surface interval from the last pre-sleep commit at 04:57:02 to the resumed foreground audit at 09:27:28 was 4h30m26; most of it was host sleep, while the final six minutes were an avoidable agent stop.

## Defect and minimal correction

`RecoverableStoreAttempt` already stopped its private heartbeat event when Lease renewal failed, but `PipelineSnapshotGroupCompletion.complete()` passed only the outer worker stop event into downstream business stages. A computer sleep could therefore expire the attempt without making the next existing Store-stage cancellation check fail immediately.

The correction:

1. adds an Event-compatible combined cancellation view in `recoverable_store_attempt.py`;
2. combines heartbeat liveness and caller shutdown immediately after the committed attempt claim enters its context;
3. retains every existing transaction boundary, active check, idempotency key and Receipt authority;
4. grants no retry and never infers the result of an in-flight Store command.

## Red / Green evidence

- Red: the new cancellation contract test initially failed with `AttributeError: 'RecoverableStoreAttempt' object has no attribute 'cancellation'`.
- Focused Green: `12 passed, 7 warnings in 194.86s` for recoverable-attempt and real PostgreSQL snapshot-group completion tests.
- Cumulative Green: Python compilation plus recoverable-attempt, generation-attempt, group-completion, saved-recovery, schedule-worker and lifecycle suites completed with `35 passed, 16 skipped, 7 warnings in 2099.63s`.
- The 16 skips are existing environment-conditioned cases; the PostgreSQL completion and attempt suites used by this change executed.

## Live AN authority readback

- installation/generation: `7eebbd30-88fe-4c3d-a665-f36c5a9d64bb` / `41223cb2-28f6-4109-bdaf-e009ca084367`;
- exact attempt: `1d01cb93-3e8e-4063-b372-bdfb027d2ba3`;
- terminal head: `abandoned`, revision 11, `ATTEMPT_LEASE_EXPIRED`, no raw error type;
- accepted 2026-09-18 20:55:20Z, last heartbeat 20:59:52Z, Lease expired 21:01:52Z, formally abandoned 2026-09-19 01:21:02Z;
- runtime binding: revision 7 / epoch 4, disabled and fenced, desired `enabled`, observed `unknown`;
- schedule definition: revision 56, still enabled;
- 12 frozen Runs and 12 dataset Receipts remain;
- original Store Receipt 0, `ecom_link` 0, projection pending 0;
- all three AN resource leases are formally released;
- `dev-org/dev-project` canary bindings: 0;
- no second AN attempt exists.

## Browser acceptance

The live UI at `http://127.0.0.1:8434/ontology` remains healthy for `org-org/dev-project` and reports AOS v1.6.5. The ecommerce navigation currently shows `暂无可见工作台入口`, which is the correct deny state while AN is fenced. This is evidence of safe denial, not evidence that the eight-workbench business objective is complete.

## Plan/code consistency and remaining boundary

- Both outer shutdown and heartbeat loss are visible through `is_set()` and bounded `wait()`.
- The completion flow changes only its cancellation view after the attempt is claimed; existing Store checks and immutable idempotency remain authoritative.
- AN remains terminal and no-effect. The currently loaded API/worker process predates this code until a controlled reload.
- Next wave: commit this repair, reload under the still-valid `m1` Lease, pause revision-56 scheduling through the formal saved-recovery owner, retire/detach AN through the released-owner lifecycle path, and only then prepare a direct successor using the original Store idempotency key.
