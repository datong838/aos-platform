# AR1-c current data/policy configuration sources checkpoint

Date: 2026-09-06

Scope: AIP-owned read-only adapters for exact current `data` and `policy`
configuration references. No public route, migration, provider call, business
write, spend, publish, or release was added.

## Implementation evidence

- `aip_runtime_configuration_sources.py` reads the original AIP data
  classification and runtime policy authorities through the caller's explicit
  transaction.
- Admission requires `current_user=aos_runtime`, exact tenant GUC, exact
  purpose/authority/id/revision/hash, current head, canonical payload/column
  consistency, active lifecycle, effective data-policy time, and runtime kill
  switch off.
- The mutable head is held `FOR SHARE`. The immutable revision is read in the
  same statement without granting the runtime role UPDATE rights. Database time
  is sampled only after the head lock returns.
- The extension-runtime kernel does not import AIP contracts or stores; the
  adapter remains on the AIP side for trusted composition-root injection.

## Test evidence

- Red: the first focused test failed with `ModuleNotFoundError` for the absent
  adapter.
- Focused final: 4 tests passed. The consolidated fail-closed matrix contains
  10 cases: tenant, purpose, authority, hash, stale data head, expired data,
  stale policy head, inactive policy, enabled kill switch, and payload drift.
  Separate cases prove the real `aos_runtime` role succeeds, the privileged
  connection is rejected, and a second connection actually waits on the head
  lock until the data policy expires before being rejected.
- Adjacent contracts: 94 passed across current source readers, configuration
  authorization/service, current control permission, and the original signed
  AIP budget reader.
- Final cumulative: 810 passed, 6 known Pydantic field-shadow warnings, exit 0,
  130.16 seconds. This covers all `extension_runtime` tests and the established
  asset-registry safety set.

## Environment finding

Two earlier cumulative attempts made the dedicated disposable PostgreSQL
container recover because its 512 MiB limit killed the checkpointer. Container
inspection showed `OomKilled=true` and approximately 487 MiB use. The isolated
`aos-ar1c-pg` limit was raised to 1 GiB; no shared database or business data was
changed. The complete cumulative suite then passed. These failed attempts are
not represented as code failures or as green evidence.

Browser acceptance: not applicable to this backend-only slice.

Next slice: compose current runtime-policy dependency readers and prove exact
binding between configuration `dataRefs` and the runtime policy's data
classification reference; this checkpoint alone is not `CurrentPolicy` and
does not authorize execution.
