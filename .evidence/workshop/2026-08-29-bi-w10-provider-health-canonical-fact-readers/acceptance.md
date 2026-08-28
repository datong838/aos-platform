# BI-W10-02 Provider Health Canonical Fact Readers Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-CANONICAL-FACT-READERS`
- Authority base: `AOS-000408`
- Cutoff: `2026-08-29T00:30:00+08:00`
- Scope: sanitized seven-source owner snapshot adapters for the activation audit
- Excluded: main startup wiring, current installation or database/environment mutation, Secret/Provider/readiness calls, Action authority creation, manual pipelines, migration and release

## Contract result

- One factory maps exactly seven authority-owner readers into the activation audit contract: deployment, canonical environment, plugin/ActionType, Action authority, Health, SourceReadiness and Binding.
- Every owner snapshot must be canonical-tenant and timezone-aware. Future cutoffs, wrong snapshot types, wrong provider sets, duplicate Health refs and non-12 SourceReadiness denominators fail at the reader boundary.
- Canonical environment is an exact five-key comparison; extra or drifted values do not pass. The values are reduced to one boolean and are not exposed by the audit.
- Health requires the exact three provider revisions (`text@7`, `image@2`, `video@1`) and counts only healthy observations unexpired at evaluation time.
- The returned mapping contains reader functions only. It has no writer, refresh, execute, Provider or Secret surface; the downstream packet remains `executionAuthorized=false` even when all facts are GREEN.

## Verification

- Canonical readers + audit/readiness/change-packet focused: `30/30 passed`.
- Provider Health, Action plugins/authority, Business Investigation, SourceReadiness, production contract and OpenAPI cumulative: `555/555 passed`.
- `compileall` and `git diff --check`: GREEN.
- Existing warning classes only; no new warning class.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- Existing API PID `68386` was not restarted or rewired.
- No current environment value was printed or changed. No plugin install, ActionType/database write, Secret resolution, Provider/readiness call, Proposal/Approval/Lease/Case/Run creation, P07/P08 manual execution, Cron catch-up, DLQ replay, migration or release occurred.

## Result

`BI_W10_PROVIDER_HEALTH_CANONICAL_FACT_READERS_GREEN_STRICT_SANITIZED_READ_ONLY_NO_EXTERNAL_EFFECT_NO_RELEASE`
