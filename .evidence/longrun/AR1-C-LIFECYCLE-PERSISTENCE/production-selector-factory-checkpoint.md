# AR1-C production selector and tenant worker factory checkpoint

Date: 2026-09-06

## Result

`PRODUCTION_SELECTOR_FACTORY_GREEN`, limited to selector and factory construction.
The persistent host is not started from `main` in this checkpoint and business
scenario count remains zero.

## Closed invariants

- Disabled or incomplete configuration performs zero directory, runtime, Web,
  or OCI access and returns a fixed INACTIVE result.
- An empty trusted directory performs one directory read and zero runtime/Web
  identity or OCI access.
- A non-empty directory is decoded into immutable descriptors before the
  runtime/Web identity preflight. Identity failure constructs zero tenant
  workers; materialization happens only after all three principals pass.
- Production configuration admission accepts only the AIP factory-minted
  current four-source authorization with the concrete current installation
  permission. The mint has no reader parameter and fixes the responsibility,
  data-classification, budget, and runtime-policy readers internally.
- A successful selection materializes only ExpiredResourceRecovery,
  ConfigurationConsumer, and RuntimeDisableConsumer with the persistent drain
  reader, exact disable permission, PostgreSQL installation store, and
  cleanup-only OCI facade.

## Verification

- Focused and adjacent suite: 64 passed.
- Isolated PostgreSQL directory, role, CAS, identity, selector, and drain suite
  on port 18432: 11 passed.
- Full extension-runtime suite with isolated PostgreSQL enabled: 738 passed,
  28 skipped.
- Python compile, `git diff --check`, and independent Prime review: passed.
- Browser acceptance: not applicable because this backend checkpoint changes no
  page.

## Explicit non-claims

No shared migration, real tenant mutation, OCI operation, Provider call, budget
hold, publish action, or business-task dispatch was executed. ACTIVE means the
host object was safely constructed; it does not mean a background host was
started. The next checkpoint owns explicit `main` startup, shutdown
convergence, process reconstruction, and the first bounded read-only business
scenario.
