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

## AO identity-chain hardening plan

Before Policy v3 is allowed to advance the phase classifier, every authority row must belong to the exact AO runtime. A matching revision alone is insufficient:

- the control Receipt must bind Policy v3 to Case v4, AO installation `d4186607-c93f-4fd0-8daa-46e349184ab9`, generation `00bb99df-d436-483d-86df-496718c6f129`, execution epoch 3, and a non-empty approval event;
- the enabled binding must use operation `ecommerce_growth_schedule_trigger` and the same AO installation, generation and epoch;
- every Policy v3 occurrence considered by the classifier must use that operation and AO identity;
- rows with Policy revision 3 but any mismatched identity remain visible as diagnostic evidence, but cannot advance the natural-chain phase;
- the once Policy requires exactly one v3 control, binding and occurrence, one recorded dispatch attempt for that occurrence, and an exact target Receipt key match;
- tests must cover valid identity and wrong installation, generation, epoch, Case revision and operation independently.

This is a read-only observer hardening. It does not modify Policy, schedule, occurrence, Case, Run, GrowthPlan or source data.

### Identity-chain verification result

- the observer now uses one exact AO identity predicate across control Receipt, enabled binding, occurrence and target runtime Receipt;
- functional tests reject wrong installation, generation, execution epoch, Case revision, approval event, operation, approval state and enabled state at their respective phase boundary;
- focused tests: 25 passed; affected AO recovery/cutover/Policy cumulative regression: 29 passed;
- the hardened observer executed against `org-org/dev-project` and remained at `awaiting_policy_v3`: current Policy rev2, target Receipts 0, exact Runs 0, exact GrowthPlans 0, canary 0 / 0 / 0;
- AO remained healthy at revision 130 with 12 running Runs, 0 succeeded and 0 failed; no automatic action was authorized;
- browser reload settled on `暂无可见工作台入口`, consistent with the incomplete recovery and absent Policy v3.

## Exact GrowthPlan lineage hardening

The initial observer selected every tenant GrowthPlan head. That was safe while the tenant had zero plans, but it could later misclassify an unrelated plan as this natural chain's output. The observer now accepts a GrowthPlan only through this exact join:

`GrowthPlan.generationArtifactRef → aip_artifact.source.agentRunId → aip_agent_run.task_run_id → aip_task_run.task_id → aip_task.goal.runRef`

The final `goal.runRef.resourceId` must equal a Business Run whose trigger key is one of the Policy v3 occurrence target keys. A plan from another Run or task is excluded even when it belongs to the same tenant.

- focused observer, Policy v3 and AO guard regression: 18 passed;
- the tightened SQL executed successfully against `org-org/dev-project`;
- current phase remains `awaiting_policy_v3`, with zero exact Runs and zero exact GrowthPlans;
- AO was still running at revision 109 during this observation;
- browser reload again settled on `暂无可见工作台入口`.
