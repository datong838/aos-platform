# AO direct successor and saved-snapshot continuation plan — 2026-09-19

## Authority and predecessor

- branch/worktree: `m1` / `/Users/ddt/work/projects/ai_agent/aos-platform`; no push; 230 L0 suspended;
- predecessor AN: installation `7eebbd30-88fe-4c3d-a665-f36c5a9d64bb`, generation `41223cb2-28f6-4109-bdaf-e009ca084367`;
- AN disable operation: `7fdd2161-1732-4a14-8aa4-101be445e801`;
- authoritative AN detach Receipt/hash: `79254572-7c39-469e-860b-1ae2f36b4b6e` / `sha256:f28bc0f92775768a3aa7c6354cb03f5f7b77f61353888e3116f60014232678f4`;
- nine routes are legacy and fenced at route revision 95 / group revision 122;
- definition revision 57 is disabled; recovery revision 18 and the original input manifest remain frozen;
- one abandoned AN attempt is terminal, and Store Receipt, `ecom_link`, pending projection and canary effects are zero.

The detach Receipt authorizes a clean direct successor. It does not authorize source rereads, manual definition execution, Store resend, fallback or external effects.

## Staged file inventory

### Stage A — replacement lifecycle

- `scripts/a0v_ao_replacement_recovery.py`
- `services/aos-api/tests/extension_runtime/test_a0v_ao_replacement_recovery.py`

Create one new approved AO installation from the exact AN detach boundary, then execute runtime prepare, verify, stage, configure and enable with the existing signed bundle and current version set. The resulting installation and generation become immutable inputs to later stages.

### Stage B — registration and cutover

- `scripts/a0v_ao_successor_business.py`
- `scripts/a0v_ao_successor_cutover.py`
- matching tests under `services/aos-api/tests/extension_runtime/`.

Register AO only from the exact AN detach Receipt and group revision 122. Cut over in ordered `approve → prepare → pause → commit → validate → resume` phases with external effects and fallback disabled. Every phase freezes its intent before mutation and forbids resend when an intent already exists.

### Stage C — saved snapshot continuation

- `scripts/a0v_ao_saved_snapshot_recovery.py`
- matching contract test and verification evidence.

Transfer definition revision 57 to AO as disabled revision 58, renew recovery revision 19 and enable definition revision 59 without source reads. The independent worker alone may claim the definition. It must reuse the original Store idempotency key and the heartbeat-loss cancellation fix loaded in commit `4fcf7a5e`.

## Stop rules

1. Stop on any mismatch in predecessor identity, detach Receipt/hash, installation state, route revision, resource state, recovery ref, frozen manifest, Store counts or canary counts.
2. Never repeat an action whose immutable intent exists; inspect authoritative results instead.
3. Never call `run_definition`, write business tables directly, reread the 12 upstream sources, or change the original Store idempotency key.
4. A naturally running AO attempt is observation-only while heartbeat and Lease advance.
5. Success requires terminal Store Receipt, link/projection reconciliation, human-review continuation, management recap and Wiki candidate evidence; mere registration, cutover or test green is not business completion.

## First exit condition

Stage A ends only when AO has an approved installation, verified runtime, configuration, enabled binding revision 4 / epoch 3, three live resources, zero canary bindings and no business attempt. It is committed before Stage B starts.
