# AO Policy v3 natural advisor chain plan — 2026-09-19

## Objective

After AO's saved twelve-source recovery reaches a verified terminal success, continue the existing QYH advisor baseline Case through a new Policy revision 3. The Runtime Host must naturally create and consume a new schedule occurrence, then start the existing governed analysis chain. No developer-created Case/Run, direct SQL mutation, manual `run_definition`, source reread or replay of the two historical occurrences is permitted.

## Current immutable boundary

- current runtime target: AO installation `d4186607-c93f-4fd0-8daa-46e349184ab9`, generation `00bb99df-d436-483d-86df-496718c6f129`, epoch 3;
- current saved recovery authority: definition revision 59 / recovery revision 19; natural attempt `67c2331d-b73f-4863-b881-0d67e6c55508` is still running when this plan is written;
- baseline Case `case-qyh-advisor-baseline-20260917` is ACTIVE at head revision/version 4;
- baseline Policy `schedule-qyh-advisor-baseline-once-20260917` is enabled at revision 2;
- Policy v1 occurrence `3c927751-b91a-53d0-8a42-7c5223ea109d` and v2 occurrence `34733f17-f1ce-582d-b1b6-585a96aee2ff` are both terminal `cancelled`. Neither occurrence, dispatch attempt nor target idempotency key may be reused;
- Policy revisions 1 and 2 remain bound to retired S and their historical control Receipts. They are evidence only and cannot authorize AO.

## Entry gate

Policy v3 preparation is allowed only when all checks pass in one current read:

1. AO recoverable_store attempt is `succeeded`, definition revision 59 is the exact enabled authority, and recovery revision 19 is current;
2. the original Store idempotency key has exactly one terminal Receipt whose request/result boundary reconciles with the saved link command;
3. expected `ecom_link` and projection state are complete, the twelve Runs and dataset Receipts remain exact, and no retirement or unresolved attempt exists;
4. AO is the only live installation for the nine business routes, its three resources are live, and `dev-org/dev-project` remains zero;
5. Case rev4, Policy rev2 and both cancelled occurrences match this plan; there is no active baseline Run and no usable current GrowthPlan;
6. current model, skill/capability, budget, role and schedule approval prerequisites remain valid.

Any mismatch stops before a proposal or Policy write. A failed or abandoned AO recovery enters retirement/direct-successor handling instead of this plan.

## File-level implementation inventory

### A. AO baseline preflight and v3 command executor

- add `scripts/a0v_ao_advisor_baseline_v3.py`;
- add `services/aos-api/tests/extension_runtime/test_a0v_ao_advisor_baseline_v3.py`.

The executor will bind the exact AO installation/generation/epoch, Case rev4, Policy rev2, both cancellation/closure facts and the successful snapshot group. It will expose separate `preflight`, `approval`, `put`, `observe` and terminal `disable` readiness actions. Every mutating action freezes intent before mutation and refuses an existing unknown intent rather than resending. Terminal disable readiness is read-only; a later fresh approval and canonical write are required before Policy disabling.

### B. Natural occurrence and analysis verification

- add `scripts/a0v_ao_advisor_baseline_v3_observe.py` because the original `observe` output does not join schedule binding, dispatch attempt, target Receipt and Run trigger authority;
- add `services/aos-api/tests/extension_runtime/test_a0v_ao_advisor_baseline_v3_observe.py`;
- add a verification document under this evidence directory.

The read-only observer classifies deterministic phases from one current read: awaiting Policy/control/binding, awaiting occurrence, occurrence pending, awaiting dispatch Receipt, awaiting Run, analysis running, or GrowthPlan ready. A GrowthPlan counts only when its `generationArtifactRef` joins to the producing AgentRun and TaskRun, and that Task's immutable intent `goal.runRef` identifies the Business Run triggered by the v3 occurrence target key. A tenant-level plan count is insufficient. The new Policy must be revision 3 and its `SchedulePolicyControlReceipt` must bind AO epoch 3 plus a fresh exact `ActionApprovalEvent`. The host alone creates the deterministic v3 occurrence and starts the Run. A missing business plan is handled by the existing baseline analysis path; it is not filled by fixture or developer input.

### C. Product acceptance continuation

When a readable, sourced GrowthPlan candidate exists, the next waves are exact plan review, internal content/operations task graph, capability/budget/approval controlled artifacts, human review continuation, management recap and Wiki candidate. Eight-workbench scenarios and three real observation windows remain separate acceptance work.

## Verification and stop rules

- focused contract and PostgreSQL isolation tests, affected cumulative regression, AR2 phase validation and browser acceptance are mandatory;
- browser visibility requires the current AO package/catalog authority. A route or test green alone is not UI acceptance;

### D. Terminal one-shot Policy closure

After the exact v3 chain has one succeeded occurrence, one exact linked GrowthPlan and no active Business Run, close the one-shot schedule through three separate actions:

1. `disable` performs a fresh read-only observer pass and freezes readiness only;
2. `disable-approval` creates and approves a new maker/checker proposal for the disabled Policy body, expected Policy revision 3 and Case version 4;
3. `disable-put` sends one canonical `ecommerce_growth_schedule_put` command with a new idempotency key, producing Policy revision 4 with `enabled=false` and disabling schedule bindings.

Each step freezes its intent before mutation and refuses an existing unknown intent. A failed/cancelled occurrence, unrelated GrowthPlan, active Run, missing Receipt or negative-tenant state cannot open closure. The earlier v3 approval cannot authorize the v4 disable write.
- unknown proposal, Policy write, dispatch, model or Store result is reconciled read-only and never resent;
- no external publication, outreach, price change, ad spend or 230 L0 action is authorized by this plan;
- completion of Policy v3 configuration is not completion of the business chain. Only source-backed plan, exact review, governed artifacts, human continuation, recap and Wiki candidate close the first-chain target.
