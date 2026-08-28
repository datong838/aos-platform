# BI-W10-02 Provider Health Main Startup Wiring Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-MAIN-STARTUP-WIRING`
- Authority base: `AOS-000402`
- Cutoff: `2026-08-28T22:43:00+08:00`
- Scope: main lifespan consumes the canonical Provider Health startup factory
- Excluded: current plugin/database/runtime configuration, API restart, Provider/Secret/readiness effect, migration and release

## Wiring result

- `main.py` no longer checks only the legacy enabled flag and no longer directly constructs `AipTextProviderHealthMaintainer()`.
- The startup factory receives the reviewed health/readiness callables explicitly. Default inactive returns no maintainer and creates no Provider Health task.
- Missing or drifted canonical authority returns only a stable failure code and creates no Provider Health task. Environment values, Provider details and Secret material are not logged.
- Only a non-null runtime from the canonical factory contributes its already assembled maintainer to the loop. There is no legacy fallback construction path.
- Runtime construction still invokes neither health nor readiness; each tick remains gated by the canonical Action Proposal/Approval/Lease/Receipt consumer.

## Verification

- Main startup + factory/runtime focused: `33/33 passed`.
- Provider Health, Action plugins/authority, AIP-3, Business Investigation, SourceReadiness, production contract and OpenAPI cumulative: `539/539 passed`.
- `compileall` and `git diff --check`: GREEN.
- Existing warnings only; no new warning class.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- Current process environment, plugin installation and current database were not changed.
- No Provider or readiness callable ran; no Secret was resolved and no real Action/Health/Case/Run/business write occurred.
- No migration, Cron replay, DLQ replay or release occurred.

## Result

`BI_W10_PROVIDER_HEALTH_MAIN_STARTUP_WIRING_CODE_CONTROL_GREEN_CANONICAL_FACTORY_ONLY_INACTIVE_OR_PREFLIGHT_FAILURE_ZERO_TASK_NO_CURRENT_ACTIVATION_NO_RELEASE`
