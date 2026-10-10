# Complete ending: validation call graph audit

Rules: 231, Main complete eight-node/Receipt contract, unique m1 writer, current Task/Lease, original Source/budget/physical kernels preserved. No database operation, native arm, Provider or execution authority.

Registered candidates: (1) Main final validation/Receipt closure, authorized by Main Task; depends on original facts, all eight persisted nodes and validation after waits. (2) native arm/end, authorized by native support Task; depends on a fixed validator with no deferred-event-producing writes and immutable package authority. Choose (1) first because candidate (2) cannot safely call an unclassified validator.

Exact files this step: this plan, audit.py, result.json and emitted SQL snapshots in this directory. No product code modification. Before any later product change update implementation-plan-1698.md with exact extraction, compatibility and native acceptance requirements.

Generate actual SQL from the current product generators. Trace the two proposed final readers into their known producers. Freeze hashes and full SQL, report every direct DML and the concrete call edges. Exit 1 when either reader reaches a producer; this is a design RED, not a test of a nonexistent full finalizer. Unknown external calls remain unproven, never implicitly pure.

Required next implementation: retain existing producer SQL and ACL behavior byte-exact; create fixed final-only validation that reconstructs the original Intent and dependency bodies from original Suite/input/Source/certificates, compares all immutable persisted nodes and Receipt, and uses the already-held physical account version without incrementing it. All writes and lock waits precede native drain. Recheck original current Source/certificates and database time after waits. Native pending/event/RI and callback/package closure, actual COMMIT and postcommit unknown retention remain separate mandatory gates. No helper-only Delivery.
