# BI-W10-02 Provider Health Maintenance Runtime Assembly Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-MAINTENANCE-RUNTIME-ASSEMBLY`
- Authority base: `AOS-000398`
- Cutoff: `2026-08-28T21:37:00+08:00`
- Scope: explicit inactive-by-default assembly of exact Action authority maintenance components
- Excluded: main startup wiring, global registry, API restart, real Provider/Secret/data effects, migration and release

## Assembly result

- Builder validates the real-tenant executor before any database or Adapter work.
- The installed `aip.provider-health-probe` ActionType must equal the full code-backed snapshot and revision hash; missing or drifted installation fails before registration.
- The current process-global `ACTION_ADAPTERS` is explicitly forbidden. Builder creates or consumes only a caller-owned isolated registry, runs deterministic conformance, and verifies the exact Adapter revision.
- Construction and conformance do not call the injected runtime refresh. The maintainer legacy refresh slot is an always-failing sentinel; only Lease Inbox -> canonical runner -> exact consumer can reach the injected Adapter.
- With no approved Lease, a tick returns `EXACT_APPROVAL_LEASE_REQUIRED` and refresh count remains zero. One approved Lease produces one Attempt, one Receipt and one fake refresh; the following tick has no active Lease and does not repeat.

## Verification

- Runtime assembly plus Provider Health maintenance/authority focused suite: `32/32 passed`.
- AIP-3 Action, Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative suite: `251/251 passed`.
- `compileall`: GREEN.
- `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- `main.py` and current `ACTION_ADAPTERS` were not modified; the new builder was not invoked by the running API.
- Tests used disposable DB data and an isolated registry. No Provider endpoint or Secret was accessed and no real Health/Case/Run/business data was written.

## Result

`BI_W10_PROVIDER_HEALTH_MAINTENANCE_RUNTIME_ASSEMBLY_CODE_CONTROL_GREEN_EXPLICIT_ISOLATED_NO_ACTIVATION_NO_EXTERNAL_EFFECT_NO_RELEASE`
