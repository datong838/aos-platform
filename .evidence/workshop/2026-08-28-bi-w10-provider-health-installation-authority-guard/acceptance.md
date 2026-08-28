# BI-W10-02 Provider Health Installation Authority Guard Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-INSTALLATION-AUTHORITY-GUARD`
- Authority base: `AOS-000404`
- Cutoff: `2026-08-28T23:08:00+08:00`
- Scope: exact installed-plugin startup prerequisite and Action plugin mutation authorization
- Excluded: current installation/database/runtime change, API restart, Provider/Secret/readiness effect, migration and release

## Current read-only facts

- `provider-health-probe` is discoverable, `required=false`, and currently `installed=false`.
- Canonical ActionType is currently absent (`AIP_RESOURCE_NOT_FOUND`).
- The latest exact `agnes-text-qyh-dev:7` observation reports `healthy` at `2026-08-28T07:46:04.106548Z`, but expired at `2026-08-28T08:01:04.106548Z`; it is not current Health authority.
- Only the legacy maintenance key is present in the inspected shell environment; canonical authority mode, fixed service subject and fixed tenant keys are absent. Values were not printed.
- Independent SourceReadiness remains `10 ready / 2 failed`; P07 latest natural run failed and P08 has no current-day natural run. This task did not replay either pipeline.

## Guard result

- Enabled startup now requires one discoverable `provider-health-probe` manifest with the exact ActionType id and `installed=true` before reading the ActionType snapshot.
- The default startup catalog reads the tenant plugin state without seeding or writing it. Inactive and authority/identity-drift paths perform zero catalog or ActionType read.
- Action plugin install/uninstall endpoints now require `admin` or `owner`. Provider Health plugin mutation additionally requires `org-org/dev-project`; checks occur before registry mutation.
- A residual ActionType can no longer make an uninstalled Provider Health plugin pass startup preflight.

## Verification

- Startup/plugin/API authorization focused: `32/32 passed`.
- Provider Health, Action plugins/authority, AIP-3, Business Investigation, SourceReadiness, production contract and OpenAPI cumulative: `545/545 passed`.
- `compileall` and `git diff --check`: GREEN.
- Existing warnings only; no new warning class.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- Current plugin remains uninstalled and canonical ActionType absent; current database/runtime environment was not changed.
- No Provider/readiness callable ran, no Secret was resolved, and no real Action/Health/Case/Run/business write occurred.
- No manual P07/P08 run, Cron catch-up, DLQ replay, migration or release occurred.

## Result

`BI_W10_PROVIDER_HEALTH_INSTALLATION_AUTHORITY_GUARD_CODE_CONTROL_GREEN_EXACT_INSTALLED_PLUGIN_REQUIRED_ADMIN_CANONICAL_TENANT_MUTATION_GUARD_NO_CURRENT_INSTALL_NO_EXTERNAL_EFFECT_NO_RELEASE`
