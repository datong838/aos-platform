# AO saved-snapshot natural start verification — 2026-09-19

## Result

The frozen twelve-source snapshot was transferred from retired AN to AO without a source reread or manual definition execution.

- AO installation/generation: `d4186607-c93f-4fd0-8daa-46e349184ab9` / `00bb99df-d436-483d-86df-496718c6f129`;
- input group/manifest: `c5ff1926-45b0-56de-b6b3-07d5b7d053a1` / `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`;
- definition transfer: AN revision 57 disabled → AO revision 58 disabled;
- recovery renewal: revision 19, content hash `sha256:201d772b6956daccc3404593bb75d1037f20ea6ac8807179ba8f9ba32a1f98a8`;
- enabled definition: revision 59, content hash `sha256:5976daf9979743fa23cdc66f9b22f79df8d8e0e4f82e1f9b360c5816a81d58bd`;
- renewal result explicitly recorded `executionStarted=false` and `sourceReads=0`.

## Natural worker claim

The confirmation read encountered a database row-lock timeout while the independent worker held the AO installation row. It produced no result marker and was not retried. A separate non-locking read established the authoritative execution state:

- attempt: `67c2331d-b73f-4863-b881-0d67e6c55508`;
- operation: `recoverable_store` / `snapshot-group-completion:c5ff1926-45b0-56de-b6b3-07d5b7d053a1`;
- state: `running`, accepted at `2026-09-19T02:41:41.455890Z`;
- heartbeat revision advanced from 4 at `02:43:12Z` to 5 at `02:43:42Z`; Lease advanced to `02:45:42Z`;
- the single attempt uses AO execution epoch 3. No second attempt exists.

This proves natural worker claim. No `run_definition` call or resend was used.

## Side-effect boundary at 02:44:03Z

- 12 snapshot members, 12 running Runs and 12 dataset Receipts;
- one relationship and one existing link command; zero retirement;
- original Store idempotency key remains unchanged in the executor;
- Store Receipt 0, `ecom_link` 0, pending projection 0;
- three AO resource leases remain live;
- `dev-org/dev-project` canary binding count 0;
- browser `http://127.0.0.1:8434/ontology` settled at `暂无可见工作台入口`, so the incomplete recovery does not expose the ecommerce workbenches.

## Verification and limits

- focused contract test: 1 passed, 7 known warnings;
- syntax compilation and `git diff --check`: passed;
- code/plan consistency: actions are limited to prepare, schedule confirmation, controls, transfer, renew, read-only confirmation/inspection and terminal disable. The transfer requires exact predecessor revision 57 and renewal requires exact revisions 19/59.

The attempt is still running. This evidence records a healthy start, not Store success or business-chain completion. The next wave is read-only observation of heartbeat, Lease, Run state, Store Receipt/link/projection boundary and tenant canary. On success, run the existing inspect/disable terminal path; on failure, freeze the exact failure before any successor decision.
