# Two-callback actual COMMIT ordering experiment

Rules:231, support full ending protocol, exact active unique-owner Lease. No product arm or formal database change.

Write only this evidence directory and newly named test_owned_order_ tables in the retained exact isolated PG16.14 lab. Freeze a test-only C library with two registered callbacks. Writer performs one fixed INSERT into an owned sample table with an unconditional rejecting deferred trigger; observer checks native pending status and inserts only an owned observation row without deferred triggers. Neither accepts arbitrary SQL. Both require superuser, top-level nonparallel arm and owned ordinary tables under the dedicated test prefix. PUBLIC/runtime receive no execute permission.

Fresh backend per case. Register writer then observer: observer executes first, sees no pending events, writer later queues one; demonstrate actual COMMIT can succeed despite the deferred rejection. Reverse registration: writer executes first, observer sees pending and rejects actual COMMIT. Ordinary INSERT/COMMIT is a negative control proving the guard actually rejects. Persist each intent before COMMIT, reconcile independently by XID/table/marker state; never repeat an unknown outcome. Verify original guard body, enabled triggers, signature library, role flags and container start unchanged.

This test-only superuser probe is not production authority, a full ending solution, Source acceptance, Task Delivery or natural first-chain evidence. It determines whether merely registering an arm callback after other callbacks closes the full contract; expected answer is no. Complete protocol must constrain every later callback or use a separately proved engine integration point.
