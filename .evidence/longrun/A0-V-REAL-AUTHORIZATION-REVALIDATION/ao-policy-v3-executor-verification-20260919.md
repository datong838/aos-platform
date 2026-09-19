# AO Policy v3 executor verification — 2026-09-19

## Outcome

`AO_POLICY_V3_EXECUTOR_PREPARED_FAIL_CLOSED`

This checkpoint prepares the next natural-chain command path while the AO saved-snapshot attempt remains healthy and running. It does not create an approval, Policy revision, occurrence, Case or Run.

## Runtime boundary observed

- AO attempt: `67c2331d-b73f-4863-b881-0d67e6c55508`;
- state remained `running`; revision advanced from 25 through 54 while this checkpoint was implemented;
- heartbeat and Lease advanced continuously; no terminal reason or error was present;
- the browser continued to show `暂无可见工作台入口`, so the incomplete Store recovery did not expose a premature workbench.

## Implemented files

- `scripts/a0v_ao_advisor_baseline_v3.py`;
- `services/aos-api/tests/extension_runtime/test_a0v_ao_advisor_baseline_v3.py`.

The executor pins AO installation `d4186607-c93f-4fd0-8daa-46e349184ab9`, generation `00bb99df-d436-483d-86df-496718c6f129`, binding revision 6 / epoch 3, saved definition revision 59, recovery revision 19, Case revision/version 4 and Policy revision/version 2. It also requires the exact two historical cancelled occurrences, the one Store Receipt for the original key, 12 terminal Runs, 12 dataset Receipts, one relationship/link command/retirement, 1,168 live links, no active baseline Run, no GrowthPlan head and zero canary occurrence.

## Fail-closed proof

- `preflight` reads the attempt before opening the Product preflight. Because the attempt is not terminal-success, it returned `AO recovery is not terminal-success; Product preflight was not opened`;
- no v3 state directory or result file was created;
- `approval` requires the immutable successful preflight result;
- `put` requires the immutable approval result and uses the canonical ecommerce router;
- `disable` is readiness-only and performs no mutation. It requires one terminal Policy v3 occurrence and zero active Runs; a fresh approval and canonical write remain mandatory afterward;
- the executor contains no `run_definition`, direct SQL write or source-read path.

## Verification

- Python compile: passed;
- focused tests: `test_a0v_ao_advisor_baseline_v3.py` plus `test_a0v_ao_saved_snapshot_recovery.py` → 3 passed;
- affected cumulative contract regression across heartbeat cancellation, AN retirement, AO lifecycle/cutover/recovery and Policy v3 → 14 passed;
- browser acceptance: current tenant page reachable; ecommerce navigation remained hidden as required during incomplete recovery.

## Next boundary

Continue observing AO without changing it. On `succeeded`, run the existing AO saved-snapshot `inspect`, reconcile Store/link/retirement/projection/resources/canary facts, disable the completed definition, and then execute v3 `preflight → approval → put`. On `failed` or `abandoned`, do not use this executor; freeze the failure boundary and enter formal retirement/direct-successor handling.
