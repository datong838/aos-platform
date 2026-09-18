# AN direct successor implementation plan — 2026-09-19

## 1. Objective and authority

Create AN as the one formal direct successor of failed and detached AM for `org-org/dev-project`, then transfer the existing twelve-Run saved snapshot without any source reread. This wave restores an installable/configurable/deniable/recoverable runtime path; it does not claim that the natural business loop or eight workbenches are complete.

The only predecessor authority is:

- AM installation `fd28d180-db24-4568-a848-101fcd3aa3c5`;
- generation `d6bc117e-d19d-4413-beb4-02884206e290`;
- disable operation `6d94d641-6fc3-4edd-801c-69114d633c0c`;
- detach Receipt `af6fe6a5-2e88-4b7d-8756-0bc977871a5d`;
- detach content hash `sha256:6f20be3f146e1f126c110b367bc43ba685d9450c9317d5f4950d29d69e07a709`;
- runtime binding revision 8 / epoch 4, disabled, fenced and detached;
- nine legacy routes at revision 92 / cutover group revision 119;
- all three AM resources released;
- definition revision 54 disabled, twelve saved Runs retained;
- running/unresolved/runtime-pending/canary/Store Receipt/Store link/projection-pending counts all zero.

Every write remains subject to an exact reread of this authority. Unknown result, CAS drift, unexpected attempt, tenant leakage or existing immutable intent stops the wave; no new idempotency key may be used to bypass an uncertain result.

## 2. File-level implementation inventory

### Phase A — create the actual AN identity

- `scripts/a0v_an_replacement_recovery.py`
  - read and verify the exact AM detach Receipt and the complete detached installation/resource/route state;
  - create one approved AN installation with a new installation identity, generation, resource set and immutable private evidence;
  - drive only the formal `prepare → verify → stage → configure → enable` lifecycle services;
  - support observation without resending; never call `run_definition`.
- `services/aos-api/tests/extension_runtime/test_a0v_an_replacement_recovery.py`
  - assert the exact AM predecessor Receipt/hash and route revisions;
  - assert lifecycle order, new AN label/state directory, fail-closed existing-intent rule and absence of manual execution.

Phase A must finish before Phase B is authored because AN installation, generation, configuration and lock hashes must be copied from real immutable receipts, never predicted.

### Phase B — register and cut over the real AN identity

- `scripts/a0v_an_successor_business.py`
  - bind the actual AN installation/generation/configuration to the exact AM detach Receipt;
  - require tenant drained counts to remain zero and group revision 119 to remain legacy/fenced;
  - register with `externalEffects=false` semantics and read back the exact request hash.
- `scripts/a0v_an_successor_cutover.py`
  - use a fresh cutover operation and approval chain;
  - perform `approve → prepare → pause → commit → validate → resume` in order;
  - prohibit fallback and external effects; never update dispatch tables directly.
- matching tests under `services/aos-api/tests/extension_runtime/test_a0v_an_successor_*.py`.

### Phase C — transfer the saved snapshot and let the Worker act naturally

- `scripts/a0v_an_saved_snapshot_recovery.py`
  - transfer from disabled AM definition revision 54 to a new disabled AN definition revision;
  - renew the existing recovery from revision 17 using the frozen manifest;
  - preserve the twelve dataset Receipts, relationship/link command, original link idempotency key and 12 Runs;
  - assert `sourceReads=0` and create a new six-hour control window;
  - enable scheduling only after all exact refs match.
- `services/aos-api/tests/extension_runtime/test_a0v_an_saved_snapshot_recovery.py`
  - cover predecessor refs, revision chain, no source read/manual definition execution, original Store key and fail-closed recovery checks.

No script may create a runtime execution attempt directly. Only the already-running independent Worker may claim the enabled definition and create the one legal recoverable Store attempt.

## 3. Execution and verification order

1. Run static Red for the absent Phase-A script, implement the minimum file, then run its focused test and Python compilation.
2. Execute Phase A one action at a time. After each action, read the immutable result and live installation state before continuing. If a command outcome is unknown, stop and reconcile by the same key.
3. Freeze the resulting AN IDs/hashes into Phase-B code and tests; run preview before registration, then execute the ordered internal cutover.
4. Freeze the final route and runtime refs into Phase C; transfer and renew with `sourceReads=0`, then enable once.
5. Observe the natural Worker. Never invoke `run_definition`, never resend an unknown Store result, and never treat a heartbeat as business completion.
6. Verify `dev-org/dev-project` remains empty, API/Host/8434 remain healthy, and the browser changes from deny state only when the formal binding/catalog authority makes an entry visible.

## 4. Completion and next wave

This wave is complete only when AN is installed, configured, cut over, enabled, has a current saved-snapshot recovery, and the natural Worker has created a uniquely attributable attempt or has completed it with fully reconciled Receipts. Code/test green without those live facts is insufficient.

If the attempt succeeds, run inspect/disable and terminal resource/route verification, then enter the Advisor Policy v3 natural first-chain wave. If it fails, capture the exact failure and unknown-commit boundary before any formal retirement/direct successor decision.

Constraints retained: m1 single writer, no push, 230 L0 suspended, no reset/rebase/clean, no user-data overwrite, exact-file staging only.
