# AR2-7D Offline Registry Credential Isolation Verification

- Date: 2026-09-10
- Branch: `m1`
- Scope: D6D2 prerequisite only
- Result: `AR2_7D_OFFLINE_REGISTRY_CREDENTIAL_ISOLATION_GREEN`

## Authority and boundary

This slice follows `ar2-7d-disable-uninstall-reinstall-plan.md`. It changes only the test-only offline Registry fixture. It does not change production runtime behavior, user Docker configuration, Registry upload/auth behavior, the 60 second pull bound, or any Provider/release authority.

## Failure evidence and root cause

The signed installation probe repeatedly timed out before business logic while pulling the approximately 59 MB localhost image. Temporary request logging showed only the host readiness request (`GET /v2/`) and no daemon manifest/blob request. Restarting `colima-aos-extension` did not change that observation, excluding an inherited pull lock and the Registry server's single-threaded response path.

The user Docker configuration names the Docker Desktop credential helper while Docker Desktop is stopped after the host reboot. A bounded probe of that helper for `127.0.0.1:18433` did not return within five seconds. Therefore `docker pull` was blocked during credential lookup before contacting the test Registry.

## Minimal correction

`offline_registry.py` now resolves the exact daemon endpoint from the requested Docker context and uses a fixture-local Docker config containing no credentials for the localhost pull only. All build, run, inspection, and cleanup operations remain on the requested context. The temporary config lives below pytest's temporary Registry directory and teardown remains exact and independently observed.

The diagnostic `ThreadingHTTPServer` experiment was removed after the request evidence disproved the concurrency hypothesis. `static_registry_server.py` remains the original read-only `HTTPServer` with GET/HEAD only, fixed digest content, no upload endpoint, and localhost-only publication.

## Verification

- Exact signed installation: `1 passed` in 3.23 s; previously timed out at 60 s before the Registry received a daemon request.
- Signed worker configuration lifecycle: `1 passed` in 10.92 s, covering signed pull, real OCI preparation, verification, configuration, lifecycle control, and cleanup.
- Signed journaled OCI neighbor: `2 passed, 11 deselected` in 4.53 s, covering both successful registration and registration-journal failure cleanup.
- Residue readback: zero `ar1-registry-*` containers and zero containers carrying `aos.extension.owner`.
- Closure verifier (`--phase ar2-1`): 1710 Python modules scanned, 93 classified, 57 migrated; all error lists empty.
- Memory validator: `GREEN`, project revision `AOS-000571`, 865 Delivery Receipts and 846 Task Receipts.
- `git diff --check`: pass.

The recurring interpreter-shutdown logging warning from `jdbc_connector_runtime.py` remains an existing test-harness warning after pytest has already reported success; it does not change the assertions or cleanup result.

## Next step

Proceed to D6D2's dedicated same-tenant/same-schema signed ecommerce lifecycle test. This prerequisite does not by itself establish `AR2_7D_DISABLE_UNINSTALL_REINSTALL_GREEN`.
