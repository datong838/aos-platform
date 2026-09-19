# AO Policy v3 natural-chain observer verification — 2026-09-19

## Outcome

`AO_POLICY_V3_OBSERVER_READY`

The observer is read-only. It does not create Policy, approval, occurrence, dispatch, Case, Run or GrowthPlan state and performs no source read.

## Implemented files

- `scripts/a0v_ao_advisor_baseline_v3_observe.py`;
- `services/aos-api/tests/extension_runtime/test_a0v_ao_advisor_baseline_v3_observe.py`.

The observer joins current baseline authority to schedule control Receipts, schedule bindings, occurrences, occurrence dispatch attempts, canonical runtime command Receipts, Run trigger Receipts, Run state heads, GrowthPlan heads/revisions and the negative tenant canary. A deterministic phase classifier reports where the natural chain currently stops.

## Current real observation

- phase: `awaiting_policy_v3`;
- current Policy revision: 2;
- historical control Receipts: 2;
- historical schedule bindings: 2;
- historical occurrences: 2;
- historical dispatch attempts: 2;
- target runtime Receipts: 0;
- baseline Case Runs: 0;
- GrowthPlan heads: 0;
- `dev-org/dev-project` bindings / occurrences / Runs: 0 / 0 / 0.

This is the correct boundary while AO saved-snapshot recovery is still running. The observer did not infer progress from a test, route or UI surface.

## Phase contract

The fixed order is: awaiting Policy v3 → awaiting control Receipt → awaiting enabled AO binding → awaiting natural v3 occurrence → occurrence pending → awaiting dispatch Receipt → awaiting canonical target Receipt → awaiting Run → analysis running → GrowthPlan ready.

## Verification

- Python compile passed;
- observer and Policy v3 focused tests: 4 passed;
- affected cumulative contract regression: 16 passed;
- the observer executed against `org-org/dev-project` and returned the exact current counts above;
- browser reload at `http://127.0.0.1:8434/ontology` settled on `暂无可见工作台入口`, proving that unfinished AO recovery and absent Policy v3 do not expose a premature workbench entry;
- the observer source contains no direct DML, `run_definition` or source-read path.

## Next boundary

AO terminal success and saved-snapshot disable remain prerequisites. Only afterward may the v3 executor create the fresh approval and canonical Policy write. The observer will then prove each naturally produced downstream authority without developer-created Case/Run wiring.
