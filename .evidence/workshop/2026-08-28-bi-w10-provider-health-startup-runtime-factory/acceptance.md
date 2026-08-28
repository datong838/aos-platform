# BI-W10-02 Provider Health Startup Runtime Factory Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-STARTUP-RUNTIME-FACTORY`
- Authority base: `AOS-000401`
- Cutoff: `2026-08-28T22:22:00+08:00`
- Scope: inactive-by-default startup result and explicit canonical runtime factory
- Excluded: `main.py`, current plugin installation/database, loop activation, Provider/Secret/readiness effects, migration and release

## Factory result

- Default/inactive configuration returns a startup result with `runtime=None`; it requires no callable and performs no Action-store read.
- Enabled configuration first consumes the exact GREEN preflight, then requires both refresh and readiness callables explicitly. There is no implicit Provider-script fallback in the factory.
- The factory passes the fixed service Principal, the same Action store and an isolated registry into the sealed runtime builder. The builder performs the second exact ActionType snapshot check and deterministic conformance.
- Construction invokes neither refresh nor readiness and leaves the process-global `ACTION_ADAPTERS` entry unchanged.
- The factory only returns an object; it does not create an asyncio task or execute a maintenance tick.

## Verification

- Startup + runtime focused: `16/16 passed`.
- Provider Health Action/authority/plugin/inbox/runtime/startup focused: `56/56 passed`.
- Action plugins, AIP-3, Business Investigation, SourceReadiness, production contract and OpenAPI cumulative: `534/534 passed`.
- `compileall` and `git diff --check`: GREEN.
- Existing warnings only; no new warning class.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- `main.py`, current plugin installation, current database and current runtime environment were not changed.
- Tests use pure counting/raising callables; construction records zero Provider and zero readiness calls.
- No Secret, real Health/Action/Case/Run/business write, migration or release occurred.

## Result

`BI_W10_PROVIDER_HEALTH_STARTUP_RUNTIME_FACTORY_CODE_CONTROL_GREEN_INACTIVE_BY_DEFAULT_EXPLICIT_CALLABLES_ISOLATED_RUNTIME_ZERO_CONSTRUCTION_EFFECT_NO_RELEASE`
