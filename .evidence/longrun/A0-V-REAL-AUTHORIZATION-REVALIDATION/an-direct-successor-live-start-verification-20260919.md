# AN direct successor live-start verification — 2026-09-19

## Result

`AN_DIRECT_SUCCESSOR_NATURAL_ATTEMPT_RUNNING`

This is a live-start checkpoint, not terminal business-loop completion.

## Formal replacement and cutover

- predecessor AM installation/generation: `fd28d180-db24-4568-a848-101fcd3aa3c5` / `d6bc117e-d19d-4413-beb4-02884206e290`;
- predecessor disable operation: `6d94d641-6fc3-4edd-801c-69114d633c0c`;
- predecessor detach Receipt/hash: `af6fe6a5-2e88-4b7d-8756-0bc977871a5d` / `sha256:6f20be3f146e1f126c110b367bc43ba685d9450c9317d5f4950d29d69e07a709`;
- AN installation/generation: `7eebbd30-88fe-4c3d-a665-f36c5a9d64bb` / `41223cb2-28f6-4109-bdaf-e009ca084367`;
- AN lock/config hashes: `sha256:d5c65c91c105425da419c846eeeb0b33801b36e38106e189821d90bec20c5140` / `sha256:f7540524730672a656cd046036d90508bbbbb2b264698c16a7743b069e610444`;
- AN lifecycle operations `runtime-apply`, `runtime-verify`, `configure` and `enable` all succeeded;
- successor registration Receipt: `363371b0-06e8-42e5-9160-b502f38d7947`, request hash `sha256:d9a407cb103beedcc8099d30163c10c64c570ba9c893eef2800c8c4b0fb4acc1`;
- cutover operation `844b18c4-9afe-4d5a-a9b2-b1011baf024d` completed ordered `prepare → pause → commit → validate → resume` receipts;
- nine operations now route to AN at route revision 93 / group revision 120; claim pause is released;
- external effects and fallback remained disabled throughout cutover.

## Saved snapshot continuation

- definition transferred from disabled AM revision 54 to disabled AN revision 55;
- recovery advanced from revision 17 to revision 18;
- current AN definition is enabled at revision 56;
- frozen input manifest remains `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`;
- all twelve existing Runs and twelve dataset Receipts were retained;
- source reads performed by the successor flow: 0;
- original Store link idempotency key remains `snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b`.

## Natural Worker state

The post-renew read-only enable confirmation encountered a database row-lock timeout. It created no immutable output and performed no resend. A direct read showed the lock coincided with the independent Worker naturally claiming the enabled definition:

- attempt: `1d01cb93-3e8e-4063-b372-bdfb027d2ba3`;
- operation kind: `recoverable_store`;
- state: `running`;
- binding revision/epoch: 6 / 3, enabled and ready;
- three AN resources remain live and unreleased;
- Store Receipt count: 0;
- `ecom_link` count: 0;
- pending projection count: 0;
- `dev-org/dev-project` canary binding count: 0.

No manual `run_definition`, source reread, Store resend or direct business-table write was used.

## Next action

Keep the AN attempt under read-only observation. While heartbeat and Lease advance, do not retry the enable check and do not alter runtime state. On success, run the existing inspect/disable terminal path after exact Store Receipt/link/projection reconciliation. On failure, freeze the terminal reason and unknown-commit boundary before any retirement decision.
