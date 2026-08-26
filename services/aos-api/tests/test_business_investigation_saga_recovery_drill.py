"""BI-W6-07 recovery drill composed from the canonical lower-level gates.

The aliases intentionally keep pytest from collecting the imported gates twice;
each test below is the named, reviewable BI-W6 recovery evidence boundary.
"""

from __future__ import annotations

from test_aip_business_investigation_compile_saga import (
    test_disposable_database_receipt_replay_isolation_immutability_and_restart as _compile_restart,
)
from test_business_investigation_saga_convergence import (
    test_publication_receipt_survives_partial_failure_and_reentry as _partial_failure_reentry,
)
from test_ecommerce_business_investigation_artifact_publication import (
    test_disposable_database_publish_replay_rls_and_nonempty_downgrade as _artifact_rollback,
)
from test_ecommerce_business_investigation_reconciliation import (
    test_waiting_unknown_reconciling_replay_isolation_and_illegal_transitions as _run_reconcile_restart,
)


def test_compile_receipt_survives_process_restart_and_refuses_destructive_rollback() -> None:
    _compile_restart()


def test_artifact_publication_survives_replay_and_refuses_destructive_rollback() -> None:
    _artifact_rollback()


def test_run_reconcile_history_survives_restart_and_refuses_destructive_rollback() -> None:
    _run_reconcile_restart()


def test_cross_service_partial_failure_reenters_from_immutable_receipt() -> None:
    _partial_failure_reentry()
