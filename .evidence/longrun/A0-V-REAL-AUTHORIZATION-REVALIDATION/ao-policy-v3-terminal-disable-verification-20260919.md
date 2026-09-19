# AO Policy v3 terminal disable path verification — 2026-09-19

## Outcome

`AO_POLICY_V3_TERMINAL_DISABLE_PATH_READY_FAIL_CLOSED`

This checkpoint prepares the governed one-shot schedule closure. It does not disable the current Policy, create an approval or write Policy revision 4 while AO recovery and the v3 natural chain are incomplete.

## Contract

The existing v3 executor now exposes three ordered terminal actions:

1. `disable`: run the exact natural-chain observer and freeze readiness only after one succeeded v3 occurrence, one target Receipt, one succeeded Business Run, no active Run, one exact linked draft GrowthPlan and a zero negative-tenant canary;
2. `disable-approval`: create a fresh maker/checker approval for the exact disabled Policy body with expected Policy revision 3 and Case version 4;
3. `disable-put`: dispatch one canonical `ecommerce_growth_schedule_put` command with idempotency key `a0v-ao-advisor-baseline-policy-disable-20260919-v4`.

The resulting authority must be Policy revision 4 with `enabled=false`; the Host disables its schedule binding in the same canonical transaction. The v3 enable approval is never reused.

## Verification

- executor compile passed;
- Policy v3, exact observer, AO guard and SchedulePut Host adapter focused regression: 26 passed, 14 deselected, seven known warnings;
- the real `disable` readiness action rejected the current `awaiting_policy_v3` state with `terminal AO Policy v3 occurrence required before disable`;
- no `disable-result.json` was written, so there is no ambiguous intent or result to replay;
- browser reload settled on `暂无可见工作台入口`, so preparing the future closure path did not expose the incomplete ecommerce workbench;
- no direct SQL mutation, source read or manual `run_definition` was introduced.

## Next boundary

Continue observing AO. Only AO terminal success opens saved-snapshot inspect/disable and Policy v3 creation. Only the later exact `growth_plan_ready` terminal state opens the three closure actions above.
