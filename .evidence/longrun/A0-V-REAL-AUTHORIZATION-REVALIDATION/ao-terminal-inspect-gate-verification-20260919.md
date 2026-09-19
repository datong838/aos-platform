# AO terminal inspect gate verification — 2026-09-19

## Outcome

`AO_TERMINAL_INSPECT_GATE_READY`

The AO recovery remains naturally running. This checkpoint strengthens the future terminal transition only; it does not inspect through the locking Product path, disable the definition, resend Store, reread sources or create business authority.

## Plan and code alignment

- `ao-direct-successor-plan-20260919.md` now requires one current terminal reconciliation before disable;
- `scripts/a0v_ao_saved_snapshot_recovery.py` exposes one read-only `terminal_facts()` query and one exact `require_terminal_facts()` gate;
- `inspect` returns the runtime status plus terminal facts and `sourceReads=0`;
- `disable` repeats the exact terminal read immediately before the existing controlled definition transition. Any drift aborts before mutation.

## Current pre-terminal observation

- attempt `67c2331d-b73f-4863-b881-0d67e6c55508` remained `running`; heartbeat revision reached 65 and Lease continued advancing;
- one AO attempt, 12 members, 12 dataset Receipts, one relationship and one link command containing 1,168 links were present;
- nine AO routes, three live resources and zero canary binding were present;
- terminal counters remained correctly incomplete: zero succeeded attempt, zero succeeded Runs, zero retirement, zero Store Receipt, zero live links and zero Store outbox event;
- projection pending remained zero.

## Exact success gate

Disable requires all of the following in the same read: one exact succeeded attempt and no sibling attempt; 12 terminal-success Runs; 12 dataset Receipts; one relationship; one exact command hash with 1,168 links; one retirement; one Store Receipt for the original idempotency key; 1,168 live links; 1,168 authoritative Store outbox rows; zero projection pending; nine AO routes; three live resources; zero canary binding.

## Verification

- Python compile passed;
- focused AO recovery plus Policy v3 tests: 3 passed;
- affected cumulative contract regression: 14 passed;
- the read-only terminal query executed successfully against current production-like tenant state and returned the expected incomplete boundary.
- browser reload settled from `正在读取工作台目录` to `暂无可见工作台入口`; the incomplete recovery therefore remained correctly excluded from the tenant workbench surface.

## Next boundary

Continue read-only observation. On terminal success run formal `inspect`; only an exact green fact set permits `disable`. Then perform browser acceptance, evidence and commit before starting Policy v3 `preflight → approval → put`.
