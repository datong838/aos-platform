# BI-W10-02 Provider Health Runtime Wiring Preflight Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-RUNTIME-WIRING-PREFLIGHT`
- Authority base: `AOS-000400`
- Cutoff: `2026-08-28T22:10:00+08:00`
- Scope: canonical startup preflight contract and expiry-sensitive test fixture stability
- Excluded: `main.py`, current plugin installation/database, runtime activation, Provider/Secret/readiness effects, migration and release

## Preflight result

- Legacy maintenance disabled returns `PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE` without reading the Action store.
- Enabled startup requires exact `action-lease-v1` authority mode, subject `service:aip-provider-health-maintenance` and tenant `org-org/dev-project` before any database read.
- The service Principal is constructed in code with only role `aip_executor`, markings `public + restricted` and `token_kind=service`; arbitrary role/marking input is not accepted.
- The installed `aip.provider-health-probe` ActionType must equal the code-backed snapshot in full. Missing and drifted snapshots fail with stable codes.
- Preflight does not build the runtime, register an Adapter, load a Secret, call Provider/readiness, or create Proposal/Approval/Lease.

## Regression repair

- The cumulative suite exposed two test modules whose fixed `2026-08-28` approval cutoff had become historical during the same-day long-running delivery.
- Their shared test instant now uses module-load UTC time. Production expiry logic is unchanged; each test still uses one stable instant and the explicit expired-Lease negative scenario remains covered.

## Verification

- Startup preflight focused: `8/8 passed`.
- Provider Health Action/authority/plugin/inbox/runtime/startup focused: `51/51 passed`.
- Action plugins, AIP-3, Business Investigation, SourceReadiness, production contract and OpenAPI cumulative: `529/529 passed`.
- `compileall` and `git diff --check`: GREEN.
- Existing warnings only; no new warning class.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- `main.py`, current plugin installation, current database and global `ACTION_ADAPTERS` were not modified by delivery code.
- No Provider endpoint or Secret was accessed and no real Health/Action/Case/Run/business data was written.

## Result

`BI_W10_PROVIDER_HEALTH_RUNTIME_WIRING_PREFLIGHT_CODE_CONTROL_GREEN_DEFAULT_INACTIVE_EXACT_AUTHORITY_IDENTITY_SNAPSHOT_NO_ACTIVATION_NO_EXTERNAL_EFFECT_NO_RELEASE`
