# BI-W10-02 Provider Health Maintenance Lease Inbox Acceptance

- Task: `BI-W10-02-PROVIDER-HEALTH-MAINTENANCE-LEASE-INBOX`
- Authority base: `AOS-000397`
- Cutoff: `2026-08-28T21:23:00+08:00`
- Scope: read-only exact active Lease selection and canonical consumer runner
- Excluded: runtime wiring/registration, API restart, real Provider/Secret/Health/business effects, P01-P12, DLQ, migration and release

## Selection result

- Inbox accepts only an executor Principal in `org-org/dev-project` and reads only Leases owned by that exact subject.
- A candidate must be active, unexpired, proposal status `leased`, exact `aip.provider-health-probe` with the current code-backed Action revision hash, proposal/Lease hash equal, and have no initial Receipt.
- Zero candidates yields no execution and runner reports `EXACT_APPROVAL_LEASE_REQUIRED`. Multiple exact candidates yield `MULTIPLE_EXACT_PROVIDER_HEALTH_LEASES_REQUIRE_SELECTION`; no implicit earliest-wins behavior exists.
- Foreign tenant, wrong owner, expired, consumed, Action revision drift and timezone-naive cutoff are excluded or rejected before Adapter dispatch.
- One candidate is converted only to `ProviderHealthLeaseExecution`; the existing canonical consumer owns execution and Receipt checks. After first consumption the Inbox is empty, while an explicit replay of the captured exact execution returns the same Receipt without a second fake refresh.

## Verification

- Inbox + maintenance + Provider Action/authority focused suite: `29/29 passed`.
- AIP-3 Action, Business Investigation, SourceReadiness, Workshop readiness, production contract and OpenAPI cumulative suite: `248/248 passed`.
- `compileall`: GREEN.
- `git diff --check`: GREEN.
- Page change: none; built-in browser acceptance: `N/A`.

## Runtime and external-effect proof

- API remains PID `68386`, sole listener on `127.0.0.1:8080`; no restart occurred.
- `main.py` and the running Adapter registry were not changed. Disposable tests removed their temporary Adapter registration in `finally`.
- No real Proposal/Approval/Lease was created, no Provider endpoint or Secret was accessed, and no real Health/Case/Run/business data was written.

## Result

`BI_W10_PROVIDER_HEALTH_MAINTENANCE_LEASE_INBOX_CODE_CONTROL_GREEN_EXACT_SINGLE_CANDIDATE_NO_LIVE_WIRING_NO_EXTERNAL_EFFECT_NO_RELEASE`
