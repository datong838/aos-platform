# BI-W10-02 Provider Health ActionType Plugin Package Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-ACTIONTYPE-PLUGIN-PACKAGE`
- Authority base: `AOS-000399`
- Cutoff: `2026-08-28T21:47:00+08:00`
- Scope: available-but-not-installed Action template package and exact snapshot tests
- Excluded: current plugin install/DB/registry/startup, Provider/Secret/data effects, migration and release

## Package result

- Added disk plugin `provider-health-probe` with ActionType id `aip.provider-health-probe`, Chinese business name, `ProviderHealthObservation` object type, four strict parameters, `restricted` marking and four exact equality criteria.
- Existing `_template_from_manifest` maps the package to the full code-backed Action snapshot. The resulting revision hash remains `ace5c268a26715ede142e24594fc2f2bf5dda9dd06b23eb009bb53ad9b40c4da`.
- Plugin is not in `DEFAULTS` or `REQUIRED`; catalog discovery does not install it. Explicit install was verified only under disposable test state and was uninstalled in `finally`.
- Runtime remains `stub`; manifest has an empty closed config schema and contains no endpoint, model, prompt, API key, SecretRef or password fields. Provider execution remains owned by the canonical Adapter authority.

## Verification

- Plugin package + existing action plugins + Provider Health 90-95 focused suite: `40/40 passed`.
- Action plugins, AIP-3, Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative suite: `259/259 passed`.
- JSON parse, `compileall` and `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- The current plugin installed set, current database, `ACTION_ADAPTERS` and `main.py` were not modified by delivery code.
- No Provider endpoint or Secret was accessed and no real Action/Health/Case/Run/business data was written.

## Result

`BI_W10_PROVIDER_HEALTH_ACTIONTYPE_PLUGIN_PACKAGE_CODE_CONTROL_GREEN_AVAILABLE_NOT_INSTALLED_EXACT_SNAPSHOT_NO_EXTERNAL_EFFECT_NO_RELEASE`
