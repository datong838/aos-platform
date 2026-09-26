"""Read-only preflight for the controlled content pre-review authority install.

This module does not migrate schemas, register packs, run Eval, or enable a
worker. Partial or unknown state is a reconciliation boundary, not a retry cue.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from aos_api.ecommerce_content_pre_review_authority import require_current_content_pre_review_gate
from aos_api.ecommerce_content_pre_review_eval import GRAPH_ID
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[[], AbstractContextManager[Any]]
_SUITES = (
    "ecommerce.content.pre-review.governance.v1",
    "ecommerce.content.pre-review.subject.v1",
)
_REQUIRED_SCHEMA = "a0v_105"


@dataclass(frozen=True)
class ContentPreReviewInstallPreflight:
    state: str
    schema_revision: str | None
    graph_count: int = 0
    suite_count: int = 0
    contract_count: int = 0


def preflight_content_pre_review_install(
    scope: TenantScope, connect_factory: ConnectFactory,
) -> ContentPreReviewInstallPreflight:
    """Inventory one tenant without side effects; only full authority is installed."""
    if type(scope) is not TenantScope:
        raise ValueError("content pre-review install needs exact tenant scope")
    with connect_factory() as conn:
        versions = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        schema = versions[0]["version_num"] if len(versions) == 1 else None
        if schema != _REQUIRED_SCHEMA:
            return ContentPreReviewInstallPreflight("SCHEMA_BLOCKED", schema)
        graphs = conn.execute(
            """SELECT graph_id FROM aip_logic_graph
                WHERE org_id=%s AND project_id=%s AND graph_id=%s LIMIT 2""",
            (*scope.key, GRAPH_ID),
        ).fetchall()
        suites = conn.execute(
            """SELECT suite_id,revision FROM aip_eval_suite_revision
                WHERE org_id=%s AND project_id=%s AND suite_id IN (%s,%s)""",
            (*scope.key, *_SUITES),
        ).fetchall()
        contracts = conn.execute(
            """SELECT contract_id,revision FROM aip_eval_contract_revision
                WHERE org_id=%s AND project_id=%s
                  AND gate_policy->>'subjectKind'=%s""",
            (*scope.key, "ecommerce_content"),
        ).fetchall()
        counts = (len(graphs), len(suites), len(contracts))
        if counts == (0, 0, 0):
            state = "INSTALLABLE"
        elif (
            counts == (1, 2, 2)
            and {(row["suite_id"], row["revision"]) for row in suites}
            == {(suite_id, 1) for suite_id in _SUITES}
            and len({row["contract_id"] for row in contracts}) == 1
            and {row["revision"] for row in contracts} == {1, 2}
        ):
            # create/freeze makes two immutable revisions of one contract.
            # Identity and all cross-lineage checks belong to the exact reader.
            try:
                require_current_content_pre_review_gate(conn, scope)
            except ValueError:
                state = "RECONCILE_REQUIRED"
            else:
                state = "INSTALLED"
        else:
            state = "RECONCILE_REQUIRED"
        return ContentPreReviewInstallPreflight(state, schema, *counts)
