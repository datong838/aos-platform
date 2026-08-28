# BI-W10-02 Provider Health Maintenance Lease Bridge Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-MAINTENANCE-LEASE-BRIDGE`
- Authority base: `AOS-000396`
- Cutoff: `2026-08-28T21:09:00+08:00`
- Scope: exact canonical Action Lease consumer and maintainer Receipt handoff
- Excluded: runtime registration, API restart, real Provider/Secret, real Health/Case/Run/business writes, P01-P12 manual execution, DLQ replay, migration and release

## Authority and single-effect result

- The new `ProviderHealthActionLeaseConsumer` accepts only an explicitly supplied executor Principal, Lease id and expected Proposal hash. It creates no Proposal, Approval or Lease.
- Before returning a maintenance result it verifies the exact Provider Health Action type and code-backed revision hash, strict payload, matching Lease and Proposal hash, applied Attempt, exact conformant Adapter revision, and exactly one matching initial applied Receipt.
- The maintainer canonical path consumes the Receipt summary directly. It does not invoke the legacy `_refresh_health` callback after Action execution.
- Canonical consumer and legacy boolean authorizer cannot be configured together. The default startup constructor still has neither a Lease source nor a canonical consumer and therefore remains deny-all.
- Replay of the same consumed Lease returns the existing immutable Receipt. Acceptance produced one Attempt, one Receipt and one fake refresh call across two maintainer ticks; the legacy refresh call count stayed zero.
- `dev-org/dev-project` cannot consume the `org-org/dev-project` Lease and fails before Adapter dispatch.

## Verification

- Provider Health maintenance, contract and full Action authority focused suite: `26/26 passed`.
- Action AIP-3, Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative suite: `245/245 passed`.
- `compileall`: GREEN.
- `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.
- Existing warnings only: Pydantic field shadowing, Starlette TestClient deprecation and pre-existing duplicate OpenAPI operation IDs.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- No Adapter was registered into the running API. Registration existed only in the disposable test process and was removed in `finally`.
- All Provider behavior was a counting in-memory fake. No endpoint was contacted, no Secret was resolved, and no real Health or business row was written.
- Independent read-only SourceReadiness monitor at `2026-08-28T21:08:53+08:00` remains `10 ready / 2 failed`, P07/P08 failed. This code-control result is not natural-slot recovery evidence.

## Result

`BI_W10_PROVIDER_HEALTH_MAINTENANCE_LEASE_BRIDGE_CODE_CONTROL_GREEN_SINGLE_RECEIPT_NO_DUPLICATE_PROVIDER_REFRESH_NO_LIVE_REGISTRATION_NO_RELEASE`
