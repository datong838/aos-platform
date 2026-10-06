# S08 original approval-event native computation investigation

Baseline m1@9c1af07521179b6cf6ab49e7d64cb8594d06f09d / AOS-001379. Registered formal-boundary Task scope and plan amended before the test. No production implementation, migrations, canonical algorithm, authoritative database, or grants changed.

Real private SCRAM issuer on retained isolated aos_test_*: two original events created by original Source/allocation approval paths. PostgreSQL constructs all 13 original event fields including user actor, nullable fields, reason and canonical UTC timestamps. Whole JSON and canonical bytes agree with original Store model; SHA256 matches both original exact refs. Default SQL timestamp serialization yields a different hash. Each of 13 fields mutated in each of two events changes hash (26 comparisons).

Probe r1: 1 passed, 51 deselected, 7 warnings, 7.55s. Adjacent whole private-boundary file: 52 passed, 7 existing warnings, 69.49s. git diff --check clean. First invocation used a wrong working-directory prefix, so the append failed and pytest selected zero tests (exit5, 51 deselected); approval-event-native-probe.log retains that operational failure and is not counted as RED or acceptance. Corrected r1 is the evidence above.

Independent route_supervisor: no omitted original model fields or required changes in this scoped investigation. Positive rows do not exercise nullable expiry, all timestamp/infinity/year boundaries, historical non-UTC references, approval-currentness, Owner, withdrawal concurrency, or full publication. Hash mutation demonstrates sensitivity, not acceptance-rule validation. No full Task Delivery.

Publication plan S10–S19 now names original dynamic facts, exact collections, maker/event/request/candidate formulas, unit/window constraints, clocks and original guard ordering. These are implementation requirements, not implemented SQL or supplier authority. Continue complete original SQL equivalence and trust/bootstrap/permit binding; publication time contract remains pending user decision.
