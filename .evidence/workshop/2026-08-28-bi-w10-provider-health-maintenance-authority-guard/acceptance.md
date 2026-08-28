# BI-W10-02 Provider Health Maintenance Authority Guard Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-MAINTENANCE-AUTHORITY-GUARD`
- Authority base: `AOS-000393`
- Cutoff: `2026-08-28T20:07:40+08:00`
- Scope: text Provider health maintenance authorization separation only
- Excluded: Provider calls, Secret resolution, P01-P12 execution, DLQ replay, Case/Run creation, real business mutation, migration apply and release

## Design and code consistency

- `AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED` only controls whether the loop may start; it no longer authorizes a due Provider refresh.
- Every due refresh asks the injected authorization callback before `_refresh_health` can be reached.
- The default callback is deny-all. A denial returns `stage=authorization`, `errorCode=EXACT_APPROVAL_LEASE_REQUIRED`, `providerCalls=0`, `healthObservationWritten=false` and `automaticRetry=false`.
- Authorization-source exceptions are reduced to stable exception type/code and do not expose the source detail.
- Fresh Health remains a read-only no-op. A pending readiness-only completion does not ask for or repeat Provider authorization.
- The production startup path does not inject an authorizer. A future operational enablement must consume the existing `Proposal -> Approval -> ExecutionLease -> Receipt` authority chain; this change creates no second approval system.

## Verification

- Targeted maintenance tests: `7 passed`.
- Provider/R1/R2/CapabilityBinding/SkillBinding/BI composition adjacency: `55 passed`.
- Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative regression: `188 passed`.
- `compileall`: GREEN.
- `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.
- Existing warnings only: Pydantic field shadowing, Starlette TestClient deprecation.

## Runtime and external-effect proof

- Current shell `.env` resolves the legacy maintenance toggle as enabled, which independently proves why the authorization split is required; the new default guard makes that toggle insufficient to invoke a Provider.
- The live API remains PID `68386`, started `2026-08-28 15:47:35 +08:00`; runtime owner readback is `RUNTIME_OWNER_EXACT`, and it remains the sole listener on `127.0.0.1:8080`.
- The live API was not restarted, so this code slice did not disturb the P07/P08 natural-slot observer. The safe startup wrapper had already launched that process with Provider maintenance disabled.
- No Provider request, Secret read, Health observation write, Pipeline run, DLQ replay, Case/Run write, migration or release was performed by this task.
- Parallel read-only SourceReadiness observation remains `10 ready / 2 failed`, with P07/P08 both failed; this task does not rewrite those facts.

## Result

`BI_W10_PROVIDER_HEALTH_MAINTENANCE_AUTHORIZATION_SPLIT_CODE_CONTROL_GREEN_NO_PROVIDER_CALL_NO_RELEASE`

