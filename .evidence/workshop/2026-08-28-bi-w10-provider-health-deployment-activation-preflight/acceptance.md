# BI-W10-02 Provider Health Deployment / Activation Preflight Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-DEPLOYMENT-ACTIVATION-PREFLIGHT`
- Authority base: `AOS-000405`
- Cutoff: `2026-08-28T23:31:00+08:00`
- Scope: pure, deterministic loop / Provider-call / real-pilot readiness evaluation
- Excluded: current installation, environment or database mutation, API restart, Secret read, Provider/readiness call, manual pipeline execution, migration and release

## Contract result

- `loop_ready` requires the expected deployed revision, exact canonical environment, installed `provider-health-probe` plugin and exact ActionType.
- `provider_call_ready` additionally requires exact Proposal, Approval, Lease and Receipt authority plus an unexpired Lease.
- `pilot_ready` additionally requires fixed 3/3 fresh Health, fixed 12/12 fresh SourceReadiness, exact operational fresh Binding and one shared exact cutoff.
- The 3 and 12 denominators are canonical invariants; callers cannot lower them to manufacture GREEN.
- Public output contains only stable codes, timestamps, booleans and revision metadata. No secret, credential, token or password value is accepted or returned.

## Current read-only facts and evaluation

- Existing API remains PID `68386`, started `2026-08-28 15:47:35 +08:00`, before the current activation-guard code commit; exact deployed revision is therefore not proven.
- `provider-health-probe` remains discoverable but `installed=false`; canonical ActionType remains absent with `AIP_RESOURCE_NOT_FOUND`.
- Only the legacy maintenance key is present in the inspected process-compatible environment; four canonical authority / subject / tenant keys are absent. No value was printed.
- Latest text Health is `healthy` at `2026-08-28T07:46:04.106548Z` but expired at `2026-08-28T08:01:04.106548Z`. Image and video observations are older and expired; fresh Health is 0/3.
- Independent SourceReadiness at `2026-08-28T23:30:14+08:00` is 10/12; P07 and P08 are `failed`. The long-running read-only monitor independently reports the same 10/12 result through the same time window.
- No exact live Proposal/Approval/Lease/Receipt authority, same-cutoff fresh operational Binding, or deployed revision was asserted without evidence.
- Sanitized evaluator result is `PROVIDER_HEALTH_LOOP_NOT_READY`; all three gates are false with separate stable missing codes. This is a current fact, not a request to stop engineering work.

## Verification

- Focused activation-readiness contract: `8/8 passed`.
- Provider Health, Action plugins/authority, AIP-3, Business Investigation, SourceReadiness, production contract and OpenAPI cumulative: `553/553 passed`.
- `compileall` and `git diff --check`: GREEN.
- Existing warning classes only; no new warning class.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains the sole listener on `127.0.0.1:8080`; no restart occurred.
- No plugin install, ActionType/environment/database write, Secret resolution, Provider/readiness call, real Proposal/Approval/Lease/Case/Run, P07/P08 manual execution, Cron catch-up, DLQ replay, migration or release occurred.

## Result

`BI_W10_PROVIDER_HEALTH_DEPLOYMENT_ACTIVATION_PREFLIGHT_GREEN_CURRENT_LOOP_CALL_PILOT_NOT_READY_SOURCE_READINESS_10_OF_12_NO_EXTERNAL_EFFECT_NO_RELEASE`
