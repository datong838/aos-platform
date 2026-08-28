# BI-W10-02 Provider Health Action Authority Bridge Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-ACTION-AUTHORITY-BRIDGE`
- Authority base: `AOS-000395`
- Cutoff: `2026-08-28T20:48:00+08:00`
- Scope: code-backed ActionType/AdapterCapabilityRevision and disposable-database Action authority chain
- Excluded: live Adapter registration, real Provider/Secret calls, API restart, P01-P12 manual execution, DLQ replay, Health/Case/Run/business writes, migration and release

## Exact authority result

- Action Type: `aip.provider-health-probe`, revision hash `ace5c268a26715ede142e24594fc2f2bf5dda9dd06b23eb009bb53ad9b40c4da`.
- Adapter revision: `aip.provider-health-probe.agnes-text@1`, content hash `72248c5d86372885594dcfd0d4390a5216c127d573ed9f71dae0a0759ce6a9e3`.
- Import remains side-effect free. Registration requires an explicit registry and injected runtime refresh callable; deterministic conformance uses a separate fixed fake and does not call the runtime refresh.
- A no-ImpactPreview technical Action may project its Adapter exact ref only when the alias instance reports that ref and the same registry contains the same instance under a GREEN conformant revision. Invalid, missing, drifted, unpublished or wrong-family refs fail closed.
- Existing adapters without `adapter_revision_ref` keep the previous alias behavior. Business Actions with a bound ImpactPreview keep the existing exact binding path.

## Canonical chain proof

- The acceptance test runs only in the disposable `aos_test_*_ti4_test` database.
- Maker `provider-health-maker`, checker `provider-health-checker` and executor `provider-health-executor` are distinct. Same-actor approval is rejected; a wrong Proposal hash cannot acquire a Lease.
- The exact chain creates one Proposal, one approval set, one ExecutionLease, one Attempt and one immutable initial Receipt.
- Attempt and Receipt expose the same exact AdapterCapabilityRevision ref. Receipt contains only observation identity, expiry, `providerCalls=3`, zero Secret payload reads and zero prompt/answer body reporting.
- Runtime fake refresh calls: registration `0`, first execution `1`, replay still `1`. Replay returns the existing single Receipt and does not dispatch again.
- `dev-org/dev-project` cannot read the main-tenant Receipt.

## Verification

- New authority bridge plus Provider Health Action contract: `14/14 passed`.
- Action Adapter/Proposal/Approval/Lease/Attempt/Receipt and maintenance adjacency: `58/58 passed`.
- Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative regression after deterministic export: `458/458 passed`.
- OpenAPI focused and two-process deterministic check: `16/16 passed`, `PASS OpenAPI and inventory are deterministic and current`.
- `compileall`: GREEN.
- `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.
- Existing warnings only: Pydantic field shadowing, Starlette TestClient deprecation and pre-existing duplicate operation IDs.

## Runtime and external-effect proof

- API remains PID `68386`, the sole listener on port `8080`, with `RUNTIME_OWNER_EXACT`; no restart occurred.
- The live `ACTION_ADAPTERS` registry was not modified. Registration/execution occurred only inside the disposable test process and was removed in `finally`.
- No Provider endpoint was contacted, no Secret was resolved, no real Health observation or business row was written, and no Pipeline/Cron/DLQ/migration/release operation ran.
- Independent read-only SourceReadiness monitor at `2026-08-28T20:43:49+08:00` still reports `10 ready / 2 failed`, P07/P08 failed. The code/test result is not treated as natural-slot recovery evidence.

## Result

`BI_W10_PROVIDER_HEALTH_ACTION_AUTHORITY_BRIDGE_CODE_CONTROL_GREEN_NO_LIVE_REGISTRATION_NO_PROVIDER_CALL_NO_RELEASE`
