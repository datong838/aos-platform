# AO foreground continuation router — 2026-09-19

## Objective and design

The foreground loop needs one deterministic next action from current authority. A periodic message or model judgement is not a continuation mechanism. The router is read-only and joins the AO attempt boundary, saved-recovery closure artifact, current advisor Policy, exact Policy v3 natural-chain phase and immutable executor artifacts.

The router never runs an executor, creates an approval, writes Policy state, resends an unknown result, reads a source or changes a browser. It emits `automaticAction=false` and one `nextAction`; the foreground controller must invoke the named existing executor separately and then re-read authority.

## Fixed decision order

1. healthy running AO → `OBSERVE_AO_RECOVERY`;
2. stale running AO → `DIAGNOSE_AO_HEARTBEAT`;
3. failed AO → `FREEZE_AO_FAILURE_BOUNDARY`;
4. succeeded AO with enabled rev59 definition → `RUN_AO_INSPECT_THEN_DISABLE`;
5. succeeded AO with exact disabled rev60 definition and closure artifact → Policy v3 preflight / approval / put, one step at a time;
6. enabled Policy v3 → observe the exact natural chain until one sourced GrowthPlan, then route through disable-readiness / fresh approval / canonical v4 put;
7. exact disabled Policy v4 → `START_FIRST_CHAIN_PLAN_REVIEW`;
8. every unknown or contradictory combination → `SAFE_BLOCKED`.

Immutable artifacts must also form a strict prefix: preflight → approval → v3 put → disable readiness → disable approval → v4 put. A later artifact without every predecessor is contradictory and blocks routing.

Only the existing governed executors own mutations. The router must remain useful after the definition changes from enabled rev59 to disabled rev60, so it cannot blindly reuse the running guard's enabled-definition invariant after closure.

## File inventory

- `scripts/a0v_ao_continuation_router.py`;
- `services/aos-api/tests/extension_runtime/test_a0v_ao_continuation_router.py`;
- this evidence document.

## Verification result

`AO_FOREGROUND_CONTINUATION_ROUTER_READY`

- 11 focused classifier/source-safety tests passed;
- 40 affected AO recovery, cutover, guard, Policy and observer tests passed;
- live read-only execution at AO revision 144 returned `RUNNING_HEALTHY_NO_ACTION` and the unique next action `OBSERVE_AO_RECOVERY`; heartbeat and Lease were healthy, 12 Runs were running and 0 had failed;
- AR2-7 closure verification scanned 1988 Python modules (200 classified, 93 migrated) with no hash, forward dependency, reverse caller, cross-layer import or dynamic-reference error;
- browser reload ultimately exposed `暂无可见工作台入口`, which is the correct product deny state before AO recovery and Policy v3 complete;
- no source read, business write, approval, Policy mutation, dispatch, `run_definition`, resend or external action was performed by the router.

The browser locator wait reported a deadline even though its own diagnostics already showed one visible matching element. A fresh complete accessibility read immediately confirmed the element. This is recorded as an acceptance-tool wait anomaly rather than product evidence loss.

## Machine-readable stdout hardening plan

The first shell consumer found that importing the AOS runtime emits structured service logs to stdout before and after the router JSON. The router decision was correct, but a consumer using `json.load` could not parse the mixed stream. The next minimal change will:

- remove runtime-heavy imports from module import time so pure classification stays side-effect free;
- load runtime modules and execute read-only observations while stdout is redirected to stderr;
- emit exactly one JSON object on stdout from `main`;
- add a subprocess test that parses the complete stdout with `json.loads`, while preserving existing pure decision tests.

No runtime authority or business behavior changes in this hardening.

### Stdout hardening verification

- runtime-heavy imports now occur only inside the live observer while stdout is redirected to stderr;
- a subprocess contract injects a runtime log and proves that complete stdout is one parseable JSON object while the log remains on stderr;
- 12 focused tests and 41 affected cumulative tests passed;
- live stdout parsed directly with `json.load`: AO revision 156, 12 running Runs, 0 succeeded, 0 failed, `nextAction=OBSERVE_AO_RECOVERY`; 14 framework diagnostic lines remained on stderr;
- AR2-7 verification remained clean across 1988 scanned modules;
- browser reload passed through `正在读取工作台目录` and settled on `暂无可见工作台入口`.

## Closed-runtime current-authority hardening plan

An exact historical `disable-result.json` is necessary but cannot alone authorize continuation if current database state has drifted to another attempt or runtime. Before any Policy v3 step, the router will require the current snapshot to match the same AO attempt, installation, generation, operation, recovery revision and manifest; 12 succeeded Runs and dataset Receipts; the one relationship/link command/retirement/Store Receipt; 1168 links and outbox rows; zero pending projection; nine routes, three resources and zero negative-tenant binding. Any mismatch blocks before reading or routing a Policy write.

### Closed-runtime authority verification

- the current closed snapshot contract covers 25 exact identity, lifecycle, Store, projection, route, resource and isolation fields plus non-null completion time;
- 15 independent drift mutations are rejected before Policy routing;
- 27 focused tests and 56 affected cumulative tests passed;
- live AO remained healthy at revision 162 with 12 running Runs and 0 failed, so the closed-state branch was correctly not opened;
- AR2-7 verification remained clean across 1988 modules;
- browser directory loading settled after about 4.3 seconds on `暂无可见工作台入口`.
