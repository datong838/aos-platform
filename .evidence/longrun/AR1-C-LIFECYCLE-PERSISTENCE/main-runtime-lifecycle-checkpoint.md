# AR1-C main runtime lifecycle checkpoint

Date: 2026-09-07

## Result

`MAIN_RUNTIME_LIFECYCLE_GREEN`, limited to the explicitly enabled production
runtime host lifecycle and restart recovery. Business scenario count remains
zero in this checkpoint.

## Closed invariants

- `main` selects the production host only after migrations, control-plane
  bootstrap, and compatibility cold starts have completed.
- An ACTIVE selection starts exactly one application-owned
  `extension-runtime-host` task. INACTIVE starts none and preserves the fixed
  selector error code.
- Immediate and delayed host failures are observed and change the runtime
  status to `FAILED_CLOSED` with the fixed `HOST_TASK_FAILED` code.
- Shutdown signals the host, waits up to the fixed application deadline, then
  cancels and still awaits the task. Caller cancellation cannot skip cleanup.
- Every tenant tick runs resource recovery, expired signed-read attempt
  recovery, configuration delivery, and disable delivery in that order.
- Expired signed reads are marked `abandoned` under the exact tenant and runtime
  role. The recovery worker never replays the external read.
- A rebuilt host refuses configuration while the original read lease is live;
  after expiry it recovers the attempt, drains the generation, completes the
  configuration, and acknowledges the original outbox event.
- A real directory database, host-bound directory principal, distinct runtime
  and Web principals, production selector, and materialized host participate in
  the selector-to-host recovery proof.

## Verification

- Focused startup, selector, host, attempt, configuration, AIP startup, and
  route-manifest suite: 96 passed, plus 2 subtests.
- Cumulative asset-registry and extension-runtime suite with isolated
  PostgreSQL enabled: 1639 passed, 28 skipped, plus 2 subtests.
- Python compile and `git diff --check`: passed.
- Independent Prime review: PASS after the restart-attempt recovery and exact
  selector/host evidence gaps were closed.
- Browser acceptance: not applicable because this backend checkpoint changes no
  page.

## Explicit non-claims

No shared migration, real tenant mutation, OCI operation, Provider call,
budget hold, publish action, or business-task dispatch was executed. This
checkpoint does not claim that the Qiyuehui workbench business loop is running.
The next wave owns one bounded real-tenant read-only path from a Chinese
business task through a digital colleague to source-backed output, task
traceability, review feedback, cost evidence, and audit evidence.
