# BI-W10-02 Provider Health Action Contract Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-ACTION-CONTRACT`
- Authority base: `AOS-000394`
- Cutoff: `2026-08-28T20:20:00+08:00`
- Scope: exact Provider Health Action payload, adapter receipt boundary and risk floor
- Excluded: runtime adapter registration, ActionType materialization, live Proposal/Approval/Lease execution, Provider calls, Secret resolution, P01-P12 execution, business mutation, migration apply and release

## Contract result

- Exact Action type: `aip.provider-health-probe`.
- Payload accepts only `agnes-text-qyh-dev@7`, `probeCount=3` and `outputPolicy=metadata-only`; extra fields and all drift fail before the refresh callable.
- The adapter projects only observation identity, expiry, exactly three Provider calls and zero Secret/body reporting. Internal refresh fields, prompts, answers, headers and token totals do not enter the Action outcome.
- Only `PROVIDER_HEALTH_REFRESH_GREEN` with a schema-valid metadata receipt becomes `applied`.
- Reconciliation remains `unknown`, reports `automaticRetry=false`, and does not call the refresh function.
- Server risk classification pins the exact Action to R2, maker-checker and at least one approval. A caller R0 hint cannot lower it.
- The module import has no registration side effect. The current runtime therefore cannot invoke this adapter until a later task bridges it through the canonical Action authority.

## Verification

- New Action + maintenance targeted: `17 passed`.
- Existing Action Proposal/Approval/Lease/Attempt/Receipt adjacency plus new contract: `36 passed`.
- Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative regression: `188 passed`.
- `compileall`: GREEN.
- `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.
- Existing warnings only: Pydantic field shadowing and Starlette TestClient deprecation.

## Runtime and external-effect proof

- API PID `68386` remains `RUNTIME_OWNER_EXACT` and the sole listener on port 8080; no restart occurred.
- The Action adapter was not registered or executed in the live runtime. All positive executions used an in-memory fake refresh callable.
- No Provider request, Secret read, Health write, Proposal/Approval/Lease, Case/Run, Pipeline, DLQ replay, migration or release occurred.
- Parallel natural-slot monitor remains `10 ready / 2 failed`, P07/P08 failed; this task does not rewrite SourceReadiness.

## Result

`BI_W10_PROVIDER_HEALTH_ACTION_CONTRACT_R2_CODE_CONTROL_GREEN_NO_REGISTRATION_NO_PROVIDER_CALL_NO_RELEASE`

