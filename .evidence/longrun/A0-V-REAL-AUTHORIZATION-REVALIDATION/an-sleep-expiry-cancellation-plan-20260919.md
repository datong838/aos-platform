# AN sleep-expiry cancellation closure plan — 2026-09-19

## Authority and exact observed boundary

- branch/worktree: `m1` / `/Users/ddt/work/projects/ai_agent/aos-platform`;
- no push; R5-M05 / 230 L0 remains suspended;
- no manual `run_definition`, no source reread and no resend after an unknown outcome;
- AN attempt `1d01cb93-3e8e-4063-b372-bdfb027d2ba3` lost its heartbeat while the computer slept and was formally closed by `ExpiredSignedReadAttemptRecovery` as `abandoned / ATTEMPT_LEASE_EXPIRED`, revision 11;
- AN binding is already fenced at revision 7 / epoch 4 with zero live resources;
- all twelve Runs and twelve dataset receipts remain frozen; the original link Store Receipt, `ecom_link`, projection-pending and `dev-org/dev-project` canary counts are all zero.

The preserved no-effect boundary permits code repair and formal AN retirement. It does not authorize retrying the original Store command.

## Defect

`RecoverableStoreAttempt` stops its heartbeat event when renewal fails, but `PipelineSnapshotGroupCompletion.complete()` continues to pass only the schedule-worker cancellation event into object, link, projection and completion stages. After a machine sleep crosses the attempt Lease, the business executor can therefore continue until a later boundary even though its attempt is no longer renewable.

The Store remains protected by immutable idempotency, but the executor must also fail closed at its next existing `_check_active()` boundary. Attempt-liveness loss and worker shutdown are two independent cancellation sources and must be combined.

## File-level implementation inventory

1. `services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py`
   - add a small combined cancellation view supporting `is_set()` and bounded `wait()`;
   - expose the attempt-owned heartbeat stop together with an optional caller cancellation event;
   - do not change attempt identity, heartbeat cadence, lease rules, Store idempotency or terminal-reason persistence.
2. `services/aos-api/aos_api/pipeline_snapshot_group_completion.py`
   - after the committed attempt claim enters its context, replace the downstream cancellation argument with the combined view;
   - preserve all existing `_check_active()` locations and transaction boundaries.
3. `services/aos-api/tests/extension_runtime/test_recoverable_store_attempt.py`
   - prove either cancellation source becomes visible through both `is_set()` and `wait()`;
   - prove an unset pair remains unset for a bounded wait.
4. `services/aos-api/tests/extension_runtime/test_analysis_snapshot_group_completion_pg.py`
   - prove group execution receives the attempt-owned combined cancellation view and refuses Store execution when heartbeat liveness is lost.
5. `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/an-sleep-expiry-cancellation-verification-20260919.md`
   - record Red/Green, cumulative regression, live AN terminal boundary, browser state, plan/code consistency and residual limits.

## Required behavior

1. An outer worker stop cancels the chain as before.
2. A heartbeat-renewal failure cancels the chain at the next pre-existing active check, before any later Store stage.
3. A currently executing independent Store call is never guessed or repeated; its immutable idempotency Receipt remains the only outcome authority.
4. Normal heartbeats and successful completion remain unchanged.
5. The fix grants no retry and creates no new business authority.

## Verification and exit conditions

- Red test demonstrates the heartbeat-owned stop is not currently wired into group execution.
- Focused cancellation and group-completion tests pass.
- Recoverable-attempt, generation-attempt, group-completion, saved-recovery and schedule-worker cumulative tests pass.
- Current AN remains terminal, fenced and no-effect; no successor attempt appears during verification.
- AN is then disabled/retired through the existing formal lifecycle pattern, with exact Receipt and resource/canary readback.
- Evidence is committed with exact staging. The next wave prepares a direct successor only after AN retirement is proven and reuses the original Store idempotency key without manual execution.
